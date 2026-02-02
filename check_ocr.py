from google.cloud import vision
import os
import sys

# UTF-8出力に設定
sys.stdout.reconfigure(encoding='utf-8')

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'google-credentials.json'
client = vision.ImageAnnotatorClient()

with open('dataset/test_images/レシート画像2.jpg', 'rb') as f:
    content = f.read()

image = vision.Image(content=content)
response = client.text_detection(image=image)
text = response.text_annotations[0].description

# ファイルに保存
with open('ocr_result.txt', 'w', encoding='utf-8') as f:
    f.write(text)

print("OCR結果をocr_result.txtに保存しました")
