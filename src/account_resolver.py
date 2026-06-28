import csv
import logging
import unicodedata
from pathlib import Path

import requests

from config import Config


logger = logging.getLogger(__name__)

_CSV_ENCODINGS = ("utf-8-sig", "shift-jis")
_CSV_ROW_LIMIT = 50
_TARGET_COLUMNS = ("取引先", "勘定科目", "税区分")


def load_past_journals(csv_path: str) -> str:
    path = Path(csv_path or Config.PAST_JOURNALS_CSV)

    if not path.is_file():
        logger.warning("Past journals CSV not found: %s", path)
        return "過去仕訳データ:\nなし"

    rows: list[list[str]] | None = None
    last_error: UnicodeDecodeError | None = None

    for encoding in _CSV_ENCODINGS:
        try:
            with path.open("r", encoding=encoding, newline="") as file:
                reader = csv.reader(file)
                rows = []
                for index, row in enumerate(reader):
                    if index > _CSV_ROW_LIMIT:
                        break
                    rows.append([cell.strip() for cell in row])
            logger.info("Loaded past journals CSV with encoding=%s: %s", encoding, path)
            break
        except UnicodeDecodeError as exc:
            last_error = exc

    if rows is None:
        logger.warning("Failed to decode past journals CSV: %s", path, exc_info=last_error)
        return "過去仕訳データ:\nなし"

    if not rows:
        return "過去仕訳データ:\nなし"

    header = rows[0]
    data_rows = rows[1:]
    columns = [column for column in _TARGET_COLUMNS if column in header]

    if columns:
        indices = [header.index(column) for column in columns]
    else:
        indices = list(range(min(3, len(header))))
        columns = [header[index] or f"列{index + 1}" for index in indices]

    lines = [", ".join(columns)]
    for row in data_rows[:_CSV_ROW_LIMIT]:
        if not any(cell.strip() for cell in row):
            continue
        values = [row[index] if index < len(row) else "" for index in indices]
        lines.append(", ".join(values))

    if len(lines) == 1:
        lines.append("なし")

    return "過去仕訳データ:\n" + "\n".join(lines)


def load_distill_table(path: str | Path) -> list[dict[str, str]]:
    table_path = Path(path)
    if not table_path.is_file():
        logger.warning("Distill table not found: %s", table_path)
        return []

    rules: list[dict[str, str]] = []
    with table_path.open("r", encoding="utf-8-sig") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line.startswith("|"):
                continue

            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) < 3:
                continue
            if cells[0] == "店名キー":
                continue
            if all(set(cell) <= {"-", ":"} for cell in cells[:3]):
                continue

            key = cells[0]
            account_title = cells[1]
            confidence = cells[2] or "低"
            if not key or not account_title:
                continue

            normalized_key = _normalize_vendor(key)
            if not normalized_key:
                continue

            rules.append(
                {
                    "key": key,
                    "normalized_key": normalized_key,
                    "account_title": account_title,
                    "confidence": confidence,
                }
            )

    logger.info("Loaded %d distill-table rules: %s", len(rules), table_path)
    return rules


def resolve_account(vendor: str, rules: list[dict[str, str]]) -> tuple[str, str]:
    normalized_vendor = _normalize_vendor(vendor)
    if not normalized_vendor:
        return "", "低"

    exact_matches = [
        rule for rule in rules if rule.get("normalized_key", "") == normalized_vendor
    ]
    if exact_matches:
        selected = _select_best_rule(exact_matches)
        return selected["account_title"], selected["confidence"]

    partial_matches = [
        rule
        for rule in rules
        if rule.get("normalized_key") and rule["normalized_key"] in normalized_vendor
    ]
    if partial_matches:
        selected = _select_best_rule(partial_matches)
        return selected["account_title"], selected["confidence"]

    return "", "低"


def get_mf_account_master(access_token: str, base_url: str) -> list[dict]:
    token = access_token.strip()
    if not token:
        logger.warning("MF access token is empty")
        return []

    resolved_base_url = (base_url or Config.MF_API_BASE_URL).rstrip("/")
    url = f"{resolved_base_url}/api/v3/account_items"

    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Failed to fetch MF account master from %s: %s", url, exc)
        return []

    items = _extract_account_items(payload)
    accounts: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        short_name = str(item.get("short_name", "")).strip() or name
        accounts.append(
            {
                "id": str(item.get("id", "")).strip(),
                "name": name,
                "short_name": short_name,
            }
        )

    logger.info("Fetched %d MF account items", len(accounts))
    return accounts


def build_context(past_journals_text: str, mf_accounts: list[dict]) -> str:
    journals_text = past_journals_text.strip() or "過去仕訳データ:\nなし"
    account_names: list[str] = []
    seen: set[str] = set()

    for account in mf_accounts:
        if not isinstance(account, dict):
            continue
        name = str(account.get("short_name") or account.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        account_names.append(name)

    accounts_text = ", ".join(account_names) if account_names else "なし"
    return (
        f"【過去の仕訳文脈】\n{journals_text}\n\n"
        f"【使用可能な勘定科目】\n{accounts_text}"
    )


def _normalize_vendor(value: object) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    return "".join(text.split())


def _select_best_rule(rules: list[dict[str, str]]) -> dict[str, str]:
    return max(
        rules,
        key=lambda rule: (
            len(rule.get("normalized_key", "")),
            len(rule.get("key", "")),
        ),
    )


def _extract_account_items(payload: object) -> list[object]:
    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        return []

    for key in ("account_items", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return value

    return []
