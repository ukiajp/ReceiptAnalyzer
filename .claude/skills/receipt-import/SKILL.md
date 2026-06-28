---
name: receipt-import
description: レシート・領収書の写真をMoneyForwardインポート用CSVにする（構成B）。「レシート取り込んで」「領収書をCSVに」「受信トレイ処理して」等で起動。Claude Codeが00_受信トレイの画像をRead(Vision)で読み正本JSON化→build_mf_csv.pyでCSV(cp932/27列)生成。MF登録は人が手動。
---

# receipt-import（構成B：Claude Vision フロント）

> 仕様＝`doc/sdd.md` 第9章・`doc/interface.md`・`doc/csv_mapping.md`・`doc/account_distillation.md`。
> Visionエンジン＝Claude Code（このスキルを実行する私）。勘定科目は蒸留表で確定スクリプトが付与。

## いつ使うか

UKIAがスマホ撮影したレシートを `00_受信トレイ/{人名}/` に保存した後、Claude Code でこのスキルを起動したとき。

## 前提

- カレント＝このプロジェクト（`scan-to-journalscan-to-journal`）。
- 受信トレイ等は `.env`/config のパス（既定 `G:\…\レシート・領収書画像\00_受信トレイ` ほか）。
- 蒸留表：`99_勘定科目参照/勘定科目参照表_v1.md`。

## 手順（私が実行する）

1. `00_受信トレイ/` 配下（再帰）の画像を列挙（desktop.ini等は除外）。0枚なら報告して終了。
2. 各画像を **Read（Vision）で読取**し、正本JSON v1.0.0（`doc/interface.md`）を生成：
   - `partner_name` / `partner_normalized` / `date` / `total` /
     `tax.rate_10` `tax.rate_8`（軽減税率は分割。単一税率なら片方を0） /
     `partner_registration_number`（T+13桁・無ければnull） / `payment_method` /
     `confidence` / `validation`（tax合算=total）/ `extensions.summary`（用途（店名））
   - `source.ocr_engine="claude_code"`。`inferred.account_title` には**内容から推定した勘定科目**を入れる（例 駐車料金→旅費交通費／飲食→会議費・接待交際費／文具→備品・消耗品費）。`account_source="claude_inference"`。
     ※スクリプトが**蒸留表に店名があればそちらを優先**（履歴整合）、無ければこのClaude推定を採用、どちらも無ければ「仮払金」。
   - 読めない値は**推測補完しない**（`status` を partial/failed にするか該当フィールドを欠落させ、下流でエラー隔離）。
   - 各JSONを `output/json/` に保存。
3. 確定スクリプトを実行（出力先＝Gドライブの回収用フォルダ・蒸留表パスを明示）：
   ```
   .venv/Scripts/python.exe build_mf_csv.py \
     --account-reference-path "G:\マイドライブ\UKIAコンサルティング株式会社\レシート・領収書画像\99_勘定科目参照\勘定科目参照表_v1.md" \
     --output-dir "G:\マイドライブ\UKIAコンサルティング株式会社\レシート・領収書画像\10_MFインポートCSV"
   ```
   → 勘定科目は3段（①蒸留表の店名一致→②Claude推定→③既定「仮払金」＋warning）・税0は「対象外」・検証・8%含む行は除外・`10_MFインポートCSV\mf_import_<JST>.csv`（cp932・27列）生成。
   - 恒久設定したい場合は `.env` に `CSV_OUTPUT_DIR` / `ACCOUNT_REFERENCE_PATH` を書けば `--` 引数は省略可。
4. 結果を報告：処理件数・成功/エラー・warnings（勘定科目低確信/未解決・複数税率混在）・生成CSVパス。
5. **画像の移動**（成功→`01_処理済み/`、エラー→`02_エラー/`）は、CSV生成成功を確認してから行う。

## Human Gate（人の確認）

- 生成CSVを**人がMoneyForwardへ手動インポート**（Phase1。自動登録はしない）。
- `勘定科目未解決(既定科目)`/`勘定科目低確信`/`複数税率混在` のwarningが付いた行は、人がMFで確認・修正（可逆）。

## 禁止事項

- 既存の処理済み画像・蒸留表を上書きしない。
- 読めない値を推測補完しない。
- MFへの登録（API送信）はしない（Phase1）。

## 失敗時

- 読めない箇所を明示し推測で埋めない／当該画像は `02_エラー/` へ／他は継続。
- 蒸留表が見つからない・CSV書込失敗は中断して報告（中途半端なCSVを残さない）。
