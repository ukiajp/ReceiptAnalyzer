# セットアップガイド

## 仮想環境の作成とセットアップ

### ステップ1: 仮想環境の作成

PowerShellまたはコマンドプロンプトで以下を実行：

```powershell
cd c:\Users\ukyas\dev\ReceiptAnalyzer
python -m venv venv
```

### ステップ2: 仮想環境の有効化

**PowerShellの場合：**
```powershell
.\venv\Scripts\Activate.ps1
```

もし実行ポリシーのエラーが出る場合：
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\venv\Scripts\Activate.ps1
```

**コマンドプロンプト（cmd）の場合：**
```cmd
venv\Scripts\activate.bat
```

**Git Bashの場合：**
```bash
source venv/Scripts/activate
```

### ステップ3: pipのアップグレード

```powershell
python -m pip install --upgrade pip
```

### ステップ4: 依存関係のインストール

```powershell
pip install -r requirements.txt
```

または、個別にインストール：

```powershell
pip install json-repair python-dotenv google-cloud-vision ollama pillow
```

### ステップ5: 動作確認

```powershell
python -c "import json_repair; print('OK')"
python -c "import google.cloud.vision; print('OK')"
python -c "import ollama; print('OK')"
```

## テスト実行

### 単一画像のテスト

```powershell
python google_vision_hybrid.py "dataset/test_images/レシート画像1.jpg"
```

### バッチ処理（全画像）

```powershell
python google_vision_hybrid.py
```

## 仮想環境の無効化

作業が終わったら：

```powershell
deactivate
```

## トラブルシューティング

### 仮想環境が作成できない場合

- Pythonが正しくインストールされているか確認：`python --version`
- 管理者権限で実行してみる
- 既存の`venv`フォルダを削除してから再作成

### 依存関係のインストールエラー

- インターネット接続を確認
- pipをアップグレード：`python -m pip install --upgrade pip`
- 個別にインストールしてエラーを特定

### 仮想環境が有効化できない場合（PowerShell）

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

を実行してから再度試す
