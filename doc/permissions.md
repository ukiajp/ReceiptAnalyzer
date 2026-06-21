# Permissions設計 + Allowlist設計

> Permissions = そもそも何に触れてよいか（境界線）
> Allowlist   = その境界内で、事前承認なし自動実行してよいもの（高速道路）
> Allowlist は Permissions の部分集合。
> 依存: `sdd.md` / 確定日: 2026-06-21

---

## 1. Permissions（境界線）

### 1-a. ファイルシステム

| パス | 権限 | 理由 |
|---|---|---|
| `./logs/` | 書き込み | 処理ログ出力 |
| `./data/past_journals.csv` | 読み取り | 過去仕訳コンテキスト |
| `./.env` | 読み取り | 設定読み込み |
| `./doc/` | 読み取り | 仕様書参照 |
| その他ローカルパス | **禁止** | 入力はDrive経由のみ |

### 1-b. 外部API

| サービス | 許可スコープ | 禁止 |
|---|---|---|
| Google Vision API | `cloud-vision.googleapis.com` への画像送信 | — |
| Google Drive API | 指定フォルダIDの読み取り・移動・リネーム | Drive全体の権限 |
| LLM API（Claude/OpenAI） | OCRテキストの送信（画像は送らない） | — |
| MF API | `journal.write` + `voucher.write` | `journal.delete` は使用しない（v1） |

### 1-c. ネットワーク

上記4サービス以外への外部通信は禁止。

---

## 2. Allowlist（Claude Code 実行の事前承認リスト）

このプロジェクトフォルダ内で Claude Code が **無確認で実行してよい** コマンド・操作。

### 許可（コマンド）

```
python pipeline.py          # パイプライン実行
python eval/run_eval.py     # 評価ハーネス実行
python -m pytest            # テスト実行
git status / git diff / git log   # 状態確認（読み取り）
git add / git commit        # コミット（pushは含まない）
rg / grep                   # コード検索
```

### 許可（ファイル操作）

```
Read:  プロジェクトフォルダ以下の全ファイル
Write: doc/*.md / tests/*.py / src/*.py（新規・更新）
       logs/*.jsonl（追記）
```

### 要承認（Claude Code は実行前に確認する）

```
git push                    # リモートへの送信
MF APIへの実際のPOST        # 本番への登録（可逆だが確認する）
.env の書き換え             # 認証情報の変更
Drive上のファイル削除       # 不可逆操作
```

### 禁止

```
rm -rf / git reset --hard   # 破壊的操作
--no-verify                 # フック回避
APIキー・トークンのログ出力  # 秘密情報の露出
```

---

## 3. Claude Code settings.json への反映

`/.claude/settings.json`（プロジェクトローカル）に以下を追加する:

```json
{
  "permissions": {
    "allow": [
      "Bash(python pipeline.py)",
      "Bash(python eval/*)",
      "Bash(python -m pytest*)",
      "Bash(git status)",
      "Bash(git diff*)",
      "Bash(git log*)",
      "Bash(git add*)",
      "Bash(git commit*)",
      "Bash(rg*)"
    ],
    "deny": [
      "Bash(git push*)",
      "Bash(rm -rf*)",
      "Bash(git reset --hard*)"
    ]
  }
}
```

---

*作成: 2026-06-21 / Claude Code Phase 0 / sdd.md から派生*
