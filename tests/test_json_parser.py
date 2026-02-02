"""
JSON解析モジュールのテスト
"""

import pytest
import json
from google_vision_hybrid import parse_json_from_response


def test_parse_json_simple():
    """シンプルなJSONの解析"""
    response = '{"store": "テスト店", "total": 1000}'
    result = parse_json_from_response(response)
    assert result["store"] == "テスト店"
    assert result["total"] == 1000


def test_parse_json_with_markdown():
    """Markdownコードブロック付きJSONの解析"""
    response = '''説明文
```json
{"store": "テスト店", "total": 1000}
```
追加の説明'''
    result = parse_json_from_response(response)
    assert result["store"] == "テスト店"
    assert result["total"] == 1000


def test_parse_json_with_extra_text():
    """前後に余計なテキストがあるJSONの解析"""
    response = 'これは説明です。{"store": "テスト店", "total": 1000} これも説明です。'
    result = parse_json_from_response(response)
    assert result["store"] == "テスト店"
    assert result["total"] == 1000


def test_parse_json_invalid():
    """無効なJSONの処理"""
    response = "これはJSONではありません"
    with pytest.raises(json.JSONDecodeError):
        parse_json_from_response(response)
