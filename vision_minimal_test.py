import ollama
from pathlib import Path

# 画像パス（同じフォルダにsample.jpgがある想定）
image_path = "sample.jpg"

print(f"画像を読み込み中: {image_path}")
print("llama3.2-vision:11bで解析中...\n")

# Vision LLMで画像解析
response = ollama.generate(
    model='llama3.2-vision:11b',
    prompt='この画像には何が写っていますか？レシートであれば、店舗名・日付・金額を抽出してください。',
    images=[image_path]
)

print("=== llama3.2-vision:11b出力 ===")
print(response['response'])
print("\n処理完了")