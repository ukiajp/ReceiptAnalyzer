import csv
import datetime as dt
import io
import logging
import os
from collections.abc import Mapping
from contextlib import suppress


logger = logging.getLogger(__name__)

FREE_TEXT_HEADERS = {
    "借方取引先",
    "貸方取引先",
    "摘要",
    "仕訳メモ",
    "タグ",
}

CSV_HEADERS = [
    "取引No",
    "取引日",
    "借方勘定科目",
    "借方補助科目",
    "借方部門",
    "借方取引先",
    "借方税区分",
    "借方インボイス",
    "借方金額(円)",
    "借方税額",
    "貸方勘定科目",
    "貸方補助科目",
    "貸方部門",
    "貸方取引先",
    "貸方税区分",
    "貸方インボイス",
    "貸方金額(円)",
    "貸方税額",
    "摘要",
    "仕訳メモ",
    "タグ",
    "MF仕訳タイプ",
    "決算整理仕訳",
    "作成日時",
    "作成者",
    "最終更新日時",
    "最終更新者",
]


def to_csv_row(canonical: dict) -> dict:
    document = canonical.get("document")
    if not isinstance(document, dict):
        document = {}

    inferred = document.get("inferred")
    if not isinstance(inferred, dict):
        inferred = {}

    extensions = document.get("extensions")
    if not isinstance(extensions, dict):
        extensions = {}

    total = _to_int(document.get("total"))
    row = {
        "取引No": "",
        "取引日": _format_trade_date(document.get("date")),
        "借方勘定科目": str(inferred.get("account_title") or ""),
        "借方補助科目": "",
        "借方部門": "",
        "借方取引先": "",
        "借方税区分": _resolve_tax_category(document.get("tax", {})),
        "借方インボイス": "",
        "借方金額(円)": total,
        "借方税額": "",
        "貸方勘定科目": "未払金",
        "貸方補助科目": "現金",
        "貸方部門": "",
        "貸方取引先": "",
        "貸方税区分": "対象外",
        "貸方インボイス": "",
        "貸方金額(円)": total,
        "貸方税額": "",
        "摘要": _build_description(document, extensions),
        "仕訳メモ": "",
        "タグ": "",
        "MF仕訳タイプ": "",
        "決算整理仕訳": "",
        "作成日時": "",
        "作成者": "",
        "最終更新日時": "",
        "最終更新者": "",
    }
    for header in FREE_TEXT_HEADERS:
        value = row.get(header, "")
        if isinstance(value, str):
            row[header] = _sanitize_csv_cell(value)
    return row


def export_to_file(canonical: dict, output_path: str) -> str:
    row = to_csv_row(canonical)
    directory = os.path.dirname(output_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    warnings = find_cp932_warnings(row)
    for warning in warnings:
        logger.warning("CP932 replacement required: %s", warning)

    should_write_header = not os.path.exists(output_path) or os.path.getsize(output_path) == 0
    with open(output_path, "a", encoding="cp932", errors="replace", newline="") as csv_file:
        writer = csv.writer(csv_file)
        if should_write_header:
            writer.writerow(CSV_HEADERS)
        writer.writerow(_ordered_row_values(row))

    logger.info("Exported canonical JSON to MoneyForward CSV: %s", output_path)
    return output_path


def export_rows_to_file(rows: list[Mapping[str, object]], output_path: str) -> str:
    directory = os.path.dirname(output_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    temp_output_path = f"{output_path}.tmp"
    try:
        with open(temp_output_path, "w", encoding="cp932", errors="replace", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(CSV_HEADERS)
            writer.writerows(_ordered_row_values(row) for row in rows)
        os.replace(temp_output_path, output_path)
    except OSError:
        with suppress(OSError):
            os.remove(temp_output_path)
        raise

    logger.info("Exported %d rows to MoneyForward CSV: %s", len(rows), output_path)
    return output_path


def export_to_string(canonical: dict) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    row = to_csv_row(canonical)
    writer.writerow(CSV_HEADERS)
    writer.writerow(_ordered_row_values(row))
    return buffer.getvalue()


def find_cp932_warnings(row: Mapping[str, object]) -> list[str]:
    warnings: list[str] = []
    for header in CSV_HEADERS:
        value = row.get(header, "")
        if not isinstance(value, str) or value == "":
            continue
        try:
            value.encode("cp932")
        except UnicodeEncodeError:
            warnings.append(f"{header}: {value}")
    return warnings


def _ordered_row_values(row: Mapping[str, object]) -> list[object]:
    values: list[object] = []
    for header in CSV_HEADERS:
        value = row.get(header, "")
        if isinstance(value, str):
            value = value.encode("cp932", errors="replace").decode("cp932")
        values.append(value)
    return values


def _resolve_tax_category(tax: dict) -> str:
    rate_10_amount = _to_int(_nested_get(tax, "rate_10.amount"))
    rate_8_amount = _to_int(_nested_get(tax, "rate_8.amount"))

    if rate_10_amount > 0 and rate_8_amount <= 0:
        return "課税仕入 10%"
    if rate_8_amount > 0 and rate_10_amount <= 0:
        return "課税仕入 8%"
    if rate_10_amount <= 0 and rate_8_amount <= 0:
        return "対象外"
    return ""


def _build_description(document: dict, extensions: dict) -> str:
    summary = str(extensions.get("summary") or "").strip()
    if summary:
        return summary
    return str(document.get("partner_name") or "").strip()


def _format_trade_date(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text:
        return ""
    try:
        parsed = dt.datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return text
    return f"{parsed.year}/{parsed.month}/{parsed.day}"


def _nested_get(data: object, path: str) -> object:
    current = data
    for key in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _to_int(value: object) -> int:
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


def _sanitize_csv_cell(value: str) -> str:
    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{value}"
    return value
