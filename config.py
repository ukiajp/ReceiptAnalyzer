import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Config:
    PROJECT_ROOT: Path = Path(__file__).resolve().parent
    LLM_ENGINE: str = os.getenv("LLM_ENGINE", "claude")
    OUTPUT_MODE: str = os.getenv("OUTPUT_MODE", "mf_api")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    MF_CLIENT_ID: str = os.getenv("MF_CLIENT_ID", "")
    MF_CLIENT_SECRET: str = os.getenv("MF_CLIENT_SECRET", "")
    MF_ACCESS_TOKEN: str = os.getenv("MF_ACCESS_TOKEN", "")
    MF_REFRESH_TOKEN: str = os.getenv("MF_REFRESH_TOKEN", "")
    INBOX_FOLDER_PATH: str = os.getenv("INBOX_FOLDER_PATH", "")
    PROCESSED_FOLDER_PATH: str = os.getenv("PROCESSED_FOLDER_PATH", "")
    ERROR_FOLDER_PATH: str = os.getenv("ERROR_FOLDER_PATH", "")
    PAST_JOURNALS_CSV: str = os.getenv("PAST_JOURNALS_CSV", "./data/past_journals.csv")
    JSON_OUTPUT_DIR: str = os.getenv("JSON_OUTPUT_DIR", str((PROJECT_ROOT / "output" / "json").resolve()))
    CSV_OUTPUT_DIR: str = os.getenv("CSV_OUTPUT_DIR", str((PROJECT_ROOT / "output" / "csv").resolve()))
    DEFAULT_ACCOUNT_TITLE: str = os.getenv("DEFAULT_ACCOUNT_TITLE", "仮払金")
    ACCOUNT_REFERENCE_PATH: str = os.getenv(
        "ACCOUNT_REFERENCE_PATH",
        str((PROJECT_ROOT / "99_勘定科目参照" / "勘定科目参照表_v1.md").resolve()),
    )
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    MF_API_BASE_URL: str = os.getenv("MF_API_BASE_URL", "https://api.biz.moneyforward.com")
    MF_TOKEN_URL: str = os.getenv("MF_TOKEN_URL", "https://accounts.moneyforward.com/oauth/token")

    LOG_DIR: Path = Path("logs")

    @classmethod
    def validate(cls) -> list[str]:
        errors: list[str] = []

        if not cls.GOOGLE_APPLICATION_CREDENTIALS:
            errors.append("GOOGLE_APPLICATION_CREDENTIALS is not set")

        if cls.LLM_ENGINE == "claude" and not cls.ANTHROPIC_API_KEY:
            errors.append("ANTHROPIC_API_KEY is required when LLM_ENGINE=claude")

        if cls.LLM_ENGINE == "openai" and not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY is required when LLM_ENGINE=openai")

        if cls.LLM_ENGINE == "gemini" and not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is required when LLM_ENGINE=gemini")

        if not cls.INBOX_FOLDER_PATH:
            errors.append("INBOX_FOLDER_PATH is not set")
        elif not Path(cls.INBOX_FOLDER_PATH).is_dir():
            errors.append(f"INBOX_FOLDER_PATH is not a directory: {cls.INBOX_FOLDER_PATH}")

        if not cls.PROCESSED_FOLDER_PATH:
            errors.append("PROCESSED_FOLDER_PATH is not set")

        if not cls.ERROR_FOLDER_PATH:
            errors.append("ERROR_FOLDER_PATH is not set")

        if cls.OUTPUT_MODE == "mf_api":
            required_values = {
                "MF_ACCESS_TOKEN": cls.MF_ACCESS_TOKEN,
                "MF_REFRESH_TOKEN": cls.MF_REFRESH_TOKEN,
                "MF_CLIENT_ID": cls.MF_CLIENT_ID,
                "MF_CLIENT_SECRET": cls.MF_CLIENT_SECRET,
            }
            for name, value in required_values.items():
                if not value:
                    errors.append(f"{name} is required when OUTPUT_MODE=mf_api")

        return errors

    @classmethod
    def ensure_directories(cls) -> None:
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
        Path(cls.JSON_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
        Path(cls.CSV_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
        if cls.PROCESSED_FOLDER_PATH:
            Path(cls.PROCESSED_FOLDER_PATH).mkdir(parents=True, exist_ok=True)
        if cls.ERROR_FOLDER_PATH:
            Path(cls.ERROR_FOLDER_PATH).mkdir(parents=True, exist_ok=True)
