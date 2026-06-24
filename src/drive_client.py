import logging
import os
from pathlib import Path
import shutil

from config import Config


logger = logging.getLogger(__name__)


class DriveClient:
    def __init__(self) -> None:
        inbox_folder_path = Config.INBOX_FOLDER_PATH.strip()
        if not inbox_folder_path:
            raise ValueError("INBOX_FOLDER_PATH is not set")

        inbox_dir = Path(inbox_folder_path)
        if not inbox_dir.is_dir():
            raise ValueError(f"INBOX_FOLDER_PATH is not a directory: {inbox_dir}")

    def list_person_folders(self, inbox_folder_path: str) -> list[dict[str, str]]:
        inbox_dir = Path(inbox_folder_path)
        folders = [
            {"id": str(path), "name": path.name}
            for path in sorted(inbox_dir.iterdir(), key=lambda item: item.name)
            if path.is_dir()
        ]
        logger.info("Listed %d person folders under %s", len(folders), inbox_folder_path)
        return folders

    def list_files(self, folder_path: str) -> list[dict[str, str]]:
        target_dir = Path(folder_path)
        files = [
            {"id": str(path), "name": path.name}
            for path in sorted(target_dir.iterdir(), key=lambda item: item.name)
            if path.is_file()
        ]
        logger.info("Listed %d files under %s", len(files), folder_path)
        return files

    def download_file(self, file_path: str) -> bytes:
        content = Path(file_path).read_bytes()
        logger.info("Downloaded file %s (%d bytes)", file_path, len(content))
        return content

    def rename_file(self, file_path: str, new_name: str) -> str:
        source_path = Path(file_path)
        renamed_path = source_path.with_name(new_name)
        source_path.rename(renamed_path)
        logger.info("Renamed file %s to %s", file_path, new_name)
        return str(renamed_path)

    def move_file(self, file_path: str, dest_folder_path: str, _current_folder_path: str) -> None:
        dest = Path(dest_folder_path) / Path(file_path).name
        if dest.exists():
            stem = dest.stem
            suffix = dest.suffix
            counter = 1
            while dest.exists():
                dest = dest.parent / f'{stem}_{counter}{suffix}'
                counter += 1
        shutil.move(file_path, os.fspath(dest))
        logger.info(
            "Moved file %s from %s to %s",
            file_path,
            _current_folder_path,
            dest_folder_path,
        )

    def get_or_create_subfolder(self, parent_path: str, folder_name: str) -> str:
        target_dir = Path(parent_path) / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Ensured subfolder %s", target_dir)
        return str(target_dir)
