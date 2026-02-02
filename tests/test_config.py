"""
設定モジュールのテスト
"""

import pytest
from pathlib import Path
from config import Config


def test_config_defaults():
    """デフォルト設定の確認"""
    assert Config.DEFAULT_LLM_MODEL == "llama3.2:3b"
    assert Config.LLM_TEMPERATURE == 0.1
    assert isinstance(Config.DATASET_DIR, Path)


def test_config_directories():
    """ディレクトリ設定の確認"""
    assert Config.TEST_IMAGES_DIR == Config.DATASET_DIR / "test_images"
    assert Config.TEST_GROUND_TRUTH_DIR == Config.DATASET_DIR / "test_ground_truth"


def test_ensure_directories():
    """ディレクトリ作成の確認"""
    Config.ensure_directories()
    assert Config.LOG_DIR.exists()
    assert Config.OUTPUT_DIR.exists()
    assert Config.TEST_GROUND_TRUTH_DIR.exists()
