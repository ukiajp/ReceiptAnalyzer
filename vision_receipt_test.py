import ollama
import json
from pathlib import Path

def extract_receipt_json(image_path):
    """Vision LLMでレシート画像からJSON抽出"""
    
    print(f"画像を解析中: {image_path}")
    
    response = ollama.generate(
        model='llama3.2-vision:11b',
        prompt='''このレシート画像から以下の情報をJSON形式で抽出してください：

{
  "store_name": "店舗名",
  "date": "YYYY-MM-DD",
  "time": "HH:MM",
  "items": [
    {"name": "商品名", "price": 金額（数値）}
  ],
  "total": 合計金額（数値）,
  "tax": 消費税額（数値）,
  "payment_method": "支払方法（現金/クレジット/その他）"
}

【重要】
- 金額は必ず数値型（カンマなし）
- 値引き後の最終金額を抽出
- JSONのみを出力（説明不要）
''',
        images=[str(image_path)],
        options={"temperature": 0.3}
    )
    
    return response['response']


def parse_json_from_response(response_text):
    """LLM出力からJSON部分を抽出"""
    
    # ```json ... ``` の形式を処理
    if '```json' in response_text:
        json_start = response_text.find('```json') + 7
        json_end = response_text.find('```', json_start)
        json_str = response_text[json_start:json_end].strip()
    # { ... } の形式を処理
    elif '{' in response_text:
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        json_str = response_text[json_start:json_end]
    else:
        raise ValueError("JSON形式が見つかりません")
    
    return json.loads(json_str)


def main():
    # テスト画像
    image_path = "sample.jpg"
    
    if not Path(image_path).exists():
        print(f"エラー: {image_path} が見つかりません")
        return
    
    print("=== レシートJSON抽出テスト ===\n")
    
    # 1. Vision LLMで解析
    raw_response = extract_receipt_json(image_path)
    print("--- LLM生出力 ---")
    print(raw_response)
    print()
    
    # 2. JSON解析
    try:
        receipt_data = parse_json_from_response(raw_response)
        
        print("--- 抽出結果 ---")
        print(f"店舗名: {receipt_data['store_name']}")
        print(f"日付: {receipt_data['date']}")
        print(f"時刻: {receipt_data.get('time', '不明')}")
        print(f"合計: ¥{receipt_data['total']:,}")
        print(f"消費税: ¥{receipt_data['tax']}")
        print(f"支払方法: {receipt_data['payment_method']}")
        print(f"\n商品数: {len(receipt_data['items'])}点")
        for item in receipt_data['items']:
            print(f"  - {item['name']}: ¥{item['price']}")
        
        # 3. JSONファイルに保存
        output_path = "vision_result.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(receipt_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ JSONファイルに保存: {output_path}")
        
    except json.JSONDecodeError as e:
        print(f"✗ JSON解析エラー: {e}")
        print("LLM出力を確認してください")
    except Exception as e:
        print(f"✗ エラー: {e}")


if __name__ == "__main__":
    main()
