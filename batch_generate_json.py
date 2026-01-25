"""
レシート一括JSON生成ツール
- vision_receipt_chat.pyの機能を拡張
- フォルダ内の全画像を自動処理
- labeling_tool.pyでの修正作業を効率化
"""

import ollama
import json
from pathlib import Path
from datetime import datetime
import sys
from PIL import Image
import tempfile
import os

def preprocess_image(image_path):
    """
    画像前処理（現在は無効化：手動調整済み画像をテスト）
    
    Returns:
        元の画像パス、削除不要フラグ
    """
    # 前処理なし：元の画像をそのまま使用
    return str(image_path), False


def extract_receipt_json(image_path, model='llama3.2-vision:11b'):
    """
    レシート画像からJSON抽出（vision_receipt_chat.pyと同じロジック）
    """
    
    # 軽減税率対応の詳細プロンプト
    prompt = """このレシート画像から以下の情報をJSON形式で抽出してください。

出力形式：
{
  "store": "店舗名",
  "date": "YYYY-MM-DD",
  "time": "HH:MM",
  "total": 合計金額（数値のみ、カンマなし）,
  "tax_10_base": 10%対象金額（数値、なければ0）,
  "tax_10_amount": 10%消費税額（数値、なければ0）,
  "tax_8_base": 8%対象金額（数値、なければ0）,
  "tax_8_amount": 8%消費税額（数値、なければ0）,
  "invoice_number": "インボイス登録番号（Tから始まる13桁、なければnull）",
  "payment_method": "支払方法（現金/クレジット/電子マネー等）",
  "items": [
    {"name": "商品名", "price": 単価（数値）}
  ]
}

注意事項：
- 金額は必ず数値型（カンマなし）
- 軽減税率（8%）と通常税率（10%）を区別
- 値引き後の最終支払額を使用
- JSONのみを出力（説明不要）
"""

    response = ollama.chat(
        model=model,
        messages=[{
            'role': 'user', 
            'content': prompt, 
            'images': [str(image_path)]
        }],
        options={"temperature": 0.1}
    )

    return response['message']['content']


def parse_json_from_response(response_text):
    """LLM出力からJSON部分を抽出"""
    
    if '```json' in response_text:
        json_str = response_text.split('```json')[1].split('```')[0].strip()
    elif '{' in response_text:
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        json_str = response_text[json_start:json_end]
    else:
        raise ValueError("JSON形式が見つかりません")
    
    return json.loads(json_str)


def process_single_image(image_file, json_path, model, overwrite, log_file):
    """
    1枚の画像を処理（前処理含む）
    
    Returns:
        'success', 'skip', 'error'
    """
    import time
    import gc
    
    json_file = json_path / f"{image_file.stem}.json"
    
    # 既存チェック
    if json_file.exists() and not overwrite:
        print(f"   ⏭️  スキップ（既存）")
        return 'skip'
    
    # 画像前処理
    processed_path, needs_cleanup = preprocess_image(image_file)
    
    try:
        # JSON抽出
        start_time = time.time()
        raw_response = extract_receipt_json(processed_path, model)
        elapsed = time.time() - start_time
        
        print(f"   ⏱️  処理時間: {elapsed:.1f}秒")
        
        try:
            parsed_json = parse_json_from_response(raw_response)
            
            # 保存
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(parsed_json, f, ensure_ascii=False, indent=2)
            
            print(f"   ✅ 成功")
            
            # ログ記録
            store = parsed_json.get('store', '不明')
            total = parsed_json.get('total', 0)
            log_file.write(f"\n✅ {image_file.name} → {json_file.name}\n")
            log_file.write(f"   店舗: {store}\n")
            log_file.write(f"   合計: {total}円\n")
            
            return 'success'
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"   ❌ エラー: {e}")
            
            # エラー詳細を保存
            error_file = json_path / f"{image_file.stem}_error.txt"
            with open(error_file, 'w', encoding='utf-8') as f:
                f.write("=== LLM生出力 ===\n")
                f.write(raw_response)
                f.write("\n\n=== エラー ===\n")
                f.write(str(e))
            
            log_file.write(f"\n❌ {image_file.name}: {e}\n")
            return 'error'
    
    finally:
        # 一時ファイルのクリーンアップ
        if needs_cleanup and os.path.exists(processed_path):
            try:
                os.unlink(processed_path)
            except:
                pass
        
        # メモリ解放
        gc.collect()


def batch_generate(image_dir, json_dir, model='llama3.2-vision:11b', overwrite=False):
    """
    フォルダ内の全画像を一括処理
    
    Args:
        image_dir: 画像フォルダ
        json_dir: JSON保存先
        model: 使用するVision LLMモデル
        overwrite: 既存JSONを上書きするか
    """
    
    img_path = Path(image_dir)
    json_path = Path(json_dir)
    json_path.mkdir(parents=True, exist_ok=True)
    
    # 画像ファイル取得
    images = sorted(list(img_path.glob("*.jpg")) + list(img_path.glob("*.png")))
    
    if not images:
        print(f"⚠️ {image_dir} に画像ファイルが見つかりません")
        return
    
    print(f"🚀 {len(images)}枚の画像からJSON生成を開始")
    print(f"📐 モデル: {model}")
    print(f"📁 保存先: {json_path.absolute()}\n")
    
    # ログファイル
    log_path = json_path.parent / "auto_generation_log.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(log_path, 'a', encoding='utf-8') as log:
        log.write(f"\n{'='*60}\n")
        log.write(f"自動生成開始: {timestamp}\n")
        log.write(f"モデル: {model}\n")
        log.write(f"{'='*60}\n\n")
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    with open(log_path, 'a', encoding='utf-8') as log_file:
        for i, image_file in enumerate(images, 1):
            print(f"🔄 [{i}/{len(images)}] {image_file.name}...")
            
            result = process_single_image(image_file, json_path, model, overwrite, log_file)
            
            if result == 'success':
                success_count += 1
            elif result == 'skip':
                skip_count += 1
            elif result == 'error':
                error_count += 1
    
    # サマリー
    print(f"\n{'='*60}")
    print(f"🎉 処理完了")
    print(f"   ✅ 成功: {success_count}件")
    print(f"   ⏭️  スキップ: {skip_count}件")
    print(f"   ❌ エラー: {error_count}件")
    print(f"{'='*60}")
    print(f"📄 ログ: {log_path.absolute()}")
    print(f"\n次のステップ: python labeling_tool.py で内容確認・修正")
    
    with open(log_path, 'a', encoding='utf-8') as log:
        log.write(f"完了: 成功 {success_count}件, スキップ {skip_count}件, エラー {error_count}件\n")


if __name__ == "__main__":
    # コマンドライン引数対応
    if len(sys.argv) > 1:
        if sys.argv[1] == "--phase2":
            # Phase 2用（100枚本番データ）
            batch_generate("dataset/images", "dataset/ground_truth")
        elif sys.argv[1] == "--help":
            print("""
使い方:
  python batch_generate_json.py                # Phase 1（テスト5-10枚）
  python batch_generate_json.py --phase2       # Phase 2（本番100枚）
  python batch_generate_json.py --overwrite    # 既存JSON上書き
            """)
            sys.exit(0)
        elif sys.argv[1] == "--overwrite":
            # 上書きモード
            batch_generate("dataset/test_images", "dataset/test_ground_truth", overwrite=True)
        else:
            print("不明な引数です。--help を参照してください")
            sys.exit(1)
    else:
        # デフォルト: Phase 1用（テスト5-10枚）
        batch_generate("dataset/test_images", "dataset/test_ground_truth")
