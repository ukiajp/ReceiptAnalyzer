# SDD — ReceiptAnalyzer v1.0（仕様駆動設計書）

> 唯一の真実源。実装はここを参照し、ここから外れない。
> 依存: `purpose.md`（根）/ `interface.md`（I/F・正本スキーマ）
> 確定日: 2026-06-21

---

## 1. 一文定義

「Googleドライブに投函されたレシート・領収書画像を、OCR → LLM構造化 → MoneyForward仕訳登録まで半自動化するCLIパイプライン。」

---

## 2. アーキテクチャ（4ステージ骨格）

```
①取り込み                    ②変換/生成                    ③人の確認    ④着地
マウント済みフォルダ/      →  Vision OCR                →  [将来拡張]  →  MF API
  受信トレイ/{人名}/           LLM構造化（LLM_ENGINE）                      仕訳登録
  （Gドライブ・BOX等）         正本JSON v1.0.0 生成                         証憑添付
                              ファイルリネーム（yyyymmdd_取引先.ext）
                              処理済み/{人名}/ へ移動
```

---

## 3. モジュール構成と責務

### src/ ディレクトリ構造

```
src/
  pipeline.py           ← オーケストレーター
  drive_client.py       ← Steps 1・4・5
  ocr_engine.py         ← Step 2
  llm_provider.py       ← Step 3（LLM呼び出し）
  account_resolver.py   ← Step 3（コンテキスト生成）
  schema_builder.py     ← Step 3（JSON変換・バリデーション）
  output/               ← 出力アダプタ（枝葉・交換可能）
    mf_api_client.py    ← Steps 6-7（アダプタ A・主系）
    csv_exporter.py     ← Step 6a（アダプタ B・派生）
config.py               ← 環境変数管理（更新）
```

### モジュール責務

| モジュール | 担当ステップ | 責務 | 新規/流用 |
|---|---|---|---|
| `pipeline.py` | 全体 | オーケストレーション・エラー処理 | 新規 |
| `drive_client.py` | 1・4・5 | マウント済みフォルダ一覧・ファイル読込・リネーム・移動（os/pathlib/shutil） | 新規 |
| `ocr_engine.py` | 2 | Google Vision API呼び出し → テキスト返却 | 既存から移植 |
| `llm_provider.py` | 3 | LLM_ENGINEで切り替え（claude / openai / gemini）→ JSON返却 | 新規 |
| `account_resolver.py` | 3 | 過去仕訳CSV + MFマスタ参照 → 勘定科目提案 | 新規 |
| `schema_builder.py` | 3 | LLM出力 → 正本JSON v1.0.0 変換・バリデーション | 新規 |
| `output/mf_api_client.py` | 6-7 | 仕訳登録POST・証憑アップロードPOST・トークンリフレッシュ | 新規 |
| `output/csv_exporter.py` | 6a | 正本JSON → MoneyForward CSVファイル出力 | 新規 |
| `config.py` | — | 環境変数管理 | 既存を更新 |

### 出力アダプタの切り替え

```
正本JSON（ピボット）
       ↓
  OUTPUT_MODE 設定
       ↓                    ↓
  mf_api_client         csv_exporter
  （主系・API登録）      （派生・CSV出力）
```

`OUTPUT_MODE=mf_api`（デフォルト）または `csv` を `.env` で指定。
アダプタ追加（freee・弥生等）は `output/` にファイルを足すだけ。`pipeline.py` は変更不要。

---

## 4. 処理フロー

```
[手動実行] python pipeline.py

for 人名フォルダ in Drive/00_受信トレイ/:
  for 画像ファイル in 人名フォルダ:

    [Step 1] ocr_engine: 画像 → OCRテキスト
      失敗 → Drive/02_エラー/{人名}/ へ移動・ログ記録・次ファイルへ

    [Step 2] account_resolver: MFマスタ取得 + 過去仕訳CSV読込 → コンテキスト生成

    [Step 3] llm_provider: OCRテキスト + コンテキスト → JSON

    [Step 4] schema_builder: バリデーション（tax整合・必須項目チェック）
      失敗 → Drive/02_エラー/{人名}/ へ移動・ログ記録・次ファイルへ

    [Step 5] ファイルリネーム: yyyymmdd_取引先.ext

    [Step 6] Drive/01_処理済み/{人名}/ へ移動  ← 正本JSONが確定した時点

    [Step 7] mf_api_client: 仕訳登録 → journal_id 取得

    [Step 8] mf_api_client: 証憑アップロード（Base64）← journal_id 必須

    [Step 9] ログ記録（成功・処理時間・journal_id）
```

---

## 5. Googleドライブ構成

```
レシート/
  00_受信トレイ/{人名}/   ← スマホから保存
  01_処理済み/{人名}/     ← Step 6 完了後
  02_エラー/{人名}/       ← OCR失敗またはバリデーション失敗
```

フォルダはローカルにマウントされたドライブ（Gドライブ・BOX等）上に置く。
`INBOX_FOLDER_PATH` 等の環境変数でパスを渡す。Drive API は使用しない。
人名フォルダは提出者識別用。v1では仕訳の `department_id` 等には反映しない（導入先次第で拡張）。

---

## 6. 設定（.env）

```
LLM_ENGINE=claude                    # claude | openai | gemini（切り替えポイント）
OUTPUT_MODE=mf_api                   # mf_api | csv（出力アダプタ切り替え）
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...                   # LLM_ENGINE=openai 時のみ
GEMINI_API_KEY=...                   # LLM_ENGINE=gemini 時のみ（無料枠あり）
GOOGLE_APPLICATION_CREDENTIALS=...  # Vision API 用サービスアカウント
MF_CLIENT_ID=...
MF_CLIENT_SECRET=...
MF_ACCESS_TOKEN=...                  # 有効期限1時間・自動リフレッシュ
MF_REFRESH_TOKEN=...
INBOX_FOLDER_PATH=...                # 受信トレイフォルダのローカルパス（例: G:\レシート\00_受信トレイ）
PROCESSED_FOLDER_PATH=...           # 処理済みフォルダのローカルパス
ERROR_FOLDER_PATH=...               # エラーフォルダのローカルパス
PAST_JOURNALS_CSV=./data/past_journals.csv
```

---

## 7. ADR（アーキテクチャ決定記録）

| ADR | 決定 | 理由 |
|---|---|---|
| ADR-001 | OCR = Google Vision API（クラウド固定） | 精度・速度・コスト最優先。ローカルOCRは非目標 |
| ADR-002 | LLM = LLM_ENGINE env varで切り替え | 企業ごとに承認LLMが異なる。枝葉として設計 |
| ADR-003 | 人別サブフォルダ | 将来の複数ユーザー対応・提出者識別 |
| ADR-004 | 正本JSON v1.0.0 = 唯一のピボット | 上流・下流の契約を一箇所に集約。スキーマ変更は interface.md が起点 |
| ADR-005 | 出力アダプタパターン（`output/` フォルダ） | MF API・CSV・将来の他会計システムを同一インターフェースで交換可能にする |
| ADR-010 | MF API直接登録（CSV非主系） | 可逆性あり・手作業ゼロへ。CSVはJSONから派生可能（OUTPUT_MODE=csv で切り替え） |
| ADR-006 | JSON確定時点で処理済みへ移動（API登録完了を待たない） | JSON後の加工は確実。OCR・LLM失敗のみ入口でブロック |
| ADR-007 | 勘定科目 = 過去仕訳CSV + MFマスタをLLMコンテキストに渡す | 企業ごとの会計慣行に自動適応。ルールベース不要 |
| ADR-008 | 証憑画像はBase64で POST /api/v3/vouchers | MF API対応済み確認済み（2026-06-21調査） |
| ADR-009 | ローカルLLM（Ollama）は対象外（v1） | 安定性優先。Phase 2以降で実験 |
| ADR-011 | Gemini（gemini-2.0-flash）をLLM_ENGINE第3の選択肢として追加 | 無料枠（1日1,500req）でのテスト・コスト削減目的。google-generativeai ライブラリ使用。ADR-002の枝葉設計に従い llm_provider.py のみ変更 |
| ADR-012 | 入力源を Drive API からマウント済みローカルパスに変更 | Drive API（フォルダID方式）は不要な複雑さ。GドライブやBOXをマウントすれば複数PC対応も可能。os/pathlib/shutil で十分。GDRIVE_*_FOLDER_ID を廃止し INBOX_FOLDER_PATH 等のパス変数に置き換え |
| ADR-013 | **Visionフロント＝Claude Code 対話スキル**（構成B）を上流の選択肢に追加 | agy CLIは非対話バッチで画像解析がハング（実測）。外部Vision/LLM APIはキー・課金・外部送信が増える。Claude Code（対話エージェント）はRead/Visionで画像→正本JSONを直接生成でき、人が起動する前提（UKIAの原案）に合致。鍵不要・人ゲート内蔵。OCR/LLM API層（ocr_engine/llm_provider）は構成Bでは不使用。**正本JSON v1.0.0 は不変＝下流（csv_exporter）はそのまま再利用**。 |
| ADR-014 | 勘定科目＝**蒸留表（店名→勘定科目）で確定スクリプト側に決定論マッピング**（構成B） | ADR-007（過去仕訳をLLM文脈に渡す）はLLMが判断＝トークン消費・非決定論。構成BではVision（Claude）を画像抽出に専念させ、勘定科目は過去仕訳帳を蒸留した参照表（店名キー→主勘定科目＋確信ヒント）でスクリプトが決定論的に付与。確信「低」は warning を付け人確認（可逆）。トークン軽・監査可能。 |
| ADR-015 | MF CSV出力を**実インポート形式に確定**（27列・Shift-JIS(cp932)・複式借方/貸方・取引日YYYY/M/D・税区分「課税仕入 10%」） | UKIAの実MFインポートCSV（現物）と既存csv_exporter（14列・utf-8-sig・貸方空）が不一致。現物に合わせ全面改訂：貸方＝未払金・補助科目 現金・対象外、借方=貸方=税込額。複数税率混在/8%検知は方式B（CSV化せずエラー隔離）。借方インボイス列はT番号でなく空（実サンプル準拠・T番号はJSONに保持）。 |
| ADR-016 | 勘定科目決定を**3段ハイブリッド**に（ADR-014の穴を塞ぐ） | 蒸留表は店名一致のみで、未収載の新店は内容が明白（例「駐車料金」）でも既定『仮払金』になる欠陥が実運用で判明。決定順を ①蒸留表の店名一致（履歴整合・最優先）→ ②Claudeが内容から推定した `inferred.account_title`（Vision段で生成・追加トークンほぼ無し）→ ③既定『仮払金』＋warning とする。蒸留表の決定論性は既知店で維持しつつ、未知店の意味推論を回復。 |

---

## 8. 制約（変更禁止）

1. 正本JSONスキーマ（`interface.md`）を実装側で勝手に変更しない
2. 証憑アップロード（Step 8）は journal_id 取得後のみ実行する（順序保証）
3. MF API登録はバリデーション通過後のみ実行する（エラーファイルには触れない）
4. Drive認証情報・MFトークン・APIキーをコードにハードコードしない
5. 入力源はマウント済みフォルダ経由とする（Drive API は使用しない）

---

## 9. 構成B（Claude Vision フロント）— 2026-06-28 追加

> 構成A（Vision OCR＋LLM API → 正本JSON）と**正本JSON v1.0.0 を共有**する、別の上流。
> Visionエンジン＝Claude Code（対話）。人が起動し、Claudeが画像を読み、確定スクリプトがCSV化する。

### 処理フロー（構成B）

```
[人] スマホ撮影 → 00_受信トレイ/{人名}/ に保存
[人] Claude Code でスキル起動（例: レシート取り込んで）

[Claude(Vision)]
  for 画像 in 00_受信トレイ/ 配下（再帰）:
    画像を Read（Vision）で読取 → 正本JSON v1.0.0 を生成
      （partner_name / partner_normalized / date / total /
        tax.rate_10 rate_8 / partner_registration_number /
        payment_method / confidence / validation / extensions.summary）
      ※ inferred.account_title は埋めない（スクリプトが蒸留表で付与）
    正本JSONを output/json/ に保存

[確定スクリプト build_mf_csv.py（決定論）]
  for 正本JSON:
    蒸留表で partner_normalized → 勘定科目＋確信（ADR-014）
    検証（tax合算=total / 方式B：複数税率・8%は除外しエラーへ）
    → MF CSV（27列・cp932・ADR-015）に1行追記
  CSV書込成功後に画像を 01_処理済み/ or 02_エラー/ へ移動（リネーム）

[人ゲート] 結果レポート（件数・warnings）確認 → CSVをMFへ手動インポート → MF画面で確認・修正（可逆）
```

### 構成A/B の分担（同じ正本JSONを共有）

| 層 | 構成A（既存） | 構成B（追加） | 共有 |
|---|---|---|---|
| 上流（JSON生成） | ocr_engine + llm_provider（API） | **Claude Code 対話Vision** | — |
| 勘定科目 | account_resolver（LLM文脈・ADR-007） | **蒸留表・決定論（ADR-014）** | — |
| 正本JSON | v1.0.0 | v1.0.0 | ✅ 同一 |
| 下流（CSV） | csv_exporter | csv_exporter | ✅ 同一（ADR-015で27列cp932へ改訂） |

### 構成B固有の参照データ

- 勘定科目蒸留表：`99_勘定科目参照/勘定科目参照表_v1.md`（受信トレイと同じドライブ。過去のMF仕訳帳から蒸留。生成手順は `doc/account_distillation.md`）。
- CSVマッピング契約：`doc/csv_mapping.md`（27列・cp932・借方/貸方・方式B）。

---

*作成: 2026-06-21 / Claude Code Phase 0 / purpose.md・interface.md から派生*
*構成B追記: 2026-06-28*
