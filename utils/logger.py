"""
ログ設定モジュール
統一されたログ出力の管理
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from config import Config


def setup_logger(
    name: str = "receipt_analyzer",
    log_level: str = Config.LOG_LEVEL,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    ロガーを設定して返す
    
    Args:
        name: ロガー名
        log_level: ログレベル (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: ログファイル名（Noneの場合はファイル出力なし）
    
    Returns:
        設定済みロガー
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # 既存のハンドラーをクリア（重複防止）
    logger.handlers.clear()
    
    # フォーマッター
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # コンソールハンドラー
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # ファイルハンドラー（指定がある場合）
    if log_file:
        Config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_path = Config.LOG_DIR / log_file
        
        file_handler = logging.FileHandler(file_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger
