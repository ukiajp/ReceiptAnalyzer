import ollama
import json

def test_engine(image_path):
    """ollama.chat()を使った改善版"""
    
    model = 'llama3.2-vision:11b'  # 実際に動作するモデル
    
    # シンプルなプロンプト（素のモデルの実力測定用）
    prompt = """このレシート画像から以下の情報をJSON形式で抽出してください。

出力形式：
{
  "store": "店舗名",
  "date": "YYYY-MM-DD",
  "total": 合計金額（数値のみ、カンマなし）,
  "tax": 消費税額（数値のみ）,
  "items": ["商品名1", "商品名2"]
}

注意事項：
- 金額は数値型で出力（例: 2717 not "2,717"）
- JSONのみを出力（説明文不要）
- 値引き後の最終支払額を使用
"""

    print(f"画像解析中: {image_path}")
    print(f"モデル: {model}\n")
    
    response = ollama.chat(
        model=model,
        messages=[{
            'role': 'user', 
            'content': prompt, 
            'images': [image_path]
        }],
        options={"temperature": 0.1}  # 低温度で安定出力
    )

    raw_output = response['message']['content']
    print("=== LLM生出力 ===")
    print(raw_output)
    print()
    
    # JSON抽出
    try:
        if '```json' in raw_output:
            json_str = raw_output.split('```json')[1].split('```')[0].strip()
        elif '{' in raw_output:
            json_start = raw_output.find('{')
            json_end = raw_output.rfind('}') + 1
            json_str = raw_output[json_start:json_end]
        else:
            raise ValueError("JSON形式が見つかりません")
        
        data = json.loads(json_str)
        
        print("=== 抽出成功 ===")
        print(f"店舗: {data['store']}")
        print(f"日付: {data['date']}")
        print(f"合計: ¥{data['total']:,}")
        print(f"消費税: ¥{data['tax']}")
        print(f"商品: {', '.join(data['items'])}")
        
        # 保存
        with open('vision_chat_result.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("\n✓ vision_chat_result.json に保存")
        
    except Exception as e:
        print(f"✗ JSON解析エラー: {e}")

if __name__ == "__main__":
    import sys
    
    # コマンドライン引数で画像パス指定可能
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        image_path = "sample.jpg"  # デフォルト
    
    test_engine(image_path)
