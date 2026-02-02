"""
ハイブリッド構成レシート解析ツール
- Google Vision API: OCR（文字認識）
- llama3.2:3b: 構造化（意味理解とJSON生成）
"""

import os
import json
import time
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from google.cloud import vision
from google.cloud.vision_v1 import AnnotateImageResponse
import ollama
from json_repair import repair_json
import tkinter as tk
from tkinter import filedialog, messagebox

from config import Config
from utils.logger import setup_logger

# ロガー設定
logger = setup_logger(__name__, Config.LOG_LEVEL, Config.LOG_FILE)

def setup_google_credentials() -> None:
    """
    Google Cloud認証情報を設定
    
    Raises:
        SystemExit: 認証情報ファイルが見つからない場合
    """
    credentials_path = Config.GOOGLE_CREDENTIALS_PATH
    
    if not Path(credentials_path).exists():
        logger.error(f"認証情報ファイルが見つかりません: {credentials_path}")
        logger.error("Google Cloud Console から認証情報JSONをダウンロードしてください")
        sys.exit(1)
    
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    logger.info(f"認証情報読み込み完了: {credentials_path}")


def extract_text_with_vision_api(image_path: str) -> Tuple[str, float]:
    """
    Google Vision APIでOCR実行
    
    Args:
        image_path: 画像ファイルのパス
    
    Returns:
        (テキストデータ, 処理時間)のタプル
    
    Raises:
        FileNotFoundError: 画像ファイルが見つからない場合
        Exception: Vision APIエラーまたはテキスト検出失敗
    """
    logger.info(f"画像読み込み開始: {image_path}")
    
    if not Path(image_path).exists():
        raise FileNotFoundError(f"画像ファイルが見つかりません: {image_path}")
    
    start_time = time.time()
    
    try:
        # Vision APIクライアント作成
        client = vision.ImageAnnotatorClient()
        
        # 画像読み込み
        with open(image_path, 'rb') as image_file:
            content = image_file.read()
        
        image = vision.Image(content=content)
        
        # OCR実行
        response: AnnotateImageResponse = client.text_detection(image=image)
        texts = response.text_annotations
        
        if response.error.message:
            error_msg = f'Google Vision API Error: {response.error.message}'
            logger.error(error_msg)
            raise Exception(error_msg)
        
        if not texts:
            error_msg = 'テキストが検出されませんでした'
            logger.warning(error_msg)
            raise Exception(error_msg)
        
        # 最初の要素が全文テキスト
        full_text = texts[0].description
        
        elapsed = time.time() - start_time
        
        logger.info(f"OCR完了: {elapsed:.2f}秒, 抽出文字数: {len(full_text)}文字")
        
        return full_text, elapsed
        
    except Exception as e:
        logger.error(f"OCRエラー: {e}", exc_info=True)
        raise


def structure_with_local_llm(
    ocr_text: str, 
    model: str = Config.DEFAULT_LLM_MODEL
) -> Tuple[Dict[str, Any], float, str]:
    """
    ローカルLLMでテキストを構造化してJSON生成
    
    Args:
        ocr_text: OCR抽出テキスト
        model: 使用するLLMモデル
    
    Returns:
        (JSON辞書, 処理時間, 生出力)のタプル
    
    Raises:
        json.JSONDecodeError: JSON解析エラー
        Exception: LLM処理エラー
    """
    logger.info(f"LLMで構造化開始 (モデル: {model})")
    
    # シンプルで高速なプロンプト（以前の成功パターンを採用）
    prompt = f"""以下のレシートOCRテキストから、必要な情報を抽出してJSON形式で出力してください。

OCRテキスト:
{ocr_text}

出力形式：
{{
  "store": "店舗名",
  "date": "YYYY-MM-DD",
  "time": "HH:MM",
  "total": 合計金額（数値のみ）,
  "tax_10_base": 10%対象金額（数値、なければ0）,
  "tax_10_amount": 10%消費税額（数値、なければ0）,
  "tax_8_base": 8%対象金額（数値、なければ0）,
  "tax_8_amount": 8%消費税額（数値、なければ0）,
  "invoice_number": "インボイス登録番号（Tから始まる13桁、なければnull）",
  "payment_method": "支払方法（現金/クレジット/電子マネー等）",
  "items": [
    {{"name": "商品名", "price": 単価（数値）}}
  ]
}}

注意事項：
- 「合計」ラベルの近くの金額を合計として抽出
- 金額は数値型で出力（カンマなし）
- JSONのみを出力（説明不要）
"""
    
    start_time = time.time()
    
    try:
        response = ollama.chat(
            model=model,
            messages=[{
                'role': 'user',
                'content': prompt
            }],
            options={
                "temperature": Config.LLM_TEMPERATURE,
                "num_predict": 512  # 出力トークン数を制限して高速化
            }
        )
        
        raw_output = response['message']['content']
        elapsed = time.time() - start_time
        
        logger.info(f"LLM処理完了: {elapsed:.2f}秒")
        
        # デバッグ用：生出力を保存（設定で有効化されている場合）
        if Config.SAVE_RAW_OUTPUT:
            output_file = Config.OUTPUT_DIR / 'llm_raw_output.txt'
            Config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(raw_output)
            logger.debug(f"LLM生出力を保存: {output_file}")
        
        # JSON抽出
        json_data = parse_json_from_response(raw_output)
        
        return json_data, elapsed, raw_output
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析エラー: {e}")
        if Config.SAVE_RAW_OUTPUT:
            logger.info(f"LLM生出力を {Config.OUTPUT_DIR / 'llm_raw_output.txt'} に保存しました")
        raise
    except Exception as e:
        logger.error(f"LLMエラー: {e}", exc_info=True)
        raise


def normalize_numeric_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    JSONデータの数値フィールドを数値型に変換
    
    Args:
        data: JSON辞書
    
    Returns:
        数値フィールドが正規化された辞書
    """
    numeric_fields = ['total', 'tax_10_base', 'tax_10_amount', 'tax_8_base', 'tax_8_amount']
    
    for field in numeric_fields:
        if field in data:
            value = data[field]
            if isinstance(value, str):
                try:
                    # 文字列から数値に変換（カンマや空白を除去）
                    cleaned = value.replace(',', '').replace(' ', '').strip()
                    data[field] = int(cleaned) if cleaned else 0
                except (ValueError, AttributeError):
                    data[field] = 0
    
    # items配列のpriceも変換
    if 'items' in data and isinstance(data['items'], list):
        for item in data['items']:
            if 'price' in item and isinstance(item['price'], str):
                try:
                    cleaned = item['price'].replace(',', '').replace(' ', '').strip()
                    item['price'] = int(cleaned) if cleaned else 0
                except (ValueError, AttributeError):
                    item['price'] = 0
    
    return data


def parse_json_from_response(response_text: str) -> Dict[str, Any]:
    """
    LLM出力からJSON部分を抽出し、多少の壊れがあっても修復して読み込む
    
    Args:
        response_text: LLMの生出力テキスト
    
    Returns:
        パースされたJSON辞書
    
    Raises:
        json.JSONDecodeError: JSON解析・修復に失敗した場合
    """
    logger.debug("JSON解析と修復を試みます...")
    
    try:
        # 1. まずはMarkdownの```json ... ``` を剥がす
        clean_text = response_text
        if '```json' in clean_text:
            clean_text = clean_text.split('```json')[1].split('```')[0]
        elif '```' in clean_text:
            clean_text = clean_text.split('```')[1].split('```')[0]
        
        # 2. 余計な説明文が前後についている場合、最初の { から 最後の } までを切り抜く
        start = clean_text.find('{')
        end = clean_text.rfind('}') + 1
        if start != -1 and end != -1:
            clean_text = clean_text[start:end]

        # 3. json_repairを使って、カンマ漏れや閉じ忘れを強力に修復してロード
        # これが標準の json.loads よりも圧倒的に頑丈です
        json_data = json.loads(repair_json(clean_text))
        
        # 4. 数値フィールドを数値型に変換（LLMが文字列で返す場合があるため）
        json_data = normalize_numeric_fields(json_data)
        
        logger.debug("JSON解析成功")
        return json_data

    except Exception as e:
        logger.error("JSON解析失敗 (修復不能)")
        logger.debug(f"LLMの生出力:\n{response_text}")
        raise json.JSONDecodeError(f"JSON解析に失敗しました: {e}", response_text, 0) from e


def hybrid_receipt_extraction(image_path: str) -> Dict[str, Any]:
    """
    ハイブリッド構成でレシート解析
    
    Args:
        image_path: レシート画像パス
    
    Returns:
        解析結果を含む辞書:
        - data: JSON辞書
        - timings: 処理時間詳細
        - raw_ocr: OCR生テキスト
        - raw_llm: LLM生出力
    """
    logger.info("="*60)
    logger.info("🚀 ハイブリッド構成レシート解析")
    logger.info("="*60)
    logger.info(f"📐 構成: Google Vision API (OCR) + {Config.DEFAULT_LLM_MODEL} (構造化)")
    
    total_start = time.time()
    
    # Step 1: Google Vision APIでOCR
    ocr_text, ocr_time = extract_text_with_vision_api(image_path)
    
    logger.debug("="*60)
    logger.debug("📄 OCR結果（抜粋）")
    logger.debug("="*60)
    logger.debug(ocr_text[:300] + ("..." if len(ocr_text) > 300 else ""))
    
    # Step 2: ローカルLLMで構造化
    json_data, llm_time, raw_output = structure_with_local_llm(ocr_text)
    
    total_time = time.time() - total_start
    
    # 結果表示
    logger.info("="*60)
    logger.info("✅ 解析結果")
    logger.info("="*60)
    logger.info(json.dumps(json_data, ensure_ascii=False, indent=2))
    
    logger.info("="*60)
    logger.info("⏱️  処理時間")
    logger.info("="*60)
    logger.info(f"OCR (Google Vision API): {ocr_time:.2f}秒")
    logger.info(f"構造化 ({Config.DEFAULT_LLM_MODEL}):     {llm_time:.2f}秒")
    logger.info(f"合計:                     {total_time:.2f}秒")
    logger.info("="*60)
    
    return {
        'data': json_data,
        'timings': {
            'ocr': ocr_time,
            'llm': llm_time,
            'total': total_time
        },
        'raw_ocr': ocr_text,
        'raw_llm': raw_output
    }


def select_images_gui() -> Optional[List[str]]:
    """
    GUIで画像ファイルを選択（複数選択可能）
    
    Returns:
        選択された画像パスのリスト、キャンセル時はNone
    """
    root = tk.Tk()
    root.withdraw()  # メインウィンドウを非表示
    
    try:
        file_paths = filedialog.askopenfilenames(
            title="レシート画像を選択（複数選択可）",
            filetypes=[
                ("画像ファイル", "*.jpg *.jpeg *.png"),
                ("JPEG", "*.jpg *.jpeg"),
                ("PNG", "*.png"),
                ("すべてのファイル", "*.*")
            ],
            initialdir=str(Config.TEST_IMAGES_DIR) if Config.TEST_IMAGES_DIR.exists() else None
        )
        
        if file_paths:
            return list(file_paths)
        else:
            return None
    except Exception as e:
        logger.error(f"ファイル選択エラー: {e}")
        return None
    finally:
        root.destroy()


def show_results_gui(results: List[Dict[str, Any]], output_files: List[str]) -> None:
    """
    処理結果をGUIで表示
    
    Args:
        results: 処理結果のリスト
        output_files: 生成されたJSONファイルのパスリスト
    """
    root = tk.Tk()
    root.withdraw()  # メインウィンドウを非表示
    
    success_count = sum(1 for r in results if r.get('success', False))
    error_count = len(results) - success_count
    
    # 結果メッセージ作成
    message = f"処理完了！\n\n"
    message += f"✅ 成功: {success_count}枚\n"
    message += f"❌ 失敗: {error_count}枚\n\n"
    
    if output_files:
        message += "生成されたファイル:\n"
        for file_path in output_files[:10]:  # 最大10件まで表示
            message += f"  • {Path(file_path).name}\n"
        if len(output_files) > 10:
            message += f"  ... 他 {len(output_files) - 10}件\n"
    
    messagebox.showinfo("処理完了", message)
    root.destroy()


def main() -> None:
    """メイン処理"""
    
    # 設定の検証とディレクトリ作成
    Config.ensure_directories()
    
    # 画像リスト取得
    image_paths: List[str] = []
    
    if len(sys.argv) > 1:
        # コマンドライン引数で画像パス指定（1枚のみ）
        image_paths = [sys.argv[1]]
        # 単一画像指定の場合は、画像ディレクトリのチェックをスキップ
        config_errors = Config.validate(check_images_dir=False)
    else:
        # GUIでファイル選択
        logger.info("GUIで画像ファイルを選択してください...")
        image_paths = select_images_gui()
        
        if not image_paths:
            logger.info("ファイル選択がキャンセルされました")
            sys.exit(0)
        
        logger.info(f"選択された画像: {len(image_paths)}枚")
        # GUI選択の場合は、画像ディレクトリのチェックをスキップ
        config_errors = Config.validate(check_images_dir=False)
    
    # 設定エラーのチェック（認証情報は必須）
    if config_errors:
        for error in config_errors:
            logger.error(error)
        # 認証情報エラーのみで終了、画像ディレクトリエラーは警告のみ
        if any("Google認証情報" in e for e in config_errors):
            sys.exit(1)
    
    # 認証設定
    setup_google_credentials()
    
    # バッチ処理
    results: List[Dict[str, Any]] = []
    output_files: List[str] = []
    success_count = 0
    error_count = 0
    total_ocr_time = 0.0
    total_llm_time = 0.0
    
    for idx, image_path in enumerate(image_paths, 1):
        image_path_obj = Path(image_path)
        if not image_path_obj.exists():
            logger.error(f"画像ファイルが見つかりません: {image_path}")
            error_count += 1
            continue
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📷 [{idx}/{len(image_paths)}] {image_path_obj.name}")
        logger.info(f"{'='*60}")
        
        try:
            # ハイブリッド解析実行
            result = hybrid_receipt_extraction(str(image_path_obj))
            
            # 結果保存先をtest_ground_truthに変更
            json_filename = image_path_obj.stem + '.json'
            
            # test_ground_truthフォルダに保存
            output_dir = Config.TEST_GROUND_TRUTH_DIR
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / json_filename
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result['data'], f, ensure_ascii=False, indent=2)
            
            logger.info(f"💾 結果保存: {output_path}")
            output_files.append(str(output_path))
            
            # 統計情報の更新
            success_count += 1
            total_ocr_time += result['timings']['ocr']
            total_llm_time += result['timings']['llm']
            
            results.append({
                'image': image_path_obj.name,
                'success': True,
                'timings': result['timings'],
                'store': result['data'].get('store', 'N/A'),
                'total': result['data'].get('total', 0)
            })
            
        except Exception as e:
            logger.error(f"エラーが発生しました: {e}", exc_info=True)
            error_count += 1
            results.append({
                'image': image_path_obj.name,
                'success': False,
                'error': str(e)
            })
    
    # サマリー表示
    logger.info(f"\n\n{'='*60}")
    logger.info("📊 バッチ処理サマリー")
    logger.info(f"{'='*60}")
    logger.info(f"処理枚数: {len(image_paths)}枚")
    logger.info(f"✅ 成功: {success_count}枚")
    logger.info(f"❌ 失敗: {error_count}枚")
    
    if success_count > 0:
        avg_ocr = total_ocr_time / success_count
        avg_llm = total_llm_time / success_count
        avg_total = (total_ocr_time + total_llm_time) / success_count
        
        logger.info(f"\n⏱️  平均処理時間:")
        logger.info(f"  OCR (Google Vision API): {avg_ocr:.2f}秒")
        logger.info(f"  構造化 ({Config.DEFAULT_LLM_MODEL}):     {avg_llm:.2f}秒")
        logger.info(f"  合計:                     {avg_total:.2f}秒")
        
        if avg_total <= 8:
            logger.info(f"\n🎉 目標達成！ 平均{avg_total:.2f}秒で完了（目標: 2〜8秒）")
        else:
            logger.warning(f"\n⚠️  目標未達: 平均{avg_total:.2f}秒（目標: 2〜8秒）")
    
    # 結果一覧
    logger.info(f"\n📋 処理結果一覧:")
    for r in results:
        if r['success']:
            # totalが文字列の場合も数値に変換してからフォーマット
            total_value = r.get('total', 0)
            if isinstance(total_value, str):
                try:
                    total_value = int(total_value)
                except (ValueError, TypeError):
                    total_value = 0
            logger.info(f"  ✅ {r['image']}: {r['store']} (¥{total_value:,}) - {r['timings']['total']:.2f}秒")
        else:
            logger.error(f"  ❌ {r['image']}: {r['error']}")
    
    logger.info(f"{'='*60}\n")
    
    # GUIで結果を表示（コマンドライン引数がない場合のみ）
    if len(sys.argv) == 1 and output_files:
        show_results_gui(results, output_files)
        
        # 確認・修正ウィンドウを起動するか確認
        root_confirm = tk.Tk()
        root_confirm.withdraw()
        
        response = messagebox.askyesno(
            "確認・修正",
            "レシートデータを確認・修正しますか？\n\n"
            "「はい」を選択すると、画像を見ながら手動で修正できるウィンドウが開きます。"
        )
        root_confirm.destroy()
        
        if response:
            # labeling_tool.pyを起動
            import subprocess
            try:
                labeling_tool_path = Path(__file__).parent / "labeling_tool.py"
                if labeling_tool_path.exists():
                    subprocess.Popen([
                        sys.executable,
                        str(labeling_tool_path)
                    ])
                    logger.info("確認・修正ウィンドウを起動しました")
                else:
                    logger.warning(f"labeling_tool.pyが見つかりません: {labeling_tool_path}")
            except Exception as e:
                logger.error(f"確認・修正ウィンドウの起動に失敗しました: {e}")
                root_error = tk.Tk()
                root_error.withdraw()
                messagebox.showerror("エラー", f"確認・修正ウィンドウを起動できませんでした:\n{e}")
                root_error.destroy()
        
        # 確認・修正ウィンドウを起動するか確認
        root = tk.Tk()
        root.withdraw()
        
        response = messagebox.askyesno(
            "確認・修正",
            "レシートデータを確認・修正しますか？\n\n"
            "「はい」を選択すると、画像を見ながら手動で修正できるウィンドウが開きます。"
        )
        root.destroy()
        
        if response:
            # labeling_tool.pyを起動
            import subprocess
            try:
                subprocess.Popen([
                    sys.executable,
                    str(Path(__file__).parent / "labeling_tool.py")
                ])
                logger.info("確認・修正ウィンドウを起動しました")
            except Exception as e:
                logger.error(f"確認・修正ウィンドウの起動に失敗しました: {e}")
                messagebox.showerror("エラー", f"確認・修正ウィンドウを起動できませんでした:\n{e}")


if __name__ == "__main__":
    main()
