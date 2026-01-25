import sys
import io
import json
import csv
from pathlib import Path
from datetime import datetime

# Windows環境での文字化け対策
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def clean_amount(amount_str):
    """
    金額文字列を数値に変換（OCR誤認識対応）
    
    Args:
        amount_str: 金額文字列（例: "半2,717", "¥2,717", "2717"）
    
    Returns:
        float: 数値に変換した金額（変換失敗時は0）
    """
    if not amount_str:
        return 0
    
    # 文字列に変換
    if isinstance(amount_str, (int, float)):
        return float(amount_str)
    
    # OCR誤認識文字を削除: 半→¥, ギ→¥, 米→¥
    cleaned = str(amount_str).replace('半', '').replace('ギ', '').replace('米', '')
    # その他の不要文字を削除
    cleaned = cleaned.replace('¥', '').replace('円', '').replace(',', '').strip()
    
    try:
        return float(cleaned)
    except:
        return 0

def determine_account(store_name, payment_method, total):
    """
    店名・支払方法・金額から勘定科目を推定（Phase 1: 簡易ルール）
    
    Args:
        store_name: 店舗名
        payment_method: 支払方法
        total: 合計金額（文字列または数値）
    
    Returns:
        dict: {
            'account': 勘定科目,
            'sub_account': 補助科目,
            'department': 部門,
            'supplier': 取引先
        }
    """
    store_lower = store_name.lower() if store_name else ""
    
    # 金額を数値に変換
    total_amount = clean_amount(total)
    
    # ガソリンスタンドキーワード
    gas_station_keywords = ['eneos', 'エネオス', 'ガソリン', 'レギュラー', 'ハイオク', 
                            '給油', '出光', 'コスモ', 'シェル', 'エッソ', 'モービル',
                            'ネクサスエナジー', '阪神', 'ss', 'ガスステーション']
    # 飲食店キーワード
    restaurant_keywords = ['restaurant', 'cafe', 'bakery', 'ベーカリー', 'カフェ', 'レストラン']
    # コンビニキーワード
    convenience_keywords = ['ローソン', 'セブン', 'ファミマ', 'lawson', 'seven', 'familymart']
    # タクシー・交通系キーワード
    transport_keywords = ['タクシー', '交通', 'taxi', '駅']
    
    # 勘定科目判定（優先順位順に判定）
    account = "会議費"  # デフォルト
    sub_account = ""
    
    # 1. ガソリンスタンド判定（最優先）
    if any(keyword in store_lower for keyword in gas_station_keywords):
        account = "旅費交通費"
        sub_account = "ガソリン代"
    # 2. 飲食店判定
    elif any(keyword in store_lower for keyword in restaurant_keywords):
        if total_amount > 5000:
            account = "交際費"
            sub_account = "飲食費"
        else:
            account = "会議費"
            sub_account = "飲食費"
    # 3. コンビニ判定
    elif any(keyword in store_lower for keyword in convenience_keywords):
        account = "消耗品費"
        sub_account = "事務用品"
    # 4. タクシー・交通系判定
    elif any(keyword in store_lower for keyword in transport_keywords):
        account = "旅費交通費"
        sub_account = "交通費"
    
    return {
        'account': account,
        'sub_account': sub_account,
        'department': "",  # デフォルトは空
        'supplier': store_name
    }

def convert_to_mf_csv(llm_summary_path, output_csv_path="mf_journal_entry.csv"):
    """
    LLMの要約結果をマネーフォワード仕訳CSVに変換
    
    Args:
        llm_summary_path: llm_summary.jsonのパス
        output_csv_path: 出力CSVファイルのパス
    """
    llm_summary_path = Path(llm_summary_path)
    
    if not llm_summary_path.exists():
        print(f"【エラー】{llm_summary_path} が見つかりません")
        return False
    
    # llm_summary.jsonを読み込む
    with open(llm_summary_path, 'r', encoding='utf-8') as f:
        llm_data = json.load(f)
    
    if not llm_data.get('success'):
        print("【エラー】LLM処理が失敗しています")
        return False
    
    parsed_data = llm_data.get('parsed_data')
    if not parsed_data:
        print("【エラー】parsed_dataが見つかりません")
        return False
    
    # データ取得
    store_name = parsed_data.get('store_name', '不明')
    date_str = parsed_data.get('date', '')
    payment_method = parsed_data.get('payment_method', '現金')
    total = parsed_data.get('total')
    tax = parsed_data.get('tax', 0)
    
    # 日付をYYYY/MM/DD形式に変換
    try:
        if date_str:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            transaction_date = date_obj.strftime('%Y/%m/%d')
        else:
            transaction_date = datetime.now().strftime('%Y/%m/%d')
    except:
        transaction_date = datetime.now().strftime('%Y/%m/%d')
    
    # 勘定科目判定
    account_info = determine_account(store_name, payment_method, total)
    
    # 支払方法から貸方勘定科目を決定
    if 'クレジット' in payment_method or 'カード' in payment_method:
        credit_account = "未払金"
        credit_sub_account = "クレジットカード"
    else:
        credit_account = "現金"
        credit_sub_account = ""
    
    # 消費税額の計算（OCR誤認識対応）
    total = clean_amount(total)
    tax = clean_amount(tax)
    
    # 税抜金額を計算
    amount_without_tax = total - tax if tax else total
    
    # 摘要作成
    summary = f"{store_name} {payment_method}"
    
    print("\n" + "="*60)
    print("【マネーフォワード仕訳生成】")
    print("="*60)
    print(f"取引日: {transaction_date}")
    print(f"店舗名: {store_name}")
    print(f"借方科目: {account_info['account']}")
    print(f"貸方科目: {credit_account}")
    print(f"金額: ¥{total:,.0f} (内消費税: ¥{tax:,.0f})")
    print("="*60)
    
    # CSV書き込み
    csv_headers = [
        '取引No', '取引日', '借方勘定科目', '借方補助科目', '借方部門', '借方取引先',
        '借方税区分', '借方インボイス', '借方金額(円)', '借方税額',
        '貸方勘定科目', '貸方補助科目', '貸方部門', '貸方取引先',
        '貸方税区分', '貸方インボイス', '貸方金額(円)', '貸方税額',
        '摘要', '仕訳メモ', 'タグ', 'MF仕訳タイプ', '決算整理仕訳',
        '作成日時', '作成者', '最終更新日時', '最終更新者'
    ]
    
    csv_row = [
        1,  # 取引No
        transaction_date,  # 取引日
        account_info['account'],  # 借方勘定科目
        account_info['sub_account'],  # 借方補助科目
        account_info['department'],  # 借方部門
        account_info['supplier'],  # 借方取引先
        '課税仕入 10%',  # 借方税区分
        '',  # 借方インボイス
        int(total),  # 借方金額(円)
        int(tax) if tax else 0,  # 借方税額
        credit_account,  # 貸方勘定科目
        credit_sub_account,  # 貸方補助科目
        '',  # 貸方部門
        '',  # 貸方取引先
        '対象外',  # 貸方税区分
        '',  # 貸方インボイス
        int(total),  # 貸方金額(円)
        0,  # 貸方税額
        summary,  # 摘要
        '',  # 仕訳メモ
        '',  # タグ
        '',  # MF仕訳タイプ
        '',  # 決算整理仕訳
        '',  # 作成日時
        '',  # 作成者
        '',  # 最終更新日時
        ''   # 最終更新者
    ]
    
    # CSV出力
    try:
        with open(output_csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(csv_headers)
            writer.writerow(csv_row)
    except PermissionError:
        print(f"\n✗ エラー: {output_csv_path} に書き込めません")
        print("   → ファイルがExcel等で開かれている可能性があります")
        print("   → ファイルを閉じてから再実行してください")
        return False
    
    print(f"\n✓ 仕訳CSVを {output_csv_path} に保存しました")
    print("\n【次のステップ】")
    print("1. CSVファイルをマネーフォワードにインポート")
    print("2. 勘定科目・部門を確認して必要に応じて修正")
    print("3. Phase 2でRAG機能を追加して精度向上")
    
    return True

if __name__ == "__main__":
    print("="*60)
    print("=== マネーフォワード仕訳変換プログラム (Phase 1) ===")
    print("="*60)
    print("\n【前提】llm_llama3.2.pyを先に実行して llm_summary.json を生成してください\n")
    
    llm_file = "llm_summary.json"
    
    if not Path(llm_file).exists():
        print(f"【エラー】{llm_file} が見つかりません")
        print("先に以下を実行してください:")
        print("  1. python ocr_paddleocr.py")
        print("  2. python llm_llama3.2.py")
        sys.exit(1)
    
    success = convert_to_mf_csv(llm_file, "mf_journal_entry.csv")
    
    if not success:
        sys.exit(1)
