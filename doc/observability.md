# Observability設計

> 「計測できないものは改善できない」。何をログ・メトリクスとして残すかを実装前に決める。
> 依存: `sdd.md` / `edd.md` / 確定日: 2026-06-21

---

## 1. ログ設計（1ファイル1レコード）

処理ごとに以下を `logs/YYYYMMDD.jsonl` に追記する（JSONL形式）。

```jsonc
{
  "ts": "2026-06-21T09:32:11+09:00",  // 処理開始時刻
  "file": "レシート.jpg",              // 元ファイル名
  "person": "鵜飼",                    // 人名フォルダ
  "status": "success",                // success | ocr_failed | llm_failed | validation_failed | mf_api_failed
  "renamed_to": "20260521_セブンイレブン.jpg",
  "journal_id": "abc-123",            // MF登録後のID（失敗時はnull）
  "vendor": "セブンイレブン○○店",
  "total": 1540,
  "account_title": "消耗品費",
  "account_source": "csv_history",
  "timings": {
    "ocr_sec": 0.72,
    "llm_sec": 4.31,
    "mf_api_sec": 1.18,
    "total_sec": 6.21
  },
  "error": null                        // エラー時はメッセージ
}
```

---

## 2. 標準出力（人が見るログ）

```
[2026-06-21 09:32:05] 処理開始: 受信トレイ/鵜飼/ (3ファイル)
[2026-06-21 09:32:06]   ✓ 20260521_セブンイレブン.jpg → 仕訳登録完了 (journal_id: abc-123) [6.2秒]
[2026-06-21 09:32:13]   ✓ 20260519_出光.jpg         → 仕訳登録完了 (journal_id: def-456) [5.8秒]
[2026-06-21 09:32:15]   ✗ receipt_blur.jpg          → OCR失敗 → エラーフォルダへ移動
[2026-06-21 09:32:15] 完了: 成功 2件 / エラー 1件 / 合計 8.7秒
```

---

## 3. 計測するメトリクス（EDD評価に使う）

| メトリクス | 収集方法 | 用途 |
|---|---|---|
| 処理時間（OCR/LLM/MF API/合計） | JSONLログ | NFR目標（2-8秒）の達成確認 |
| エラー率・エラー分類 | JSONLログ集計 | 失敗パターンの特定 |
| 一発合格率 | evalハーネス実行 | 北極星指標の計測 |
| フィールド別精度 | evalハーネス実行 | EDD基準との照合 |
| MF API呼び出し回数 | JSONLログ集計 | レート制限・コスト管理 |

---

## 4. ログファイル管理

- 保存先: `logs/YYYYMMDD.jsonl`（日次ローテーション）
- 保持期間: v1では自動削除しない（手動管理）
- `google-credentials.json` / `.env` はログに含めない
- ログ自体は機密情報（vendor名・金額）を含む → `.gitignore` に `logs/` を追加

---

## 5. v1 では実装しないもの

- リアルタイムダッシュボード（Streamlit等）→ 将来のPhase 2
- Slack通知 → コネクター設計（将来）
- コスト集計・予算アラート → 将来のObservability拡張

---

*作成: 2026-06-21 / Claude Code Phase 0 / sdd.md・edd.md から派生*
