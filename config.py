"""
設定管理モジュール
環境変数とデフォルト値の管理
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()


class Config:
    """アプリケーション設定"""
    
    # Google Cloud認証情報
    GOOGLE_CREDENTIALS_PATH: str = os.getenv(
        "GOOGLE_CREDENTIALS_PATH", 
        "google-credentials.json"
    )
    
    # Ollama設定
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    DEFAULT_LLM_MODEL: str = os.getenv("DEFAULT_LLM_MODEL", "llama3.2:3b")
    
    # ディレクトリ設定
    DATASET_DIR: Path = Path(os.getenv("DATASET_DIR", "dataset"))
    TEST_IMAGES_DIR: Path = DATASET_DIR / "test_images"
    TEST_GROUND_TRUTH_DIR: Path = DATASET_DIR / "test_ground_truth"
    
    # 処理設定
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    TIMEOUT_SECONDS: int = int(os.getenv("TIMEOUT_SECONDS", "60"))
    
    # ログ設定
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR: Path = Path(os.getenv("LOG_DIR", "logs"))
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE", "receipt_analyzer.log")
    
    # 出力設定
    OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", "output"))
    SAVE_RAW_OUTPUT: bool = os.getenv("SAVE_RAW_OUTPUT", "true").lower() == "true"
    
    @classmethod
    def validate(cls, check_images_dir: bool = True) -> list[str]:
        """
        設定の妥当性を検証
        
        Args:
            check_images_dir: テスト画像ディレクトリの存在チェックを行うか
        
        Returns:
            エラーメッセージのリスト
        """
        errors = []
        
        if not Path(cls.GOOGLE_CREDENTIALS_PATH).exists():
            errors.append(f"Google認証情報が見つかりません: {cls.GOOGLE_CREDENTIALS_PATH}")
        
        if check_images_dir and not cls.TEST_IMAGES_DIR.exists():
            errors.append(f"テスト画像ディレクトリが見つかりません: {cls.TEST_IMAGES_DIR}")
        
        return errors
    
    @classmethod
    def ensure_directories(cls):
        """必要なディレクトリを作成"""
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.TEST_GROUND_TRUTH_DIR.mkdir(parents=True, exist_ok=True)
