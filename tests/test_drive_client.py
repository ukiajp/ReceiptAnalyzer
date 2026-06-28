from pathlib import Path

import pytest

from config import Config
from src.drive_client import DriveClient


def test_init_requires_existing_inbox_directory(monkeypatch, tmp_path):
    missing_dir = tmp_path / "missing"
    monkeypatch.setattr(Config, "INBOX_FOLDER_PATH", str(missing_dir))

    with pytest.raises(ValueError, match="INBOX_FOLDER_PATH is not a directory"):
        DriveClient()


def test_local_file_operations(monkeypatch, tmp_path):
    inbox_dir = tmp_path / "inbox"
    processed_dir = tmp_path / "processed"
    person_dir = inbox_dir / "alice"
    nested_dir = person_dir / "nested"
    source_file = person_dir / "receipt.jpg"

    nested_dir.mkdir(parents=True)
    processed_dir.mkdir()
    source_file.write_bytes(b"image-bytes")

    monkeypatch.setattr(Config, "INBOX_FOLDER_PATH", str(inbox_dir))
    client = DriveClient()

    person_folders = client.list_person_folders(str(inbox_dir))
    assert person_folders == [{"id": str(person_dir), "name": "alice"}]

    files = client.list_files(str(person_dir))
    assert files == [{"id": str(source_file), "name": "receipt.jpg"}]

    assert client.download_file(str(source_file)) == b"image-bytes"

    renamed_path = client.rename_file(str(source_file), "20260625_vendor.jpg")
    renamed_file = Path(renamed_path)
    assert renamed_file.exists()
    assert renamed_file.name == "20260625_vendor.jpg"

    processed_person_dir = Path(client.get_or_create_subfolder(str(processed_dir), "alice"))
    assert processed_person_dir == processed_dir / "alice"
    assert processed_person_dir.exists()
    assert processed_person_dir.is_dir()

    client.move_file(renamed_path, str(processed_person_dir), str(person_dir))
    moved_file = processed_person_dir / renamed_file.name
    assert moved_file.exists()
    assert not renamed_file.exists()
