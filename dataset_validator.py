"""
データセット検証ツール
- 画像とJSONの対応チェック
- JSON必須フィールドチェック
- 金額計算の整合性チェック
"""

import json
from pathlib import Path

# 必須フィールド定義
REQUIRED_FIELDS = {
    "metadata": ["image_file", "created_at"],
    "receipt": [
        "store_name",
        "date",
        "items",
        "total"
    ]
}

def validate_json_structure(json_data, filename):
    """JSON構造の検証"""
    errors = []
    
    # メタデータチェック
    if "metadata" not in json_data:
        errors.append(f"{filename}: 'metadata'セクションがありません")
    else:
        for field in REQUIRED_FIELDS["metadata"]:
            if field not in json_data["metadata"]:
                errors.append(f"{filename}: metadata.{field} が欠落")
    
    # レシートデータチェック
    if "receipt" not in json_data:
        errors.append(f"{filename}: 'receipt'セクションがありません")
    else:
        for field in REQUIRED_FIELDS["receipt"]:
            if field not in json_data["receipt"]:
                errors.append(f"{filename}: receipt.{field} が欠落")
        
        # items配列チェック
        if "items" in json_data["receipt"]:
            items = json_data["receipt"]["items"]
            if not isinstance(items, list) or len(items) == 0:
                errors.append(f"{filename}: itemsが空です")
            else:
                for i, item in enumerate(items):
                    if "name" not in item:
                        errors.append(f"{filename}: items[{i}].name が欠落")
                    if "total_price" not in item:
                        errors.append(f"{filename}: items[{i}].total_price が欠落")
    
    return errors

def validate_calculations(json_data, filename):
    """金額計算の整合性チェック"""
    errors = []
    
    if "receipt" not in json_data:
        return errors
    
    receipt = json_data["receipt"]
    
    # 商品合計チェック
    if "items" in receipt and "subtotal" in receipt:
        items_total = sum(item.get("total_price", 0) for item in receipt["items"])
        if items_total != receipt["subtotal"]:
            errors.append(
                f"{filename}: 商品合計({items_total})と小計({receipt['subtotal']})が不一致"
            )
    
    # 消費税チェック
    if all(k in receipt for k in ["tax_10_base", "tax_10_amount", "tax_8_base", "tax_8_amount", "total"]):
        calculated_total = (
            receipt["tax_10_base"] + receipt["tax_10_amount"] +
            receipt["tax_8_base"] + receipt["tax_8_amount"]
        )
        if calculated_total != receipt["total"]:
            errors.append(
                f"{filename}: 計算合計({calculated_total})と記載合計({receipt['total']})が不一致"
            )
    
    return errors

def validate_dataset(dataset_dir, ground_truth_dir):
    """データセット全体の検証"""
    
    dataset_path = Path(dataset_dir)
    gt_path = Path(ground_truth_dir)
    
    print(f"📊 データセット検証開始")
    print(f"   画像: {dataset_path}")
    print(f"   JSON: {gt_path}\n")
    
    # 画像ファイル一覧
    images = list(dataset_path.glob("*.jpg"))
    
    if not images:
        print("⚠️ 画像ファイルが見つかりません")
        return
    
    total_errors = 0
    valid_count = 0
    
    for image_file in images:
        json_file = gt_path / f"{image_file.stem}.json"
        
        # 1. 対応するJSONの存在チェック
        if not json_file.exists():
            print(f"❌ {image_file.name}: 対応するJSONファイルがありません")
            total_errors += 1
            continue
        
        # 2. JSON読み込み
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ {json_file.name}: JSON解析エラー - {e}")
            total_errors += 1
            continue
        
        # 3. 構造検証
        structure_errors = validate_json_structure(json_data, json_file.name)
        
        # 4. 計算検証
        calc_errors = validate_calculations(json_data, json_file.name)
        
        # 5. 結果表示
        all_errors = structure_errors + calc_errors
        if all_errors:
            print(f"⚠️ {image_file.name}:")
            for error in all_errors:
                print(f"   - {error}")
            total_errors += len(all_errors)
        else:
            print(f"✅ {image_file.name}: OK")
            valid_count += 1
    
    # サマリー
    print(f"\n{'='*60}")
    print(f"検証完了: {len(images)}ファイル")
    print(f"  ✅ 正常: {valid_count}件")
    print(f"  ⚠️ エラー: {total_errors}件")
    print(f"{'='*60}")

if __name__ == "__main__":
    # Phase 1データセット検証
    validate_dataset("dataset/test_images", "dataset/test_ground_truth")
    
    # Phase 2データセット検証（作成後）
    # validate_dataset("dataset/images", "dataset/ground_truth")
