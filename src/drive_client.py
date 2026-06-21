import io
import logging
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import Resource, build
from googleapiclient.http import MediaIoBaseDownload

from config import Config


logger = logging.getLogger(__name__)

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


class DriveClient:
    def __init__(self) -> None:
        credentials_path = Config.GOOGLE_APPLICATION_CREDENTIALS.strip()
        if not credentials_path:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS is not set")

        credential_file = Path(credentials_path)
        if not credential_file.is_file():
            raise FileNotFoundError(
                f"GOOGLE_APPLICATION_CREDENTIALS file not found: {credential_file}"
            )

        creds = Credentials.from_service_account_file(
            str(credential_file),
            scopes=[DRIVE_SCOPE],
        )
        self._drive: Resource = build("drive", "v3", credentials=creds)

    def list_person_folders(self, inbox_folder_id: str) -> list[dict[str, str]]:
        query = (
            f"'{self._escape_query_value(inbox_folder_id)}' in parents "
            f"and mimeType = '{FOLDER_MIME_TYPE}' "
            "and trashed = false"
        )
        folders = self._list_files_by_query(
            query=query,
            fields="id, name",
            order_by="name_natural",
        )
        logger.info("Listed %d person folders under %s", len(folders), inbox_folder_id)
        return folders

    def list_files(self, folder_id: str) -> list[dict[str, str]]:
        query = (
            f"'{self._escape_query_value(folder_id)}' in parents "
            f"and mimeType != '{FOLDER_MIME_TYPE}' "
            "and trashed = false"
        )
        files = self._list_files_by_query(
            query=query,
            fields="id, name, mimeType",
            order_by="name_natural",
        )
        logger.info("Listed %d files under %s", len(files), folder_id)
        return files

    def download_file(self, file_id: str) -> bytes:
        request = self._drive.files().get_media(fileId=file_id, supportsAllDrives=True)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False

        while not done:
            _, done = downloader.next_chunk()

        content = buffer.getvalue()
        logger.info("Downloaded file %s (%d bytes)", file_id, len(content))
        return content

    def move_file(self, file_id: str, dest_folder_id: str, current_folder_id: str) -> None:
        self._drive.files().update(
            fileId=file_id,
            addParents=dest_folder_id,
            removeParents=current_folder_id,
            supportsAllDrives=True,
        ).execute()
        logger.info(
            "Moved file %s from %s to %s",
            file_id,
            current_folder_id,
            dest_folder_id,
        )

    def rename_file(self, file_id: str, new_name: str) -> None:
        self._drive.files().update(
            fileId=file_id,
            body={"name": new_name},
            supportsAllDrives=True,
        ).execute()
        logger.info("Renamed file %s to %s", file_id, new_name)

    def get_or_create_subfolder(self, parent_folder_id: str, folder_name: str) -> str:
        query = (
            f"'{self._escape_query_value(parent_folder_id)}' in parents "
            f"and name = '{self._escape_query_value(folder_name)}' "
            f"and mimeType = '{FOLDER_MIME_TYPE}' "
            "and trashed = false"
        )
        folders = self._list_files_by_query(
            query=query,
            fields="id",
            order_by="name_natural",
        )
        if folders:
            folder_id = folders[0]["id"]
            logger.info("Found subfolder %s (%s)", folder_name, folder_id)
            return folder_id

        response = self._drive.files().create(
            body={
                "name": folder_name,
                "mimeType": FOLDER_MIME_TYPE,
                "parents": [parent_folder_id],
            },
            fields="id",
            supportsAllDrives=True,
        ).execute()
        folder_id = response["id"]
        logger.info("Created subfolder %s (%s)", folder_name, folder_id)
        return folder_id

    def _list_files_by_query(
        self,
        query: str,
        fields: str,
        order_by: str,
    ) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        page_token: str | None = None

        while True:
            response = self._drive.files().list(
                q=query,
                fields=f"nextPageToken, files({fields})",
                orderBy=order_by,
                pageSize=1000,
                pageToken=page_token,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
            ).execute()
            items.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if page_token is None:
                break

        return items

    @staticmethod
    def _escape_query_value(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")
