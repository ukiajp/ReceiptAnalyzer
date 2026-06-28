from src.schema_builder import build_from_llm_output, inject_defaults, validate


def test_build_from_llm_output_strips_markdown_and_injects_defaults():
    llm_text = """
```json
{
  "status": "success",
  "document": {
    "document_type": "receipt",
    "partner_name": "Test Store",
    "date": "2026-06-21",
    "total": 1098,
    "tax": {
      "rate_10": {"base": 900, "amount": 90},
      "rate_8": {"base": 100, "amount": 8}
    }
  }
}
```
"""

    result = build_from_llm_output(llm_text)

    assert result["schema_version"] == "1.0.0"
    assert result["source"]["ocr_engine"] == "google_vision"
    assert result["status"] == "success"
    assert result["document"]["validation"]["tax_sum_matches_total"] is True
    assert result["document"]["validation"]["registration_number_checkdigit"] == "absent"


def test_build_from_llm_output_sets_failed_when_required_field_is_missing():
    llm_text = """
    {
      "status": "success",
      "document": {
        "document_type": "receipt",
        "partner_name": "Test Store",
        "date": "2026-06-21",
        "tax": {}
      }
    }
    """

    result = build_from_llm_output(llm_text)

    assert result["status"] == "failed"
    assert "Missing required field: document.total" in result["_meta"]["errors"]


def test_validate_sets_partial_on_tax_mismatch():
    data = {
        "schema_version": "1.0.0",
        "status": "success",
        "document": {
            "document_type": "receipt",
            "partner_name": "Test Store",
            "date": "2026-06-21",
            "total": 1000,
            "tax": {
                "rate_10": {"base": 900, "amount": 90},
                "rate_8": {"base": 0, "amount": 0},
            },
        },
    }

    ok, errors = validate(data)

    assert ok is True
    assert data["status"] == "partial"
    assert errors
    assert data["document"]["validation"]["tax_sum_matches_total"] is False


def test_validate_returns_false_when_status_is_failed():
    data = {"status": "failed"}

    ok, errors = validate(data)

    assert ok is False
    assert errors == ["status is failed"]


def test_inject_defaults_sets_schema_version_and_ocr_engine():
    data = inject_defaults({})

    assert data["schema_version"] == "1.0.0"
    assert data["source"]["ocr_engine"] == "google_vision"
