import csv
import io
import logging
import os


logger = logging.getLogger(__name__)

CSV_HEADERS = [
    "取引日",
    "借方勘定科目",
    "借方補助科目",
    "借方税区分",
    "借方金額",
    "借方税額",
    "貸方勘定科目",
    "貸方補助科目",
    "貸方税区分",
    "貸方金額",
    "貸方税額",
    "摘要",
    "タグ",
    "MF仕訳ID",
]


def to_csv_row(canonical: dict) -> dict:
    document = canonical.get("document", {})
    inferred = document.get("inferred", {})
    tax = document.get("tax", {})

    total = document.get("total", "")
    tax_category, tax_amount = _resolve_tax_fields(tax)

    return {
        "取引日": document.get("date", ""),
        "借方勘定科目": inferred.get("account_title", ""),
        "借方補助科目": "",
        "借方税区分": tax_category,
        "借方金額": total,
        "借方税額": tax_amount,
        "貸方勘定科目": "",
        "貸方補助科目": "",
        "貸方税区分": "",
        "貸方金額": "",
        "貸方税額": "",
        "摘要": _build_description(document),
        "タグ": "",
        "MF仕訳ID": "",
    }


def export_to_file(canonical: dict, output_path: str) -> str:
    row = to_csv_row(canonical)
    directory = os.path.dirname(output_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    should_write_header = not os.path.exists(output_path) or os.path.getsize(output_path) == 0

    with open(output_path, "a", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_HEADERS)
        if should_write_header:
            writer.writeheader()
        writer.writerow(row)

    logger.info("Exported canonical JSON to MoneyForward CSV: %s", output_path)
    return output_path


def export_to_string(canonical: dict) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_HEADERS)
    writer.writeheader()
    writer.writerow(to_csv_row(canonical))
    return buffer.getvalue()


def _resolve_tax_fields(tax: dict) -> tuple[str, int | str]:
    rate_10_amount = _to_int(tax.get("rate_10", {}).get("amount"))
    rate_8_amount = _to_int(tax.get("rate_8", {}).get("amount"))

    if rate_10_amount > 0 and rate_8_amount > 0:
        return "対象外", ""
    if rate_10_amount > 0:
        return "課税仕入10%", rate_10_amount
    if rate_8_amount > 0:
        return "課税仕入8%", rate_8_amount
    return "対象外", ""


def _build_description(document: dict) -> str:
    partner_name = str(document.get("partner_name", "")).strip()
    total = _to_int(document.get("total"))

    if partner_name and total > 0:
        return f"{partner_name} {total}円"
    if partner_name:
        return partner_name
    if total > 0:
        return f"{total}円"
    return ""


def _to_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
