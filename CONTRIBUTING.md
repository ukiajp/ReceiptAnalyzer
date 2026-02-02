# コントリビューションガイド

このプロジェクトへの貢献をありがとうございます！以下のガイドラインに従ってください。

## 🚀 開発環境のセットアップ

1. リポジトリをクローン
2. 仮想環境を作成・有効化
3. 依存関係をインストール: `pip install -r requirements.txt`
4. 開発用依存関係をインストール: `pip install -r requirements-dev.txt` (作成予定)

## 📝 コーディング規約

### コードスタイル

- **Black**: コードフォーマッターを使用
- **Ruff**: リンターを使用
- **型ヒント**: 可能な限り型ヒントを追加

```bash
# フォーマット
black .

# リンター
ruff check .
```

### 型チェック

```bash
mypy . --ignore-missing-imports
```

## 🧪 テスト

### テストの実行

```bash
# 全テスト実行
pytest

# カバレッジ付き
pytest --cov=. --cov-report=html

# 特定のテストファイル
pytest tests/test_config.py
```

### テストの書き方

- テストファイルは `tests/` ディレクトリに配置
- ファイル名は `test_*.py` 形式
- 関数名は `test_*` 形式

## 📦 プルリクエスト

1. 新しいブランチを作成: `git checkout -b feature/your-feature-name`
2. 変更をコミット: `git commit -m "Add: 機能説明"`
3. ブランチをプッシュ: `git push origin feature/your-feature-name`
4. プルリクエストを作成

### コミットメッセージ

- `Add:` 新機能追加
- `Fix:` バグ修正
- `Update:` 機能改善
- `Refactor:` リファクタリング
- `Docs:` ドキュメント更新
- `Test:` テスト追加・修正

## 🔍 コードレビュー

- すべてのプルリクエストはレビューが必要です
- レビューコメントには丁寧に対応してください
- 質問があれば遠慮なく聞いてください

## 📚 ドキュメント

- 新しい機能を追加する場合は、README.mdを更新してください
- 複雑なロジックにはコメントを追加してください
- docstringはGoogle形式で記述してください

## 🐛 バグ報告

Issueを作成する際は、以下を含めてください：

- 再現手順
- 期待される動作
- 実際の動作
- 環境情報（OS、Pythonバージョンなど）

## 💡 機能提案

新機能の提案も歓迎します！Issueで議論しましょう。
