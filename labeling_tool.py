"""
レシート高速アノテーションツール（改良版）
- 軽減税率対応（10%/8%内訳）
- 商品価格入力対応
- 自動検算機能
"""

import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import json
from pathlib import Path

# --- 設定 ---
IMAGE_DIR = Path("dataset/test_images")  # Phase 1用
JSON_DIR = Path("dataset/test_ground_truth")
JSON_DIR.mkdir(parents=True, exist_ok=True)

class AnnotationTool:
    def __init__(self, root):
        self.root = root
        self.root.title("レシート高速アノテーションツール v2.0")
        self.root.geometry("1400x900")

        # 画像リスト取得
        self.image_files = sorted(list(IMAGE_DIR.glob("*.jpg")) + list(IMAGE_DIR.glob("*.png")))
        if not self.image_files:
            messagebox.showerror("エラー", f"{IMAGE_DIR} に画像がありません！")
            root.destroy()
            return
        
        self.current_index = 0

        # レイアウト
        self.paned_window = tk.PanedWindow(root, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        # 左側：画像表示
        self.image_frame = tk.Frame(self.paned_window, bg="gray")
        self.paned_window.add(self.image_frame, width=700)
        
        self.canvas = tk.Canvas(self.image_frame, bg="gray")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 右側：入力フォーム
        self.input_frame = tk.Frame(self.paned_window, padx=20, pady=20)
        self.paned_window.add(self.input_frame, width=600)

        self.create_form()
        self.load_image()

    def create_form(self):
        # ファイル名表示
        self.filename_label = tk.Label(
            self.input_frame, 
            text="", 
            font=("Arial", 14, "bold"),
            fg="blue"
        )
        self.filename_label.pack(pady=10)

        # 基本情報セクション
        self.create_section("基本情報", [
            ("store", "店舗名"),
            ("date", "日付 (YYYY-MM-DD)"),
            ("time", "時刻 (HH:MM)"),
        ])

        # 金額セクション
        self.create_section("金額情報", [
            ("total", "合計金額"),
            ("tax_10_base", "10%対象額"),
            ("tax_10_amount", "10%消費税"),
            ("tax_8_base", "8%対象額（なければ0）"),
            ("tax_8_amount", "8%消費税（なければ0）"),
        ])

        # その他
        self.create_section("その他", [
            ("invoice_number", "インボイス番号 (T...)"),
            ("payment_method", "支払方法（現金/クレジット/電子マネー等）"),
        ])

        # 商品リスト
        tk.Label(
            self.input_frame, 
            text="商品リスト（商品名:金額 の形式、改行区切り）",
            font=("Arial", 10, "bold")
        ).pack(fill="x", pady=(10, 0))
        
        tk.Label(
            self.input_frame, 
            text="例: 透明絶景カレンダー:1650",
            font=("Arial", 9),
            fg="gray"
        ).pack(fill="x")
        
        self.item_text = tk.Text(self.input_frame, height=6, font=("Arial", 10))
        self.item_text.pack(fill="x", pady=(0, 10))

        # 検算結果表示
        self.calc_result = tk.Label(
            self.input_frame, 
            text="", 
            font=("Arial", 10),
            fg="green"
        )
        self.calc_result.pack(fill="x", pady=5)

        # ボタン
        btn_frame = tk.Frame(self.input_frame)
        btn_frame.pack(fill="x", pady=20)
        
        tk.Button(btn_frame, text="<< 前へ", command=self.prev_image, width=10).pack(side=tk.LEFT)
        tk.Button(
            btn_frame, 
            text="検算", 
            command=self.validate_calculations,
            bg="#ffffcc",
            width=10
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            btn_frame, 
            text="保存して次へ >>", 
            command=self.save_and_next, 
            bg="#ccffcc", 
            height=2,
            width=15
        ).pack(side=tk.LEFT, expand=True, fill="x", padx=10)
        tk.Button(btn_frame, text="次へ(保存なし)", command=self.next_image, width=12).pack(side=tk.RIGHT)

    def create_section(self, title, fields):
        """セクション作成"""
        tk.Label(
            self.input_frame, 
            text=title, 
            font=("Arial", 11, "bold")
        ).pack(fill="x", pady=(10, 5))
        
        for key, label_text in fields:
            lbl = tk.Label(self.input_frame, text=label_text, anchor="w")
            lbl.pack(fill="x")
            entry = tk.Entry(self.input_frame, font=("Arial", 10))
            entry.pack(fill="x", pady=(0, 5))
            
            if not hasattr(self, 'entries'):
                self.entries = {}
            self.entries[key] = entry

    def load_image(self):
        if not self.image_files: 
            return
        
        img_path = self.image_files[self.current_index]
        self.filename_label.config(
            text=f"{self.current_index + 1}/{len(self.image_files)}: {img_path.name}"
        )
        
        # 既存JSONロード
        json_path = JSON_DIR / f"{img_path.stem}.json"
        existing_data = {}
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
            except:
                pass

        # フォームにセット
        for key, entry in self.entries.items():
            entry.delete(0, tk.END)
            val = existing_data.get(key, "")
            if val is None: 
                val = ""
            entry.insert(0, str(val))
        
        # 商品リスト
        self.item_text.delete("1.0", tk.END)
        items = existing_data.get("items", [])
        if items:
            lines = [f"{item['name']}:{item['price']}" for item in items]
            self.item_text.insert("1.0", "\n".join(lines))

        # 画像表示
        img = Image.open(img_path)
        img.thumbnail((700, 900))
        self.photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(350, 450, image=self.photo, anchor=tk.CENTER)
        
        self.calc_result.config(text="")

    def validate_calculations(self):
        """検算機能"""
        try:
            total = int(self.entries["total"].get())
            tax_10_base = int(self.entries["tax_10_base"].get() or 0)
            tax_10_amount = int(self.entries["tax_10_amount"].get() or 0)
            tax_8_base = int(self.entries["tax_8_base"].get() or 0)
            tax_8_amount = int(self.entries["tax_8_amount"].get() or 0)
            
            # 計算チェック
            calc_total = tax_10_base + tax_10_amount + tax_8_base + tax_8_amount
            
            if calc_total == total:
                self.calc_result.config(text="✅ 検算OK！", fg="green")
            else:
                self.calc_result.config(
                    text=f"⚠️ 不一致: 計算={calc_total}, 記載={total}",
                    fg="red"
                )
        except ValueError:
            self.calc_result.config(text="⚠️ 数値を入力してください", fg="orange")

    def save_and_next(self):
        """保存して次へ"""
        try:
            data = {}
            
            # 基本データ収集
            for key, entry in self.entries.items():
                val = entry.get().strip()
                
                if key in ["total", "tax_10_base", "tax_10_amount", "tax_8_base", "tax_8_amount"]:
                    data[key] = int(val) if val else 0
                elif key == "invoice_number" and not val:
                    data[key] = None
                else:
                    data[key] = val
            
            # 商品リスト解析
            items_raw = self.item_text.get("1.0", tk.END).strip()
            items = []
            for line in items_raw.split("\n"):
                line = line.strip()
                if not line:
                    continue
                
                if ":" in line:
                    name, price = line.rsplit(":", 1)
                    items.append({
                        "name": name.strip(),
                        "price": int(price.strip())
                    })
                else:
                    items.append({
                        "name": line,
                        "price": 0
                    })
            
            data["items"] = items
            
            # 保存
            img_path = self.image_files[self.current_index]
            save_path = JSON_DIR / f"{img_path.stem}.json"
            
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 保存: {save_path.name}")
            self.next_image()

        except Exception as e:
            messagebox.showerror("エラー", f"保存失敗:\n{e}")

    def next_image(self):
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.load_image()
        else:
            messagebox.showinfo("完了", "最後の画像です！")

    def prev_image(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.load_image()

if __name__ == "__main__":
    root = tk.Tk()
    app = AnnotationTool(root)
    root.mainloop()
