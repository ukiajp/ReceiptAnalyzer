from pathlib import Path

from config import Config


def test_validate_requires_folder_paths(monkeypatch):
    monkeypatch.setattr(Config, "GOOGLE_APPLICATION_CREDENTIALS", "creds.json")
    monkeypatch.setattr(Config, "LLM_ENGINE", "claude")
    monkeypatch.setattr(Config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(Config, "OUTPUT_MODE", "csv")
    monkeypatch.setattr(Config, "INBOX_FOLDER_PATH", "")
    monkeypatch.setattr(Config, "PROCESSED_FOLDER_PATH", "")
    monkeypatch.setattr(Config, "ERROR_FOLDER_PATH", "")

    errors = Config.validate()

    assert "INBOX_FOLDER_PATH is not set" in errors
    assert "PROCESSED_FOLDER_PATH is not set" in errors
    assert "ERROR_FOLDER_PATH is not set" in errors


def test_validate_requires_gemini_key(monkeypatch):
    monkeypatch.setattr(Config, "GOOGLE_APPLICATION_CREDENTIALS", "creds.json")
    monkeypatch.setattr(Config, "LLM_ENGINE", "gemini")
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(Config, "OUTPUT_MODE", "csv")
    monkeypatch.setattr(Config, "INBOX_FOLDER_PATH", "inbox")
    monkeypatch.setattr(Config, "PROCESSED_FOLDER_PATH", "processed")
    monkeypatch.setattr(Config, "ERROR_FOLDER_PATH", "error")

    errors = Config.validate()

    assert "GEMINI_API_KEY is required when LLM_ENGINE=gemini" in errors


def test_ensure_directories_creates_log_dir(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(Config, "LOG_DIR", log_dir)

    Config.ensure_directories()

    assert Config.LOG_DIR == log_dir
    assert isinstance(Config.LOG_DIR, Path)
    assert log_dir.exists()
    assert log_dir.is_dir()
