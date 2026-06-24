import datetime
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from config import Config
from src import account_resolver, llm_provider, ocr_engine, schema_builder
from src.drive_client import DriveClient
from src.output.mf_api_client import MFApiClient


logging.basicConfig(level=Config.LOG_LEVEL)
logger = logging.getLogger(__name__)


def run() -> None:
    errors = Config.validate()
    if errors:
        for error in errors:
            logger.error(error)
            print(f"[x] {error}", file=sys.stderr)
        sys.exit(1)

    Config.ensure_directories()

    try:
        drive_client = DriveClient()
        mf_api_client = MFApiClient() if Config.OUTPUT_MODE == "mf_api" else None
        mf_accounts: list[dict] = []
        if mf_api_client is not None:
            try:
                mf_accounts = mf_api_client.get_account_items()
                logger.info("MF account master loaded (%d items)", len(mf_accounts))
            except Exception as exc:
                logger.warning("Failed to fetch MF account master at startup: %s", exc)
        person_folders = drive_client.list_person_folders(Config.INBOX_FOLDER_PATH)
    except Exception as exc:
        logger.error("Failed to initialize pipeline: %s", exc, exc_info=True)
        print(f"[x] 初期化失敗: {exc}", file=sys.stderr)
        sys.exit(1)

    started_at = time.perf_counter()
    total_count = 0
    success_count = 0
    mf_api_failed_count = 0
    error_count = 0

    for person_folder in person_folders:
        person_name = str(person_folder.get("name", "")).strip() or "unknown"
        person_folder_id = str(person_folder.get("id", "")).strip()
        if not person_folder_id:
            logger.warning("Skipping person folder without id: %s", person_folder)
            continue

        try:
            files = drive_client.list_files(person_folder_id)
        except Exception as exc:
            logger.error("Failed to list files for person=%s: %s", person_name, exc, exc_info=True)
            print(f"[ERR] {person_name} -> ファイル一覧取得失敗: {exc}")
            continue

        if files:
            print(f"[INFO] {person_name} ({len(files)}件)")

        for file_info in files:
            total_count += 1
            result = _process_file(
                drive_client=drive_client,
                mf_api_client=mf_api_client,
                mf_accounts=mf_accounts,
                person_name=person_name,
                person_folder_id=person_folder_id,
                file_info=file_info,
            )
            _append_jsonl_log(result)
            _print_result(result)

            status = result["status"]
            if status == "success":
                success_count += 1
            elif status == "mf_api_failed":
                mf_api_failed_count += 1
            else:
                error_count += 1

    elapsed = time.perf_counter() - started_at
    if total_count == 0:
        print("[DONE] 処理対象なし")
        return

    print(
        "[DONE] 成功 "
        f"{success_count}件 / MF失敗 {mf_api_failed_count}件 / "
        f"エラー {error_count}件 ({elapsed:.1f}秒)"
    )


def _process_file(
    drive_client: DriveClient,
    mf_api_client: MFApiClient | None,
    mf_accounts: list[dict],
    person_name: str,
    person_folder_id: str,
    file_info: dict[str, str],
) -> dict[str, Any]:
    started_at = time.perf_counter()
    file_id = str(file_info.get("id", "")).strip()
    original_name = str(file_info.get("name", "")).strip() or "unknown"
    current_folder_id = person_folder_id
    image_bytes = b""
    ocr_text = ""
    canonical: dict[str, Any] = {}
    renamed_to: str | None = None
    journal_id: str | None = None
    ocr_sec = 0.0
    llm_sec = 0.0
    mf_api_sec = 0.0

    def finalize(status: str, error_message: str | None = None) -> dict[str, Any]:
        total_sec = time.perf_counter() - started_at
        now = datetime.datetime.now().astimezone()
        return {
            "ts": now.isoformat(timespec="seconds"),
            "file": original_name,
            "person": person_name,
            "status": status,
            "renamed_to": renamed_to,
            "journal_id": journal_id,
            "vendor": _get_nested(canonical, "document.partner_name"),
            "total": _to_int(_get_nested(canonical, "document.total")),
            "account_title": _get_nested(canonical, "document.inferred.account_title"),
            "account_source": _get_nested(canonical, "document.inferred.account_source"),
            "timings": {
                "ocr_sec": round(ocr_sec, 2),
                "llm_sec": round(llm_sec, 2),
                "mf_api_sec": round(mf_api_sec, 2),
                "total_sec": round(total_sec, 2),
            },
            "error": error_message,
        }

    def fail(status: str, error_message: str) -> dict[str, Any]:
        move_error = _move_to_error_folder(
            drive_client=drive_client,
            file_id=file_id,
            current_folder_id=current_folder_id,
            person_name=person_name,
        )
        if move_error:
            error_message = f"{error_message} | move_to_error_failed: {move_error}"
        return finalize(status, error_message)

    try:
        image_bytes = drive_client.download_file(file_id)
        ocr_text, ocr_sec = ocr_engine.extract_text(image_bytes)
    except Exception as exc:
        return fail("ocr_failed", str(exc))

    try:
        past_journals = account_resolver.load_past_journals(Config.PAST_JOURNALS_CSV)
        context = account_resolver.build_context(past_journals, mf_accounts)
        llm_text, llm_sec = llm_provider.call_llm(ocr_text, context)
    except Exception as exc:
        return fail("llm_failed", str(exc))

    try:
        canonical = schema_builder.build_from_llm_output(llm_text)
        ok, errors = schema_builder.validate(canonical)
        if not ok or errors or str(canonical.get("status", "")).strip().lower() != "success":
            detail = "; ".join(errors) if errors else "schema validation failed"
            raise ValueError(detail)

        renamed_to = _build_renamed_file_name(original_name, canonical)
        file_id = drive_client.rename_file(file_id, renamed_to)
        processed_folder_id = drive_client.get_or_create_subfolder(
            Config.PROCESSED_FOLDER_PATH,
            person_name,
        )
        drive_client.move_file(file_id, processed_folder_id, current_folder_id)
        current_folder_id = processed_folder_id
    except Exception as exc:
        return fail("validation_failed", str(exc))

    if Config.OUTPUT_MODE == "mf_api" and mf_api_client is not None:
        mf_started_at = time.perf_counter()
        try:
            journal_id = mf_api_client.register_journal(
                canonical,
                mf_accounts,
                image_bytes,
                renamed_to or original_name,
            )
        except Exception as exc:
            mf_api_sec = time.perf_counter() - mf_started_at
            return finalize("mf_api_failed", str(exc))
        mf_api_sec = time.perf_counter() - mf_started_at

    return finalize("success")


def _build_renamed_file_name(original_name: str, canonical: dict[str, Any]) -> str:
    date_value = str(_get_nested(canonical, "document.date") or "").strip().replace("-", "")
    partner_name = str(_get_nested(canonical, "document.partner_name") or "").strip()
    suffix = Path(original_name).suffix
    safe_date = _sanitize_filename_part(date_value, "unknown_date")
    safe_partner = _sanitize_filename_part(partner_name, "unknown_vendor")
    return f"{safe_date}_{safe_partner}{suffix}"


def _sanitize_filename_part(value: str, fallback: str) -> str:
    table = str.maketrans({
        "\\": "_",
        "/": "_",
        ":": "_",
        "*": "_",
        "?": "_",
        '"': "_",
        "<": "_",
        ">": "_",
        "|": "_",
    })
    cleaned = value.strip().replace("\r", " ").replace("\n", " ").translate(table)
    return cleaned or fallback


def _move_to_error_folder(
    drive_client: DriveClient,
    file_id: str,
    current_folder_id: str,
    person_name: str,
) -> str | None:
    try:
        error_folder_id = drive_client.get_or_create_subfolder(
            Config.ERROR_FOLDER_PATH,
            person_name,
        )
        drive_client.move_file(file_id, error_folder_id, current_folder_id)
    except Exception as exc:
        logger.error(
            "Failed to move file=%s person=%s to error folder: %s",
            file_id,
            person_name,
            exc,
            exc_info=True,
        )
        return str(exc)
    return None


def _append_jsonl_log(record: dict[str, Any]) -> None:
    timestamp = datetime.datetime.fromisoformat(record["ts"])
    log_path = Config.LOG_DIR / f"{timestamp:%Y%m%d}.jsonl"
    try:
        with log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.error("Failed to append JSONL log to %s: %s", log_path, exc, exc_info=True)
        print(f"[x] ログ書き込み失敗: {exc}", file=sys.stderr)


def _print_result(record: dict[str, Any]) -> None:
    status = str(record["status"])
    display_name = str(record.get("renamed_to") or record.get("file") or "unknown")
    total_sec = float(record.get("timings", {}).get("total_sec", 0.0))

    if status == "success":
        if Config.OUTPUT_MODE == "mf_api":
            print(f"[OK] {display_name} -> 仕訳登録完了 ({total_sec:.1f}秒)")
        else:
            print(f"[OK] {display_name} -> 処理完了 ({total_sec:.1f}秒)")
        return

    if status == "mf_api_failed":
        print(f"[WARN] {display_name} -> 仕訳登録失敗、処理済みで保持 ({total_sec:.1f}秒)")
        return

    labels = {
        "ocr_failed": "OCR失敗",
        "llm_failed": "LLM失敗",
        "validation_failed": "バリデーション失敗",
    }
    label = labels.get(status, "処理失敗")
    print(f"[ERR] {display_name} -> {label}、エラーフォルダへ移動 ({total_sec:.1f}秒)")


def _get_nested(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for key in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").strip()
        if not cleaned:
            return None
        try:
            return int(cleaned)
        except ValueError:
            return None
    return None


if __name__ == "__main__":
    run()
