import base64
import logging

import requests

from config import Config


logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 10
_YEN_SUFFIX = "\u5186"
_ACCOUNT_CASH = "\u73fe\u91d1"
_ACCOUNT_BANK = "\u666e\u901a\u9810\u91d1"
_ACCOUNT_PAYABLE = "\u672a\u6255\u91d1"
_KEYWORD_CASH = "\u73fe\u91d1"
_KEYWORD_BANK_TRANSFER = "\u632f\u8fbc"
_KEYWORD_BANK = "\u9280\u884c"


class MFApiClient:
    def __init__(self):
        self.api_base_url = Config.MF_API_BASE_URL.rstrip("/")
        self.token_url = Config.MF_TOKEN_URL

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {Config.MF_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

    def refresh_token(self) -> None:
        response = requests.post(
            self.token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": Config.MF_REFRESH_TOKEN,
                "client_id": Config.MF_CLIENT_ID,
                "client_secret": Config.MF_CLIENT_SECRET,
            },
            timeout=_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()

        access_token = str(payload.get("access_token", "")).strip()
        if not access_token:
            raise ValueError("MoneyForward token refresh did not return access_token")

        Config.MF_ACCESS_TOKEN = access_token

        refresh_token = str(payload.get("refresh_token", "")).strip()
        if refresh_token:
            Config.MF_REFRESH_TOKEN = refresh_token

        logger.info("Refreshed MoneyForward access token")

    def get_account_items(self) -> list[dict]:
        response = self._request("GET", "/api/v3/account_items")
        response.raise_for_status()

        payload = response.json()
        items = payload.get("account_items", [])
        if not isinstance(items, list):
            raise ValueError("MoneyForward account_items response is invalid")

        return [item for item in items if isinstance(item, dict)]

    def find_account_id(self, account_name: str, account_items: list[dict]) -> tuple[str | None, str | None]:
        normalized_name = str(account_name or "").strip()
        if not normalized_name:
            return None, None

        for item in account_items:
            item_name = str(item.get("name", "")).strip()
            if not item_name:
                continue
            if normalized_name in item_name or item_name in normalized_name:
                account_id = str(item.get("id", "")).strip() or None
                tax_id = str(item.get("tax_id", "")).strip() or None
                return account_id, tax_id

        return None, None

    def register_journal(
        self,
        canonical: dict,
        account_items: list[dict],
        image_bytes: bytes,
        file_name: str,
    ) -> str:
        journal_id = self._post_journal(canonical=canonical, account_items=account_items)
        self._upload_voucher(journal_id=journal_id, image_bytes=image_bytes, file_name=file_name)
        return journal_id

    def _post_journal(self, canonical: dict, account_items: list[dict]) -> str:
        document = canonical.get("document", {}) if isinstance(canonical, dict) else {}
        inferred = document.get("inferred", {}) if isinstance(document, dict) else {}

        transaction_date = str(document.get("date", "")).strip()
        partner_name = str(document.get("partner_name", "")).strip()
        total = int(document.get("total", 0) or 0)
        debit_name = str(inferred.get("account_title", "")).strip()
        credit_name = self._resolve_credit_account_name(str(document.get("payment_method", "")).strip())

        debit_account_id, debit_tax_id = self.find_account_id(debit_name, account_items)
        credit_account_id, credit_tax_id = self.find_account_id(credit_name, account_items)

        branches: list[dict] = []
        skipped_remarks: list[str] = []

        if debit_account_id is None or credit_account_id is None:
            skipped_remarks.append(
                "account_id_not_found"
                f": debit={debit_name or 'unknown'}, credit={credit_name or 'unknown'}"
            )
        else:
            branches.append(
                {
                    "debitor": {
                        "value": total,
                        "account_item_id": debit_account_id,
                        "tax_id": debit_tax_id or "",
                    },
                    "creditor": {
                        "value": total,
                        "account_item_id": credit_account_id,
                        "tax_id": credit_tax_id or "",
                    },
                    "remark": "",
                }
            )

        if not branches:
            message = ", ".join(skipped_remarks) or "No valid journal branches"
            logger.warning("Skipping MoneyForward journal registration: %s", message)
            raise ValueError(message)

        payload = {
            "journal": {
                "transaction_date": transaction_date,
                "journal_type": "journal_entry",
                "memo": f"{partner_name} {total}{_YEN_SUFFIX}".strip(),
                "branches": branches,
            }
        }

        response = self._request("POST", "/api/v3/journals", json=payload)
        response.raise_for_status()

        response_payload = response.json()
        journal = response_payload.get("journal", {})
        journal_id = str(journal.get("id", "")).strip() if isinstance(journal, dict) else ""
        if not journal_id:
            raise ValueError("MoneyForward journal response did not return journal id")

        return journal_id

    def _upload_voucher(self, journal_id: str, image_bytes: bytes, file_name: str) -> None:
        encoded_file = base64.b64encode(image_bytes).decode()
        payload = {
            "journal_id": journal_id,
            "voucher_files": [
                {
                    "file_name": file_name,
                    "file_data": encoded_file,
                }
            ],
        }

        response = self._request("POST", "/api/v3/vouchers", json=payload)
        response.raise_for_status()

    def _request(self, method: str, path: str, json: dict | None = None) -> requests.Response:
        url = f"{self.api_base_url}{path}"

        response = requests.request(
            method=method,
            url=url,
            headers=self._get_headers(),
            json=json,
            timeout=_REQUEST_TIMEOUT,
        )
        if response.status_code != 401:
            return response

        logger.info("MoneyForward API returned 401. Refreshing token and retrying: %s", path)
        self.refresh_token()
        return requests.request(
            method=method,
            url=url,
            headers=self._get_headers(),
            json=json,
            timeout=_REQUEST_TIMEOUT,
        )

    def _resolve_credit_account_name(self, payment_method: str) -> str:
        normalized = payment_method.strip().lower()
        if _KEYWORD_CASH in payment_method or "cash" in normalized:
            return _ACCOUNT_CASH
        if _KEYWORD_BANK_TRANSFER in payment_method or _KEYWORD_BANK in payment_method or "bank" in normalized:
            return _ACCOUNT_BANK
        return _ACCOUNT_PAYABLE
