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
        self.root.title("レシート高速アノテーションツール v2.1 (回転・ズーム対応)")
        self.root.geometry("1400x900")

        # 画像リスト取得
        self.image_files = sorted(list(IMAGE_DIR.glob("*.jpg")) + list(IMAGE_DIR.glob("*.png")))
        if not self.image_files:
            messagebox.showerror("エラー", f"{IMAGE_DIR} に画像がありません！")
            root.destroy()
            return
        
        self.current_index = 0
        self.rotation_angle = 0  # 画像回転角度
        self.zoom_level = 1.0    # ズーム倍率
        self.pan_start_x = 0     # パン開始位置
        self.pan_start_y = 0
        self.image_offset_x = 0  # 画像の表示位置オフセット
        self.image_offset_y = 0
        self.image_id = None     # Canvas上の画像ID

        # レイアウト
        self.paned_window = tk.PanedWindow(root, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        # 左側：画像表示
        self.image_frame = tk.Frame(self.paned_window, bg="gray")
        self.paned_window.add(self.image_frame, width=700)
        
        # 画像操作ボタン
        img_controls = tk.Frame(self.image_frame, bg="lightgray")
        img_controls.pack(side=tk.TOP, fill=tk.X)
        tk.Button(img_controls, text="⟲ 左回転", command=self.rotate_left, width=10).pack(side=tk.LEFT, padx=2)
        tk.Button(img_controls, text="⟳ 右回転", command=self.rotate_right, width=10).pack(side=tk.LEFT, padx=2)
        tk.Button(img_controls, text="🔍+ 拡大", command=self.zoom_in, width=8).pack(side=tk.LEFT, padx=2)
        tk.Button(img_controls, text="🔍- 縮小", command=self.zoom_out, width=8).pack(side=tk.LEFT, padx=2)
        tk.Button(img_controls, text="リセット", command=self.reset_view, width=8).pack(side=tk.LEFT, padx=2)
        
        self.canvas = tk.Canvas(self.image_frame, bg="gray")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # マウスホイールでズーム
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        # ドラッグでパン
        self.canvas.bind("<ButtonPress-1>", self.on_pan_start)
        self.canvas.bind("<B1-Motion>", self.on_pan_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_pan_end)

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

        # 税額自動計算ボタン
        tax_calc_frame = tk.Frame(self.input_frame)
        tax_calc_frame.pack(fill="x", pady=10)
        tk.Label(tax_calc_frame, text="税額自動計算:", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        tk.Button(tax_calc_frame, text="全額10%で逆算", command=lambda: self.auto_calc_tax(10), bg="#ffdddd", width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(tax_calc_frame, text="全額8%で逆算", command=lambda: self.auto_calc_tax(8), bg="#ddffdd", width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(tax_calc_frame, text="税クリア", command=self.clear_tax, bg="#eeeeee", width=8).pack(side=tk.LEFT, padx=5)

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
        
        # 画像の回転・ズームをリセット
        self.rotation_angle = 0
        self.zoom_level = 1.0
        self.image_offset_x = 0
        self.image_offset_y = 0
        
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

        # 元画像を保存
        self.original_image = Image.open(img_path)
        
        # 画像表示
        self.display_image()
        
        self.calc_result.config(text="")

    def display_image(self):
        """現在の回転・ズーム設定で画像を表示"""
        if not hasattr(self, 'original_image'):
            return
        
        # 回転
        img = self.original_image.rotate(-self.rotation_angle, expand=True)
        
        # ズーム適用
        canvas_width = self.canvas.winfo_width() or 700
        canvas_height = self.canvas.winfo_height() or 900
        
        # アスペクト比を維持しながらリサイズ
        img.thumbnail((int(canvas_width * self.zoom_level), int(canvas_height * self.zoom_level)), Image.Resampling.LANCZOS)
        
        self.photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        
        # 画像をオフセット位置に配置
        self.image_id = self.canvas.create_image(
            canvas_width//2 + self.image_offset_x, 
            canvas_height//2 + self.image_offset_y, 
            image=self.photo, 
            anchor=tk.CENTER
        )

    def rotate_left(self):
        """左に90度回転"""
        self.rotation_angle = (self.rotation_angle - 90) % 360
        self.display_image()

    def rotate_right(self):
        """右に90度回転"""
        self.rotation_angle = (self.rotation_angle + 90) % 360
        self.display_image()

    def zoom_in(self):
        """拡大"""
        self.zoom_level = min(self.zoom_level * 1.2, 5.0)  # 最大5倍
        self.display_image()

    def zoom_out(self):
        """縮小"""
        self.zoom_level = max(self.zoom_level / 1.2, 0.3)  # 最小0.3倍
        self.display_image()

    def reset_view(self):
        """表示をリセット"""
        self.rotation_angle = 0
        self.zoom_level = 1.0
        self.image_offset_x = 0
        self.image_offset_y = 0
        self.display_image()

    def on_mousewheel(self, event):
        """マウスホイールでズーム"""
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def on_pan_start(self, event):
        """パン開始：マウスクリック位置を記録"""
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self.canvas.config(cursor="fleur")  # 十字カーソルに変更

    def on_pan_move(self, event):
        """パン移動：画像を移動"""
        if self.image_id is None:
            return
        
        # マウスの移動量を計算
        dx = event.x - self.pan_start_x
        dy = event.y - self.pan_start_y
        
        # 画像のオフセットを更新
        self.image_offset_x += dx
        self.image_offset_y += dy
        
        # キャンバス上の画像を移動
        self.canvas.move(self.image_id, dx, dy)
        
        # 次回のために現在位置を記録
        self.pan_start_x = event.x
        self.pan_start_y = event.y

    def on_pan_end(self, event):
        """パン終了：カーソルを元に戻す"""
        self.canvas.config(cursor="")

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

    def auto_calc_tax(self, rate):
        """合計金額から税額を逆算して埋める"""
        import math
        try:
            total_str = self.entries["total"].get().strip().replace(",", "")
            if not total_str:
                messagebox.showwarning("警告", "合計金額を先に入力してください")
                return
            
            total = int(total_str)
            
            # 内税計算: 税額 = 合計 * 税率 / (100 + 税率)  (端数切り捨て)
            tax_amount = math.floor(total * rate / (100 + rate))
            base_amount = total - tax_amount
            
            # フォームにセット
            self.clear_tax() # 一旦クリア
            
            if rate == 10:
                self.entries["tax_10_base"].delete(0, tk.END)
                self.entries["tax_10_base"].insert(0, str(base_amount))
                self.entries["tax_10_amount"].delete(0, tk.END)
                self.entries["tax_10_amount"].insert(0, str(tax_amount))
            else:
                self.entries["tax_8_base"].delete(0, tk.END)
                self.entries["tax_8_base"].insert(0, str(base_amount))
                self.entries["tax_8_amount"].delete(0, tk.END)
                self.entries["tax_8_amount"].insert(0, str(tax_amount))
            
            self.calc_result.config(text=f"✅ {rate}%で自動計算完了 (税抜:{base_amount}円 + 税:{tax_amount}円)", fg="blue")
                
        except ValueError:
            messagebox.showerror("エラー", "合計金額には数値を入力してください")

    def clear_tax(self):
        """税額欄をクリア"""
        for k in ["tax_10_base", "tax_10_amount", "tax_8_base", "tax_8_amount"]:
            self.entries[k].delete(0, tk.END)
            self.entries[k].insert(0, "0")

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
