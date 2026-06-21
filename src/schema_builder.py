import json
import logging
import re


logger = logging.getLogger(__name__)

_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)
_REGISTRATION_NUMBER_RE = re.compile(r"^T\d{13}$")
_REQUIRED_FIELDS = (
    "schema_version",
    "status",
    "document.document_type",
    "document.partner_name",
    "document.date",
    "document.total",
    "document.tax",
)
_CHECK_DIGIT_WEIGHTS = (1, 2, 3, 4, 5, 6, 7)


def build_from_llm_output(llm_text: str) -> dict:
    try:
        data = json.loads(_extract_json_text(llm_text))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Failed to parse LLM output: %s", exc)
        data = inject_defaults({})
        data["status"] = "failed"
        validation = _ensure_validation(data)
        validation["registration_number_checkdigit"] = "absent"
        validation["tax_sum_matches_total"] = False
        _set_errors(data, [f"Invalid JSON: {exc}"])
        return data

    if not isinstance(data, dict):
        logger.warning("LLM output JSON must be an object")
        data = inject_defaults({})
        data["status"] = "failed"
        validation = _ensure_validation(data)
        validation["registration_number_checkdigit"] = "absent"
        validation["tax_sum_matches_total"] = False
        _set_errors(data, ["Top-level JSON must be an object."])
        return data

    data = inject_defaults(data)
    missing_fields = [field for field in _REQUIRED_FIELDS if _get_nested(data, field) is None]
    if missing_fields:
        logger.warning("LLM output missing required fields: %s", ", ".join(missing_fields))
        data["status"] = "failed"
        validation = _ensure_validation(data)
        validation["registration_number_checkdigit"] = "absent"
        validation["tax_sum_matches_total"] = False
        _set_errors(data, [f"Missing required field: {field}" for field in missing_fields])
        return data

    _, errors = validate(data)
    if errors:
        _set_errors(data, errors)
    return data


def validate(data: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    validation = _ensure_validation(data)

    if data.get("status") == "failed":
        validation.setdefault("registration_number_checkdigit", "absent")
        validation.setdefault("tax_sum_matches_total", False)
        return False, ["status is failed"]

    total = _to_int(_get_nested(data, "document.total"))
    tax_values = [
        _to_int(_get_nested(data, "document.tax.rate_10.base"), default=0),
        _to_int(_get_nested(data, "document.tax.rate_10.amount"), default=0),
        _to_int(_get_nested(data, "document.tax.rate_8.base"), default=0),
        _to_int(_get_nested(data, "document.tax.rate_8.amount"), default=0),
    ]

    if total is None or any(value is None for value in tax_values):
        errors.append("Tax fields and total must be numeric.")
        validation["tax_sum_matches_total"] = False
        if data.get("status") != "failed":
            data["status"] = "partial"
    else:
        computed_total = sum(tax_values)
        is_tax_free = computed_total == 0
        validation["tax_sum_matches_total"] = computed_total == total or is_tax_free
        if computed_total != total and not is_tax_free:
            errors.append(
                "tax.rate_10.base + tax.rate_10.amount + tax.rate_8.base + "
                f"tax.rate_8.amount != total ({computed_total} != {total})"
            )
            if data.get("status") != "failed":
                data["status"] = "partial"

    registration_number = _get_nested(data, "document.partner_registration_number")
    if registration_number in (None, ""):
        validation["registration_number_checkdigit"] = "absent"
    elif _is_valid_registration_number(str(registration_number)):
        validation["registration_number_checkdigit"] = "valid"
    else:
        validation["registration_number_checkdigit"] = "invalid"
        logger.warning("partner_registration_number checkdigit failed: %s", registration_number)

    return data.get("status") != "failed", errors


def inject_defaults(data: dict) -> dict:
    if not isinstance(data, dict):
        data = {}

    if not data.get("schema_version"):
        data["schema_version"] = "1.0.0"

    source = data.get("source")
    if not isinstance(source, dict):
        source = {}
        data["source"] = source

    if not source.get("ocr_engine"):
        source["ocr_engine"] = "google_vision"

    return data


def _extract_json_text(llm_text: str) -> str:
    if not isinstance(llm_text, str):
        raise TypeError("llm_text must be a string")

    match = _CODE_BLOCK_RE.search(llm_text)
    text = match.group(1).strip() if match else llm_text.strip()

    if text.startswith("{") and text.endswith("}"):
        return text

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and start < end:
        return text[start : end + 1]

    return text


def _ensure_validation(data: dict) -> dict:
    document = data.get("document")
    if not isinstance(document, dict):
        document = {}
        data["document"] = document

    validation = document.get("validation")
    if not isinstance(validation, dict):
        validation = {}
        document["validation"] = validation

    return validation


def _set_errors(data: dict, errors: list[str]) -> None:
    meta = data.get("_meta")
    if not isinstance(meta, dict):
        meta = {}
        data["_meta"] = meta
    meta["errors"] = errors


def _get_nested(data: dict, path: str):
    current = data
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _to_int(value, *, default=None):
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").strip()
        if cleaned == "":
            return default
        try:
            return int(cleaned)
        except ValueError:
            return default
    return default


def _is_valid_registration_number(value: str) -> bool:
    if not _REGISTRATION_NUMBER_RE.fullmatch(value):
        return False

    # 法人番号（T+13桁）: 先頭1桁がチェックデジット、残り12桁で計算
    # 奇数位置ウェイト2、偶数位置ウェイト1（右から数える）、モジュラス9
    digits = value[1:]
    check_digit = int(digits[0])
    company_number = digits[1:]

    total = 0
    for index, digit in enumerate(reversed(company_number)):
        weight = 2 if (index + 1) % 2 == 1 else 1
        total += int(digit) * weight

    remainder = total % 9
    expected = 0 if remainder == 0 else 9 - remainder
    return check_digit == expected
