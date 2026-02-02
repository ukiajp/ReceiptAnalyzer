# レシート自動解析システム (Receipt Analyzer)

Google Vision APIとローカルLLMを組み合わせた、高精度なレシート自動読み取りシステムです。

## 🎯 特徴

- **ハイブリッド構成**: Google Vision API（OCR） + ローカルLLM（構造化）
- **プライバシー重視**: 機密情報はローカルLLMで処理
- **高精度**: 店舗名、日時、商品、金額、消費税を自動抽出
- **バッチ処理対応**: 複数レシートの一括処理
- **JSON出力**: 会計システム連携に最適な構造化データ

## 📋 要件

- Python 3.12以上
- Google Cloud Platform アカウント（Vision API有効化）
- Ollama インストール済み
- llama3.2:3b モデル（または互換モデル）

## 🚀 セットアップ

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd ReceiptAnalyzer
```

### 2. 仮想環境の作成と有効化

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 3. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 4. Google Cloud認証情報の設定

1. [Google Cloud Console](https://console.cloud.google.com/)でプロジェクトを作成
2. Vision APIを有効化
3. サービスアカウントキーをダウンロード
4. `google-credentials.json`としてプロジェクトルートに配置

### 5. Ollamaのセットアップ

```bash
# Ollamaのインストール（未インストールの場合）
# https://ollama.ai/ からダウンロード

# モデルのダウンロード
ollama pull llama3.2:3b
```

### 6. 環境変数の設定（オプション）

`.env`ファイルを作成して設定をカスタマイズ：

```env
GOOGLE_CREDENTIALS_PATH=google-credentials.json
DEFAULT_LLM_MODEL=llama3.2:3b
LOG_LEVEL=INFO
```

## 💻 使用方法

### 基本的な使い方

```bash
# バッチ処理モード（dataset/test_images内の全画像を処理）
python google_vision_hybrid.py

# 単一画像処理
python google_vision_hybrid.py path/to/receipt.jpg
```

### 出力

処理結果は `dataset/test_ground_truth/` にJSON形式で保存されます。

```json
{
  "store": "店舗名",
  "date": "2026-01-20",
  "time": "19:45",
  "total": 2717,
  "tax_10_base": 2470,
  "tax_10_amount": 247,
  "tax_8_base": 0,
  "tax_8_amount": 0,
  "invoice_number": null,
  "payment_method": "クレジット",
  "items": [
    {"name": "商品名", "price": 1000}
  ]
}
```

## 📁 プロジェクト構造

```
ReceiptAnalyzer/
├── google_vision_hybrid.py  # メインスクリプト
├── config.py                # 設定管理
├── utils/
│   └── logger.py           # ログ設定
├── dataset/
│   ├── test_images/        # 入力画像
│   └── test_ground_truth/  # 出力JSON
├── requirements.txt        # 依存関係
└── README.md              # このファイル
```

## 🔧 設定

`config.py`で各種設定を変更できます：

- `DEFAULT_LLM_MODEL`: 使用するLLMモデル
- `LLM_TEMPERATURE`: LLMの温度パラメータ（0.0-1.0）
- `LOG_LEVEL`: ログレベル（DEBUG, INFO, WARNING, ERROR）

環境変数でも設定可能です。

## 🧪 テスト

```bash
# ユニットテスト実行
pytest tests/

# カバレッジ付きテスト
pytest --cov=. tests/
```

## 📊 処理時間の目安

- OCR (Google Vision API): 1-3秒
- 構造化 (llama3.2:3b): 2-5秒
- **合計: 3-8秒/枚**

## 🐛 トラブルシューティング

### Google Vision APIエラー

- 認証情報ファイルが正しいか確認
- Vision APIが有効化されているか確認
- クォータ制限に達していないか確認

### Ollamaエラー

- Ollamaが起動しているか確認: `ollama list`
- モデルがダウンロード済みか確認: `ollama list`
- モデル名が正しいか確認（`config.py`の`DEFAULT_LLM_MODEL`）

### JSON解析エラー

- `llm_raw_output.txt`を確認してLLMの生出力を確認
- プロンプトを調整（`google_vision_hybrid.py`の`structure_with_local_llm`関数）

## 📝 ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 🤝 貢献

プルリクエストを歓迎します！大きな変更の場合は、まずIssueで議論してください。

## 📚 関連ドキュメント

- [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) - プロジェクトの詳細な開発記録
- [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md) - 開発ログ

## 🎓 技術スタック

- **OCR**: Google Cloud Vision API
- **LLM**: Ollama (llama3.2:3b)
- **言語**: Python 3.12
- **JSON修復**: json-repair
