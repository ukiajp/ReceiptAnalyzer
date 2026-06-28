import argparse
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config import Config
from src import account_resolver
from src.output import csv_exporter


logger = logging.getLogger(__name__)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_JST = timezone(timedelta(hours=9))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build MoneyForward import CSV from canonical JSON.")
    parser.add_argument("--json-dir", default=Config.JSON_OUTPUT_DIR)
    parser.add_argument("--account-reference-path", default=Config.ACCOUNT_REFERENCE_PATH)
    parser.add_argument("--output-dir", default=Config.CSV_OUTPUT_DIR)
    return parser.parse_args()


def run() -> int:
    logging.basicConfig(level=Config.LOG_LEVEL)
    args = parse_args()

    json_dir = Path(args.json_dir)
    account_reference_path = Path(args.account_reference_path)
    output_dir = Path(args.output_dir)

    processed = 0
    csv_rows = 0
    errors = 0
    warnings_count = 0
    output_csv_path: Path | None = None

    rules = account_resolver.load_distill_table(account_reference_path)
    if not account_reference_path.is_file():
        warnings_count += 1
        _print_warning(account_reference_path, "勘定科目参照表が見つかりません")

    if not json_dir.is_dir():
        errors += 1
        _print_error(json_dir, "JSONディレクトリが見つかりません")
        _print_summary(processed, csv_rows, errors, warnings_count, output_csv_path)
        return 1

    export_rows: list[dict[str, Any]] = []
    for json_path in sorted(json_dir.rglob("*.json")):
        processed += 1
        try:
            canonical = _load_json(json_path)
            if canonical is None:
                errors += 1
                _print_error(json_path, "JSONを読み込めません")
                continue

            status = str(canonical.get("status") or "").strip().lower()
            if status == "failed":
                errors += 1
                _print_error(json_path, 'status=="failed"')
                continue

            document = canonical.get("document")
            if not isinstance(document, dict):
                errors += 1
                _print_error(json_path, "document不正")
                continue

            validation_messages = _validate_canonical(canonical)
            if validation_messages:
                errors += 1
                warnings_count += len(validation_messages)
                for message in validation_messages:
                    _print_warning(json_path, message)
                continue

            if _has_rate_8_tax(canonical):
                warnings_count += 1
                errors += 1
                _print_warning(json_path, "8%含む(要手動)")
                continue

            inferred = _ensure_inferred(document)
            account_title = str(inferred.get("account_title") or "").strip()
            vendor = str(
                inferred.get("partner_normalized") or _get_nested(canonical, "document.partner_name") or ""
            )
            resolved_account, confidence = account_resolver.resolve_account(vendor, rules)
            if resolved_account:
                inferred["account_title"] = resolved_account
                inferred["account_source"] = "distill_table"
                if "低" in confidence:
                    warnings_count += 1
                    _print_warning(json_path, "勘定科目低確信")
            elif account_title:
                inferred["account_title"] = account_title
                inferred["account_source"] = "claude_inference"
                warnings_count += 1
                _print_warning(json_path, "AI推定科目(要確認)")
            else:
                inferred["account_title"] = Config.DEFAULT_ACCOUNT_TITLE
                inferred["account_source"] = "default"
                warnings_count += 1
                _print_warning(json_path, "勘定科目未解決(既定科目)")

            row = csv_exporter.to_csv_row(canonical)
            encoding_warnings = csv_exporter.find_cp932_warnings(row)
            if encoding_warnings:
                warnings_count += len(encoding_warnings)
                for message in encoding_warnings:
                    _print_warning(json_path, f"cp932置換: {message}")

            export_rows.append(row)
        except Exception:
            warnings_count += 1
            errors += 1
            logger.exception("Failed to process JSON: %s", json_path)
            _print_warning(json_path, "処理中例外(要手動確認)")
            continue

    if export_rows:
        timestamp = datetime.now(_JST).strftime("%Y%m%d_%H%M%S")
        output_csv_path = output_dir / f"mf_import_{timestamp}.csv"
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            csv_exporter.export_rows_to_file(export_rows, str(output_csv_path))
        except OSError:
            errors += 1
            logger.exception("Failed to write CSV: %s", output_csv_path)
            _print_fatal(output_csv_path, "CSV書き込み失敗")
            _print_summary(processed, csv_rows, errors, warnings_count, None)
            return 1
        csv_rows = len(export_rows)
    else:
        print("[INFO] CSV対象0件のためファイルは作成しません")

    _print_summary(processed, csv_rows, errors, warnings_count, output_csv_path)
    return 0


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load JSON: %s (%s)", path, exc)
        return None

    if not isinstance(data, dict):
        logger.warning("Canonical JSON must be an object: %s", path)
        return None
    return data


def _validate_canonical(canonical: dict[str, Any]) -> list[str]:
    messages: list[str] = []

    total = _to_int(_get_nested(canonical, "document.total"))
    if total <= 0:
        messages.append("document.total不正")

    date_value = str(_get_nested(canonical, "document.date") or "").strip()
    if not _DATE_RE.fullmatch(date_value):
        messages.append("document.date不正")

    rate_10_base = _to_int(_get_nested(canonical, "document.tax.rate_10.base"))
    rate_10_amount = _to_int(_get_nested(canonical, "document.tax.rate_10.amount"))
    rate_8_base = _to_int(_get_nested(canonical, "document.tax.rate_8.base"))
    rate_8_amount = _to_int(_get_nested(canonical, "document.tax.rate_8.amount"))
    tax_total = rate_10_base + rate_10_amount + rate_8_base + rate_8_amount
    has_out_of_scope_tax = total > 0 and all(
        value == 0 for value in (rate_10_base, rate_10_amount, rate_8_base, rate_8_amount)
    )
    if not has_out_of_scope_tax and tax_total != total:
        messages.append("税合算不一致")

    return messages


def _has_rate_8_tax(canonical: dict[str, Any]) -> bool:
    rate_8_base = _to_int(_get_nested(canonical, "document.tax.rate_8.base"))
    rate_8_amount = _to_int(_get_nested(canonical, "document.tax.rate_8.amount"))
    return rate_8_base > 0 or rate_8_amount > 0


def _ensure_inferred(document: dict[str, Any]) -> dict[str, Any]:
    inferred = document.get("inferred")
    if not isinstance(inferred, dict):
        inferred = {}
        document["inferred"] = inferred

    return inferred


def _get_nested(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for key in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def _to_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").strip()
        if not cleaned:
            return 0
        try:
            return int(cleaned)
        except ValueError:
            return 0
    return 0


def _print_warning(path: Path, message: str) -> None:
    print(f"[WARN] {path}: {message}")


def _print_error(path: Path, message: str) -> None:
    print(f"[ERR] {path}: {message}")


def _print_fatal(path: Path, message: str) -> None:
    print(f"[FATAL] {path}: {message}")


def _print_summary(
    processed: int,
    csv_rows: int,
    errors: int,
    warnings_count: int,
    output_csv_path: Path | None,
) -> None:
    print(f"processed={processed}")
    print(f"csv_rows={csv_rows}")
    print(f"errors={errors}")
    print(f"warnings={warnings_count}")
    print(f"output_csv={output_csv_path if output_csv_path else ''}")


if __name__ == "__main__":
    raise SystemExit(run())
