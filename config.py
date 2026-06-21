import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Config:
    LLM_ENGINE: str = os.getenv("LLM_ENGINE", "claude")
    OUTPUT_MODE: str = os.getenv("OUTPUT_MODE", "mf_api")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    MF_CLIENT_ID: str = os.getenv("MF_CLIENT_ID", "")
    MF_CLIENT_SECRET: str = os.getenv("MF_CLIENT_SECRET", "")
    MF_ACCESS_TOKEN: str = os.getenv("MF_ACCESS_TOKEN", "")
    MF_REFRESH_TOKEN: str = os.getenv("MF_REFRESH_TOKEN", "")
    GDRIVE_INBOX_FOLDER_ID: str = os.getenv("GDRIVE_INBOX_FOLDER_ID", "")
    GDRIVE_PROCESSED_FOLDER_ID: str = os.getenv("GDRIVE_PROCESSED_FOLDER_ID", "")
    GDRIVE_ERROR_FOLDER_ID: str = os.getenv("GDRIVE_ERROR_FOLDER_ID", "")
    PAST_JOURNALS_CSV: str = os.getenv("PAST_JOURNALS_CSV", "./data/past_journals.csv")
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

        if not cls.GDRIVE_INBOX_FOLDER_ID:
            errors.append("GDRIVE_INBOX_FOLDER_ID is not set")

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
