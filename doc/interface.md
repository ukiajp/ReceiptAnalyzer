# 正本中間JSONスキーマ（Canonical Intermediate Schema）— I/F

> これが扇の要（ピボット）。OCRより上流はこれを**作り**、着地（API/CSV/Excel/画像添付）はこれを**参照する**。
> ここが歪むと全アダプタが歪む。schema_version 1.0.0 / 確定日 2026-06-21

---

## 設計原則

| 原則 | 内容 |
|------|------|
| 唯一の正本 | 上流＝生成、下流＝参照。全枝葉がこの契約に依存する |
| 証憑種別の分離 | `document_type` で `receipt`／`invoice` を判別。共通ベース＋種別固有 |
| バージョニング | semver。**項目追加＝minor（後方互換）／削除・意味変更＝major** |
| 拡張フィールド | 未知キーは捨てず保持（forward互換）。企業固有項目は `extensions{}` に隔離 |
| 移植性 | キーは英語（Python↔Rust移行のため）。意味は日本語でドキュメント |

---

## スキーマ v1.0

```jsonc
{
  "schema_version": "1.0.0",
  "status": "success",                       // success | partial | failed
  "document": {
    "document_type": "receipt",              // receipt | invoice  ★必須

    // ── 共通ベース ──
    "partner_name": "セブンイレブン○○店",   // 取引先/店舗  ★必須（旧 store/store_name を一本化）
    "partner_registration_number": null,     // 適格請求書番号 T+13桁・任意（チェックデジット検証対象）
    "date": "2026-03-22",                    // 取引日/発行日  ★必須
    "total": 1080,                           // 合計  ★必須・致命
    "tax": {                                 // 軽減税率対応・分割  ★必須・致命
      "rate_10": { "base": 900, "amount": 90 },
      "rate_8":  { "base": 100, "amount": 8 }
    },
    "payment_method": "現金",                // 任意

    // ── invoice のときのみ ──
    "invoice_fields": {
      "due_date": null,                      // 支払期日
      "bank_transfer": null,                 // 振込先
      "invoice_number": null
    },

    // ── 幹：履歴参照で推定した"提案"（最終確定は人） ──
    "inferred": {
      "account_title": "消耗品費",           // 勘定科目(提案)
      "account_source": "csv_history",        // csv_history=過去仕訳CSV参照 | mf_api=MF API履歴参照 | rule=ルールベース | default=デフォルト
      "partner_normalized": "セブンイレブン" // 名寄せ後（一発合格率を上げる）
    },

    // ── 人確認UI用：弱い箇所を一目で ──
    "confidence": { "total": 0.99, "date": 0.95, "partner_name": 0.86 },

    // ── 自己検証 ──
    "validation": {
      "registration_number_checkdigit": "absent", // valid | invalid | absent
      "tax_sum_matches_total": true
    },

    "line_items": [],                        // 明細・任意
    "extensions": {}                         // 企業固有項目の隔離先
  },
  "source": {
    "image_ref": null,                       // 証憑画像への参照（層B添付用・任意）
    "ocr_engine": "google_vision"
  },
  "_meta": { "timings": { "ocr": 0.7, "llm": 7.0 } }
}
```

---

## 必須 / 致命の区分

- **必須**：`schema_version`, `status`, `document.document_type`, `partner_name`, `date`, `total`, `tax`
- **致命（99%級・誤りは限りなくゼロ）**：`total`, `tax`
- それ以外（invoice_fields・inferred・confidence・line_items・extensions）は**任意**。v1 はこの最小核で動く。

---

## validation ルール（EDD / 幹で自己検証）

1. `rate_10.base + rate_10.amount + rate_8.base + rate_8.amount == total`（税合算＝合計の整合）
2. `partner_registration_number` があれば T＋13桁チェックデジット検証 → `valid|invalid|absent`
3. `status == failed` のとき `document` は信頼しない（着地に渡さない）

---

## 既存コードからの移行（契約破損の解消）

| 現状（破損） | 統一後 |
|------|--------|
| `store`（hybrid）/ `store_name`（converter） | `document.partner_name` |
| 封筒 `{data,...}`（hybrid）/ `{success, parsed_data}`（converter） | `{schema_version, status, document, source, _meta}` |
| `tax`（単一・converter） | `tax.rate_10 / rate_8`（分割）。converter を分割対応に修正 |

> 移行実装は spec ではなくコード変更のため、3engine-impl フロー（Codex実装→agyレビュー→統合）で行う。
