# レシート自動仕訳システム v2.0 - 仕様書

**作成日**: 2026年1月23日  
**対象**: Vision LLMベースの新実装

---

## 1. プロジェクト概要

### 1.1 目的
レシート画像から直接、会計システム用のJSON形式データを抽出し、マネーフォワード（MF）インポート用CSVを生成する。

### 1.2 v1.0からの変更点

| 項目 | v1.0 (OCR方式) | v2.0 (Vision LLM方式) |
|------|----------------|----------------------|
| アーキテクチャ | 画像→OCR→LLM→CSV | 画像→Vision LLM→CSV |
| OCR | PaddleOCR/EasyOCR | **不要** |
| 精度 | 低（誤認識多数） | 高（レイアウト理解） |
| 処理時間 | 15-20秒 | 10-15秒（予測） |
| ファインチューニング | テキストLLM | Vision LLM |

### 1.3 プロジェクト哲学
> 「誰でも使えるAI」の実現  
> - ✅ ローカル実行（プライバシー保護、オフライン対応）
> - ✅ 低スペックPC対応（RTX 5050、4GB VRAM）
> - ✅ 無料（OpenAI API不要）
> - ✅ 高精度（専用モデルのファインチューニング）

---

## 2. システムアーキテクチャ

### 2.1 処理フロー

```
┌─────────────┐
│ レシート画像 │
│  (JPG/PNG)  │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────┐
│ Vision LLM (Qwen2.5-VL)      │
│ - Base: Qwen2.5-VL-2B        │
│ - Format: GGUF (Q4_K_M)      │
│ - Custom: LoRA fine-tuned    │
│ - Engine: llama.cpp          │
└──────┬───────────────────────┘
       │
       ▼
┌─────────────────────────┐
│    JSON データ          │
│  {                      │
│    "store_name": "...", │
│    "date": "...",       │
│    "items": [...],      │
│    "total": 108,        │
│    "tax": 8,            │
│    "invoice_number": "" │
│  }                      │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│  勘定科目判定ロジック     │
│  - ガソリン→旅費交通費   │
│  - コンビニ→消耗品費     │
│  - 飲食店→会議費         │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│ MF仕訳CSVファイル        │
│  (mf_journal_entry.csv) │
└─────────────────────────┘

【Phase 4: Rustパッケージ化】
       ▼
┌─────────────────────────┐
│ 配布用バイナリ (Rust)    │
│ - 1ファイル実行形式      │
│ - Python環境不要         │
│ - GPU不要（CPU推論）     │
│ - サイズ: 2GB以下        │
└─────────────────────────┘
```

### 2.2 技術スタック

**開発フェーズ（Phase 1-3: Python）**:

| 層 | 技術 | 備考 |
|----|------|------|
| Vision LLM | Qwen2.5-VL-2B | 日本語レシートに最適化 |
| 推論エンジン | Ollama / llama.cpp | GGUF形式サポート |
| ファインチューニング | Unsloth + LoRA | RTX 5050で4GB VRAM |
| GUI | Tkinter | Python標準ライブラリ |
| CSV生成 | Python標準csv | UTF-8-sig (Excel対応) |
| 実行環境 | Python 3.12 | venv使用 |

**配布フェーズ（Phase 4: Rust）**:

| 層 | 技術 | 備考 |
|----|------|------|
| 推論エンジン | llama-cpp-rs | Rust bindings for llama.cpp |
| 画像処理 | image crate | リサイズ・前処理 |
| GUI | egui / iced | Rustネイティブ軽量GUI |
| モデル形式 | GGUF Q4_K_M | 量子化で1.5-2GB |
| ビルド | cargo build --release | 1バイナリ配布 |

### 2.3 モデル選択の根拠

#### なぜQwen2.5-VLか？

**LLaVA 7Bとの比較**:

| 項目 | LLaVA 7B | Qwen2.5-VL-2B | 判定 |
|------|----------|---------------|------|
| 日本語精度 | △ | ◎ | Qwen圧勝 |
| 小さい文字 | △ | ◎ | 動的解像度対応 |
| レイアウト理解 | ○ | ◎ | 縦長レシートに強い |
| モデルサイズ | 7B (5GB) | 2B (1.5GB) | 2Bが軽量 |
| CPU推論速度 | 遅い | 速い | 2Bが3-4倍高速 |
| 日本語学習量 | 少ない | 多い | Qwenは中国語・日本語特化 |

**結論**: レシート解析には**Qwen2.5-VL-2B**が最適

#### 2B vs 7Bの選択

| 用途 | 推奨モデル | 理由 |
|------|-----------|------|
| 開発・検証 | 7B | 未学習でも高精度 |
| 配布・製品化 | 2B | ファインチューニングで7B並み精度 + 軽量高速 |

**本プロジェクトの方針**:
1. Phase 1-2: **Qwen2.5-VL-7B**で精度検証
2. Phase 3: **Qwen2.5-VL-2B**にLoRAファインチューニング
3. Phase 4: **2B GGUF版**をRustパッケージ化

---

## 3. 機能仕様

### 3.1 入力

**対応画像形式**:
- JPG/JPEG
- PNG
- 解像度: 800px〜（推奨1200px以上）

**対応レシート種別**:
- コンビニ（FamilyMart、ローソン、セブンイレブン）
- ガソリンスタンド（ENEOS、出光、コスモ）
- 飲食店
- タクシー
- **インボイス対応**（登録番号自動抽出）

### 3.2 Vision LLMによる抽出

**モデル**: Qwen2.5-VL-7B → 2B (ファインチューニング後)

**推論方法**:
```bash
# Ollama経由（開発時）
ollama run qwen2.5-vl:7b

# llama.cpp直接（配布時）
./main -m qwen2.5-vl-2b-q4_k_m.gguf --image receipt.jpg
```

**プロンプト設計**:
```
あなたはレシート画像を解析する専門家です。
以下の情報をJSON形式で正確に抽出してください：

【抽出項目】
1. 店舗名 (store_name): レシート上部の店舗ロゴまたは店名
2. 日付 (date): YYYY-MM-DD形式
3. 時刻 (time): HH:MM形式
4. 商品リスト (items): [{"name": "商品名", "price": 金額}]
5. 合計金額 (total): 最終支払額（値引き後）
6. 消費税額 (tax): 内消費税の金額
7. 支払方法 (payment_method): クレジット/現金/その他

【重要な注意事項】
- 合計金額は値引き後の最終金額を使用すること
- 「小計」「含計」「合計」などのラベル近くの金額を探す
- クーポン値引き後の金額がある場合はそちらを優先
- 複数の金額候補がある場合は、レシート下部の金額を選択
- 数字の読み間違いに注意（¥108を¥4497としない）

【出力形式】
JSON形式のみを出力してください。説明文は不要です。

例:
{
  "store_name": "FamilyMart",
  "date": "2024-01-05",
  "time": "09:38",
  "items": [
    {"name": "スイートオレンジ&温州みかん", "price": 108}
  ],
  "total": 108,
  "tax": 8,
  "payment_method": "クレジット"
}
```

### 3.3 勘定科目判定ロジック

**convert_to_mf.py の仕様**（v1.0から引き継ぎ）

**判定ルール**（優先順位順）:

1. **ガソリンスタンド** → `旅費交通費` / `ガソリン代`
   - キーワード: eneos, エネオス, 出光, コスモ, シェル, レギュラー, ハイオク

2. **飲食店** → `会議費` / `会議飲食費`
   - キーワード: restaurant, cafe, カフェ, レストラン, bakery

3. **コンビニ** → `消耗品費` / `事務用品`
   - キーワード: familymart, lawson, seven, ファミマ, ローソン, セブン

4. **タクシー** → `旅費交通費` / `タクシー代`
   - キーワード: タクシー, taxi, 交通

5. **デフォルト** → `会議費`

**消費税仕訳**:
```
借方: 費用科目 ¥XXX (税区分: 課税仕入 10%, 税額: ¥YY)
貸方: 未払金 ¥XXX (税区分: 対象外, 税額: ¥0)
```

### 3.4 出力

**ファイル名**: `mf_journal_entry.csv`

**フォーマット**: UTF-8-sig（Excelで開ける）

**列構成** (27列):
```
取引No,取引日,借方勘定科目,借方補助科目,借方部門,借方取引先,借方税区分,
借方インボイス,借方金額(円),借方税額,貸方勘定科目,貸方補助科目,貸方部門,
貸方取引先,貸方税区分,貸方インボイス,貸方金額(円),貸方税額,摘要,
仕訳メモ,タグ,MF仕訳タイプ,決算整理仕訳,作成日時,作成者,
最終更新日時,最終更新者
```

**サンプル出力**:
```csv
1,2024/1/5,消耗品費,事務用品,,FamilyMart,課税仕入 10%,,108,8,未払金,クレジットカード,,,対象外,,108,0,FamilyMart クレジット,,,,,,,,
```

---

## 4. 実装計画

### Phase 1: 基礎実装（1週間）

**目標**: Qwen2.5-VL-7Bで基本動作を確認

1. **環境構築**
   ```bash
   # Ollamaでのインストール
   ollama pull qwen2.5-vl:7b
   pip install ollama pillow
   ```

2. **vision_qwen.py 作成**
   - 画像読み込み（高解像度対応）
   - Qwen2.5-VL API呼び出し
   - JSON解析とバリデーション

3. **main.py 改修**
   - OCR呼び出し削除
   - vision_qwen.py 統合
   - エラーハンドリング改善

4. **精度検証**
   - テストレシート10-20枚で検証
   - v1.0 (OCR→LLM方式) との比較
   - **ベンチマーク**: 処理時間、精度、VRAM使用量

### Phase 2: 7B→2Bモデル比較（1週間）

**目標**: 未学習2Bモデルの実力測定

1. **Qwen2.5-VL-2Bインストール**
   ```bash
   ollama pull qwen2.5-vl:2b
   ```

2. **同一データで7B vs 2B比較**
   - 精度差の定量化
   - 処理速度の測定
   - VRAM/CPU使用率の比較

3. **2Bモデルでの課題抽出**
   - 誤認識パターンの分析
   - ファインチューニングで改善可能か判断

4. **学習データ設計**
   - 100-500枚の収集計画
   - アノテーション方法の確立

### Phase 3: LoRAファインチューニング（2週間）

**目標**: レシート専用2Bモデル作成（7B並み精度）

1. **データ収集**
   - レシート画像: 100-500枚
   - 正解JSON作成（手動 or GPT-4V補助）
   - データ拡張（回転、ノイズ、明度調整）

2. **データセット形式**
   ```json
   {
     "image": "receipt_001.jpg",
     "conversations": [
       {
         "role": "user",
         "content": "この画像はレシートです。店舗名・日時・商品・合計金額・消費税・インボイス登録番号をJSON形式で抽出してください"
       },
       {
         "role": "assistant",
         "content": "{\"store_name\": \"FamilyMart\", \"date\": \"2024-01-05\", \"total\": 108, \"tax\": 8, \"invoice_number\": \"T1234567890123\"}"
       }
     ]
   }
   ```

3. **LoRA学習（Unsloth使用）**
   ```bash
   # QLoRA: 4bit量子化でVRAM 4GB以下
   python train_lora.py \
     --model qwen2.5-vl-2b \
     --data receipts_dataset.json \
     --lora-rank 16 \
     --epochs 3 \
     --batch-size 1
   ```

4. **モデル評価**
   - テストセット（50枚）で精度測定
   - **目標**: 7Bモデルの90%以上の精度
   - LoRAアダプター保存: `receipt-qwen-2b-lora`

5. **GGUF変換**
   ```bash
   # 配布用に量子化
   python convert_to_gguf.py \
     --model receipt-qwen-2b-lora \
     --output receipt-qwen-2b-q4_k_m.gguf
   ```

### Phase 4: Rustパッケージ化（2週間）

**目標**: 企業配布可能な1バイナリ実行形式

1. **Rustプロジェクト作成**
   ```bash
   cargo new --bin receipt-analyzer
   cd receipt-analyzer
   ```

2. **依存関係追加 (Cargo.toml)**
   ```toml
   [dependencies]
   llama-cpp-rs = "0.5"  # llama.cppのRustバインディング
   image = "0.24"        # 画像処理
   egui = "0.24"         # GUI（軽量）
   serde_json = "1.0"    # JSON処理
   csv = "1.3"           # CSV出力
   ```

3. **推論エンジン実装 (src/inference.rs)**
   ```rust
   use llama_cpp_rs::{LlamaModel, LlamaContext};
   
   pub struct ReceiptAnalyzer {
       model: LlamaModel,
       context: LlamaContext,
   }
   
   impl ReceiptAnalyzer {
       pub fn new(model_path: &str) -> Self {
           // GGUFモデル読み込み
           let model = LlamaModel::load_from_file(model_path).unwrap();
           let context = model.create_context().unwrap();
           Self { model, context }
       }
       
       pub fn analyze_receipt(&self, image_path: &str) -> serde_json::Value {
           // 画像前処理 → Vision LLM推論 → JSON解析
       }
   }
   ```

4. **GUI実装 (src/main.rs)**
   - ファイル選択ダイアログ
   - 進捗表示
   - 結果プレビュー
   - CSV保存ボタン

5. **ビルド最適化**
   ```bash
   # リリースビルド（サイズ最適化）
   cargo build --release
   
   # さらに圧縮（UPX使用）
   upx --best --lzma target/release/receipt-analyzer.exe
   ```

6. **配布パッケージ作成**
   ```
   receipt-analyzer-v2.0/
   ├── receipt-analyzer.exe  # 実行ファイル（10-20MB）
   ├── receipt-qwen-2b-q4_k_m.gguf  # モデル（1.5-2GB）
   ├── README.txt            # 使用方法
   └── LICENSE.txt
   ```

**配布時の利点**:
- ✅ Python環境不要（1ファイル実行）
- ✅ GPU不要（CPUで高速動作）
- ✅ 依存関係なし（DLL地獄なし）
- ✅ 企業PCでも動作（権限不要）

### Phase 5: ポートフォリオ完成（1週間）

1. **README.md充実**
   - デモGIF作成（実行の様子）
   - ベンチマーク結果
   - インストール手順（Python版・Rust版両方）
   - 精度データ（OCR方式 vs Vision方式）

2. **ドキュメント整備**
   - コード内コメント充実
   - API仕様書
   - ファインチューニング手順書

3. **公開準備**
   - GitHub公開
   - Qiita記事執筆
   - リリースノート作成

---

## 5. 成功指標

### 5.1 精度目標

| 指標 | v1.0 (OCR→LLM) | v2.0 Phase1 (7B) | v2.0 Phase3 (2B LoRA) | v2.0 Phase4 (Rust) |
|------|----------------|------------------|----------------------|-------------------|
| 店舗名正答率 | 80% | **95%** | **95%** | **95%** |
| 金額正答率 | 60% | **90%** | **90%** | **90%** |
| 日時正答率 | 90% | **98%** | **98%** | **98%** |
| インボイス番号 | - | **85%** | **90%** | **90%** |
| 総合正答率 | 70% | **90%** | **92%** | **92%** |

### 5.2 パフォーマンス目標

| 項目 | Python版 (7B) | Python版 (2B) | Rust版 (2B GGUF) |
|------|---------------|---------------|------------------|
| 処理時間/枚 | 15秒 | **10秒** | **8秒** |
| VRAM使用量 | 6GB | 3GB | **0GB (CPU)** |
| メモリ使用量 | 8GB | 4GB | **2GB** |
| バイナリサイズ | - | - | **2GB (モデル込)** |
| 起動時間 | 5秒 | 3秒 | **1秒** |

**Rust版の配布時優位性**:
- ✅ Python環境不要（インストーラー不要）
- ✅ GPU不要（CPUのみで動作）
- ✅ 依存関係ゼロ（.exeダブルクリックで起動）
- ✅ 企業PC対応（管理者権限不要）
- ✅ オフライン動作（ネット接続不要）

### 5.3 ユーザビリティ目標

- ✅ GUIで画像選択（1クリック）
- ✅ 結果をプレビュー表示
- ✅ CSV自動保存
- ✅ エラーメッセージが分かりやすい
- ✅ インストール手順が明確（Rust版: 解凍するだけ）
- ✅ マニュアル不要で直感的に使える

### 5.2 パフォーマンス目標

- 処理時間: 15秒以内/枚
- VRAM使用量: 4GB以内
- GPU使用率: 80%以下（発熱対策）

### 5.3 ユーザビリティ目標

- ✅ GUIで画像選択（1クリック）
- ✅ 結果をメッセージボックスで表示
- ✅ エラーメッセージが分かりやすい
- ✅ インストール手順が明確

---

## 6. リスクと対策

### 6.1 技術リスク

| リスク | 対策 |
|--------|------|
| Qwen2.5-VLの日本語精度が想定以下 | 7B→2Bで段階的検証、最悪7Bで配布 |
| VRAM不足 | QLoRA 4bit量子化、バッチサイズ1 |
| 学習データ不足 | データ拡張（回転、ノイズ、明度）、最小100枚でスタート |
| Rustビルドエラー | llama-cpp-rsの代わりにCandle検討 |
| GGUF変換失敗 | llama.cpp公式ツール使用 |

### 6.2 スケジュールリスク

| リスク | 対策 |
|--------|------|
| LoRA学習が長期化 | Phase 1 (7B未学習) で既に公開レベル |
| データ収集が進まない | 最小100枚で開始、段階的改善 |
| Rust実装が難航 | Python版を先行公開、Rust版は後日リリース |

### 6.3 ビジネスリスク

| リスク | 対策 |
|--------|------|
| 競合製品の出現 | インボイス特化・MF直結で差別化 |
| 配布先でエラー多発 | 詳細なエラーログ、FAQ充実 |

---

## 7. 引き継ぎファイル

### 7.1 必須ファイル（新ディレクトリへコピー）

- ✅ `NEXT_PROJECT_SPEC.md` (本ファイル)
- ✅ `convert_to_mf.py` (勘定科目判定ロジック)
- ✅ `PROJECT_SUMMARY.md` (学びの記録)

### 7.2 参考ファイル（任意）

- `llm_llama3.2.py` (プロンプト設計の参考)
- `main.py` (GUI構造の参考)

### 7.3 不要ファイル（削除対象）

- `venv_py312/` (5.5GB の仮想環境)
- `venv/` (25MB の古い仮想環境)
- `ocr_paddleocr.py`, `ocr_easyocr.py` (OCR不要)
- `test2.py` (検証用)
- `ocr_result.json`, `llm_result.json`, `llm_summary.json` (一時ファイル)
- `mf_journal_entry.csv` (出力サンプル)
- `__pycache__/` (キャッシュ)
- `ANALYSIS.md` (一時メモ)

**削除効果**: 5,600 MB → 10 MB以下（99.8%削減）

---

## 8. 参考資料

### 8.1 技術記事

**Vision LLM**:
- [Qwen2.5-VL公式](https://github.com/QwenLM/Qwen2.5-VL)
- [Qwen2.5-VL Ollama](https://ollama.ai/library/qwen2.5-vl)
- [動的解像度の説明](https://qwenlm.github.io/blog/qwen2-vl/)

**LoRA学習**:
- [Unsloth LoRA学習](https://github.com/unslothai/unsloth)
- [Axolotl（QLoRA）](https://github.com/OpenAccess-AI-Collective/axolotl)

**Rust推論**:
- [llama-cpp-rs](https://github.com/edgenai/llama_cpp-rs)
- [Candle](https://github.com/huggingface/candle)
- [GGUF形式](https://github.com/ggerganov/llama.cpp/blob/master/gguf-py/README.md)

### 8.2 データセット例

- [領収書データセット (SROIE)](https://rrc.cvc.uab.es/?ch=13)
- [日本語レシートデータセット構築ガイド](https://qiita.com/tags/領収書認識)
- [インボイス制度対応](https://www.nta.go.jp/taxes/shiraberu/zeimokubetsu/shohi/keigenzeiritsu/invoice.htm)

---

## 9. まとめ

### v2.0の核心技術

**Qwen2.5-VL + LoRA + Rustの三位一体**:

1. **Qwen2.5-VL**: 日本語レシートに最適化されたVision LLM
   - ✅ 動的解像度対応（縦長レシート、小さい文字）
   - ✅ OCRステップ不要（誤認識リスク排除）
   - ✅ レイアウト理解（文脈を踏まえた抽出）

2. **LoRAファインチューニング**: レシート特化の専用モデル化
   - ✅ 2Bモデルで7B並み精度（軽量・高速）
   - ✅ RTX 5050でも学習可能（QLoRA 4bit）
   - ✅ 100-500枚で実用レベル

3. **Rust配布**: 企業PCでも動く堅牢パッケージ
   - ✅ Python環境不要（.exeダブルクリック）
   - ✅ GPU不要（CPUで8秒/枚）
   - ✅ 依存関係ゼロ（DLL地獄なし）
   - ✅ オフライン動作（プライバシー保護）

### プロジェクトの価値

**技術的差別化**:
- 🎯 OCR→LLMの2段階を1段階に統合
- 🎯 汎用モデル→レシート特化モデル
- 🎯 Python開発版→Rust配布版の両立
- 🎯 2026年の最先端技術スタック

**ビジネス価値**:
- 💼 実務に即投入可能（マネーフォワード連携）
- 💼 インボイス制度対応（登録番号自動抽出）
- 💼 企業配布可能（管理者権限不要）
- 💼 サポートコスト削減（環境依存なし）

**ポートフォリオとしての魅力**:
- 📚 Vision LLMの実践的活用
- 📚 ファインチューニングの実証
- 📚 Rustでのプロダクト化
- 📚 実務課題の解決（OCR精度問題）

### 「誰でも使えるAI」の実現

このプロジェクトは以下を証明します：

> **高価なAPI不要、高性能GPU不要で、
> 専門的なAI機能を誰でも使えるようにできる**

- ✅ ローカル実行（月額課金なし、オフライン可）
- ✅ 低スペックPC対応（CPU推論、2GB RAM）
- ✅ 簡単インストール（解凍するだけ）
- ✅ 高精度（専用ファインチューニング）

これは単なる技術デモではなく、**実際に配布して使われるプロダクト**です。

### 次のステップ

**今日（1月23日）**:
- ✅ 仕様書完成
- ✅ 学びの記録（PROJECT_SUMMARY.md更新）
- ✅ 不要ファイル整理

**明日から（新ディレクトリで）**:
1. Phase 1開始: Qwen2.5-VL-7Bインストール
2. vision_qwen.py実装
3. ベンチマーク（v1.0 OCR方式との比較）

**2週間後**:
4. Phase 2: 7B vs 2B比較
5. Phase 3: LoRAファインチューニング

**1ヶ月後**:
6. Phase 4: Rust配布版完成
7. GitHub公開 + Qiita記事

---

**作成者**: ukyas  
**最終更新**: 2026年1月23日  
**バージョン**: v2.0仕様（Qwen2.5-VL + Rust）

---

## 変更履歴

### 2026年1月23日
- 初版作成
- LLaVA → Qwen2.5-VLに変更（日本語精度向上）
- Rustパッケージ化をPhase 4に追加
- 2B vs 7Bモデル比較を明示
- GGUF量子化とllama-cpp-rs統合を追加

---

## 9. まとめ

### v2.0の核心

**Vision LLM方式により**:
- ✅ OCR誤認識問題の根本解決
- ✅ レイアウト理解による高精度化
- ✅ LoRAによる専用モデル化
- ✅ 「誰でも使えるAI」の実現

**プロジェクトの価値**:
- 🎯 ポートフォリオとして差別化
- 🎯 実務に即応用可能
- 🎯 オープンソースコミュニティへの貢献
- 🎯 技術トレンド（Vision LLM、LoRA）の実践

**次のステップ**: 新ディレクトリでPhase 1を開始 → LLaVA動作確認

---

**作成者**: ukyas  
**最終更新**: 2026年1月23日
