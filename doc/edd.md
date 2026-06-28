# EDD — 評価駆動開発基準（Evaluation-Driven Development）

> GATEのオラクル判定ロジック。「合格/不合格」を人の主観でなくスコアで決める。
> 依存: `sdd.md` / `nfr.md` / `interface.md` / 確定日: 2026-06-21

---

## 1. 評価対象フィールドと合否しきい値

正本JSONスキーマ（interface.md）の各フィールドを以下の3層で評価する。

| 層 | フィールド | 合格条件 | 目標精度 | 備考 |
|---|---|---|---|---|
| **致命** | `document.total` | 金額が完全一致 | **99%以上** | 1円でも違えば不合格 |
| **致命** | `document.tax.rate_10.amount` + `rate_8.amount` | 税額合算がtotalと整合 | **99%以上** | `validation.tax_sum_matches_total` で自動検証 |
| **重要** | `document.date` | YYYY-MM-DD形式・日付として有効 | **95%以上** | 前後1日のズレは警告（不合格にしない） |
| **重要** | `document.partner_name` | 主要チェーン名レベルで一致（表記揺れ許容） | **90%以上** | 「セブン-イレブン○○店」→「セブンイレブン」でOK |
| **提案** | `document.inferred.account_title` | 過去仕訳と同じ科目が提案される | **90%以上** | 不一致は警告・人が修正 |
| **任意** | `document.partner_registration_number` | T+13桁チェックデジット検証通過 | — | `absent` は合格 |

---

## 2. 一発合格の定義

```
一発合格 = 致命フィールドが全て合格 AND 重要フィールドが許容内
```

- 致命フィールド（total・tax）に1つでも誤りがあれば **不合格**
- 重要フィールドの誤りは **警告**（人が確認・修正すれば合格）
- 提案・任意フィールドの誤りは **情報のみ**

**北極星指標：一発合格率 80%以上**（人が修正なしで確認だけで通る率）

---

## 3. 自動バリデーション（schema_builder.py が担当）

```python
# interface.md の validation ルールを実装する

rule_1: tax.rate_10.base + tax.rate_10.amount
      + tax.rate_8.base  + tax.rate_8.amount == document.total
      → 不整合なら status="partial"・エラーフォルダへ

rule_2: partner_registration_number が存在する場合
      → T + 13桁 + チェックデジット検証
      → 結果を validation.registration_number_checkdigit に記録

rule_3: status == "failed" の場合
      → document フィールドを着地（MF API登録）に渡さない
```

---

## 4. eval ハーネス（50〜100枚での精度計測）

```
dataset/
  eval_images/          ← テスト用レシート画像（本番未使用）
  eval_ground_truth/    ← 期待値JSON（正本スキーマ v1.0.0 準拠）

実行: python eval/run_eval.py
出力:
  - 一発合格率（%）
  - フィールド別精度（%）
  - 処理時間（avg/p95）
  - エラー分類（OCR失敗/LLM失敗/バリデーション失敗）
```

**eval harness は v1 実装後に構築する**（データ収集が先）。
現状の `dataset/test_ground_truth/` は旧スキーマのため、正本スキーマへの移行が必要。

---

## 5. エラー分類

| 分類 | 条件 | 処理 |
|---|---|---|
| `ocr_failed` | Vision APIがテキストを返さない・例外 | エラーフォルダへ |
| `llm_failed` | LLMがJSONを返さない・パース不能 | エラーフォルダへ |
| `validation_failed` | tax整合チェック失敗・必須項目欠損 | エラーフォルダへ |
| `mf_api_failed` | 仕訳登録API失敗（4xx/5xx） | ログ記録・処理済みフォルダには移動済み |
| `voucher_failed` | 証憑アップロード失敗 | ログ記録のみ（仕訳は登録済みのため） |

---

## 6. GATEの運用（v1）

v1 では EDD の自動GATE（CI連携）は構築しない。
人間（UKIA）が以下の軸で最終判断する：

```
確認軸：
  1. 致命フィールドが合格か
  2. 可逆性が担保されているか（MFで削除できるか）
  3. ログにエラーがないか
```

---

## 7. 構成B（Claude Vision）での評価差分 — 2026-06-28

- Visionエンジン＝Claude Code（`source.ocr_engine="claude_code"`）。評価対象フィールド・致命/重要の区分は構成Aと同一。
- 勘定科目（提案）の評価は**蒸留表マッチ**で行う：完全一致/単方向部分一致で解決。未解決は既定科目「仮払金」＋warning `勘定科目未解決(既定科目)`（人が修正＝可逆）。
- **CSV着地の合否（構成B固有・MFインポート通過条件）**：エンコーディング cp932／27列／取引日 YYYY/M/D／税区分が `課税仕入 10%`(空白込み)・`課税仕入 8%`・`対象外` のいずれか／借方金額=貸方金額=total。1つでも不一致なら不合格（MFが弾く）。
- 税0（非課税/対象外）取引：税合算チェックを素通しし税区分「対象外」（過去踏襲）。複数税率混在は方式Bで除外（エラー）。
- エラー分類に追加：`vision_failed`（Claudeが画像を読めない/JSON不正）→ 02_エラーへ。`csv_write_failed`（cp932書込失敗）→ 中断・中途半端CSVを残さない。

---

*作成: 2026-06-21 / Claude Code Phase 0 / sdd.md・nfr.md・interface.md から派生*
*構成B追記: 2026-06-28*
