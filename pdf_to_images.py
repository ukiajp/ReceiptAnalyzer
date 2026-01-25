import os
import fitz  # PyMuPDF
import shutil
from pathlib import Path
from datetime import datetime

def convert_pdfs_to_images(source_folder, output_folder, zoom_level=3.0):
    """
    PDFをJPG画像に変換し、処理結果に応じてPDFを移動
    
    Args:
        source_folder: PDFが入っているフォルダ (例: dataset/pdf)
        output_folder: 画像の保存先 (例: dataset/test_images)
        zoom_level: 拡大倍率（3.0 = 216dpi推奨）
    """
    # パス設定
    src_path = Path(source_folder)
    out_path = Path(output_folder)
    complete_path = src_path / "complete"
    err_path = src_path / "err"
    log_path = src_path.parent / "conversion_log.txt"
    
    # フォルダ作成
    out_path.mkdir(parents=True, exist_ok=True)
    complete_path.mkdir(parents=True, exist_ok=True)
    err_path.mkdir(parents=True, exist_ok=True)

    # PDFファイルを探す（completeとerrフォルダは除外）
    pdf_files = [f for f in src_path.glob("*.pdf") if f.is_file()]
    
    if not pdf_files:
        print(f"⚠️ {source_folder} にPDFファイルが見つかりませんでした。")
        return

    print(f"🔍 {len(pdf_files)}個のPDFが見つかりました。")
    print(f"📐 解像度: {int(72 * zoom_level)} DPI相当")
    print("変換を開始します...\n")

    # ログ開始
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, 'a', encoding='utf-8') as log:
        log.write(f"\n{'='*60}\n")
        log.write(f"変換開始: {timestamp}\n")
        log.write(f"解像度: {int(72 * zoom_level)} DPI\n")
        log.write(f"{'='*60}\n\n")

    success_count = 0
    error_count = 0
    total_images = 0
    
    for pdf_file in pdf_files:
        pdf_success = True
        error_msg = ""
        
        try:
            doc = fitz.open(pdf_file)
            images_created = []
            
            for i, page in enumerate(doc):
                # Vision LLMに最適な解像度（216dpi）
                mat = fitz.Matrix(zoom_level, zoom_level)
                pix = page.get_pixmap(matrix=mat)
                
                # 保存ファイル名
                if doc.page_count == 1:
                    output_filename = f"{pdf_file.stem}.jpg"
                else:
                    output_filename = f"{pdf_file.stem}_p{i+1}.jpg"
                
                save_path = out_path / output_filename
                pix.save(save_path)
                images_created.append(output_filename)
                
                # ファイルサイズ表示
                file_size = save_path.stat().st_size / 1024  # KB
                print(f"✅ {output_filename} ({file_size:.1f} KB)")
                total_images += 1
                
            doc.close()
            
            # 成功: PDFをcompleteフォルダに移動
            dest_path = complete_path / pdf_file.name
            shutil.move(str(pdf_file), str(dest_path))
            success_count += 1
            
            # ログ記録
            with open(log_path, 'a', encoding='utf-8') as log:
                log.write(f"✅ SUCCESS: {pdf_file.name}\n")
                log.write(f"   画像数: {len(images_created)}\n")
                for img in images_created:
                    log.write(f"   - {img}\n")
                log.write(f"   移動先: complete/{pdf_file.name}\n\n")
                
        except Exception as e:
            pdf_success = False
            error_msg = str(e)
            error_count += 1
            
            # エラー: PDFをerrフォルダに移動
            dest_path = err_path / pdf_file.name
            shutil.move(str(pdf_file), str(dest_path))
            
            print(f"❌ エラー ({pdf_file.name}): {error_msg}")
            
            # ログ記録
            with open(log_path, 'a', encoding='utf-8') as log:
                log.write(f"❌ ERROR: {pdf_file.name}\n")
                log.write(f"   原因: {error_msg}\n")
                log.write(f"   移動先: err/{pdf_file.name}\n\n")

    # 完了メッセージ
    print(f"\n{'='*60}")
    print(f"🎉 変換完了")
    print(f"   成功: {success_count}個のPDF → {total_images}枚の画像")
    print(f"   失敗: {error_count}個のPDF")
    print(f"{'='*60}")
    print(f"📁 画像保存先: {out_path.absolute()}")
    print(f"📁 成功PDF: {complete_path.absolute()}")
    if error_count > 0:
        print(f"📁 失敗PDF: {err_path.absolute()}")
    print(f"📄 ログ: {log_path.absolute()}")
    
    # ログ終了
    with open(log_path, 'a', encoding='utf-8') as log:
        log.write(f"完了: 成功 {success_count}件, 失敗 {error_count}件, 画像 {total_images}枚\n")

if __name__ == "__main__":
    # 設定
    pdf_dir = "dataset/pdf"           # PDF読み取り元
    output_dir = "dataset/test_images"  # Phase 1用（5-10枚テスト）
    # output_dir = "dataset/images"    # Phase 2用（100枚本番）← 切り替え可能
    
    # DPI設定
    # zoom=2.0: 144dpi（軽量）
    # zoom=3.0: 216dpi（推奨）
    # zoom=4.0: 288dpi（高精度）
    dpi_zoom = 3.0
    
    convert_pdfs_to_images(pdf_dir, output_dir, zoom_level=dpi_zoom)
