# 環境構築手順（macOS／Windows）

## 1. 実行方式

基本方式は、`sample_asset` repositoryをCloneまたはZIP展開したMac／Windows上でPython／FastAPIとChromaを直接実行し、IBM Cloud上のwatsonx.ai APIへ接続する構成とする。IBM Cloudへアプリケーションをデプロイする必要はない。

| 方式 | 位置付け | 必要なもの |
|---|---|---|
| Python直接実行 + Chroma | 標準・推奨 | uv。Mock確認時はIBM Cloud接続情報不要 |
| Docker／Podman Compose | 任意のMilvus発展構成 | Docker DesktopまたはPodman Desktop |
| Mock／NumPy | test用fallback | IBM Cloud接続情報なし |

## 2. 使用するPython version

本手順ではPython **3.14** を使用する。

## 3. 前提条件と共通の事前準備

### 3.1 端末・ソフトウェア

| 項目 | 必須条件 |
|---|---|
| OS | macOS、または64bit Windows 11 |
| Shell | macOS Terminal、またはWindows PowerShell |
| Git／ZIP | GitでCloneできること。Git未導入の場合はZIP展開で代替可能 |
| Browser | 最新版のChrome、Edge、Firefox、Safariのいずれか |
| 権限 | ユーザー領域へのuv／Python導入と作業directoryへの書込・実行権限 |
| PCリソース | 空き容量10GB以上、メモリ4GB以上を目安とする |
| Port | localhostのTCP 8000番が利用可能であること |

Python、uv、Docker／Podman、Node.jsは事前導入不要である。Python 3.14とuvは本手順内で導入し、Docker／Podmanは任意の発展構成でのみ使用する。

### 3.2 ネットワーク

初回構築では、次へのHTTPS接続を許可する。

- 配布元のGit repository（ZIP配布の場合は不要）
- `https://astral.sh`（uv installer）
- `https://pypi.org`および`https://files.pythonhosted.org`（Python依存関係）
- `https://jp-tok.ml.cloud.ibm.com`（watsonx.ai利用時のみ）

組織Proxy、SSL inspection、PowerShell実行制限がある場合は、セットアップ前に利用環境の管理者へ確認する。

### 3.3 watsonx.ai利用時に必要な情報

次の情報を準備する。

- watsonx.ai URL、Project ID、生成Model ID、Embedding Model ID
- IBM Cloud API Key
- Embedding出力次元

API Keyやpasswordをチャット、Git、画面キャプチャへ含めない。FastAPIが直接接続するのはwatsonx.ai Runtime APIであり、Vector DBには端末上のChromaを使用する。

### 3.4 所要時間

Mock + Chromaの初回起動は30～90分、トラブル対応を含めて2時間以内を目安とする。

| 作業 | 目安 |
|---|---:|
| CloneまたはZIP展開 | 5～10分 |
| uv／Python 3.14導入 | 10～30分 |
| 依存関係導入 | 5～30分 |
| Index構築とMock起動確認 | 5～15分 |
| watsonx.ai接続確認 | 15～30分 |

## 4. macOS

### 4.1 CloneまたはZIP展開

Git repositoryをCloneする場合:

```bash
git clone <repository-url> sample_asset
cd sample_asset
```

ZIPの場合はFinderまたは`unzip sample_asset.zip`で展開し、`sample_asset`へ移動する。アプリケーション、Seed、元Excelはすべてこのディレクトリ内にある。

### 4.2 uvの導入

組織のsoftware配布手順がある場合はそれを優先する。公式installerを使用する場合:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

新しいTerminalを開き、確認する。

```bash
uv --version
uv python install 3.14
```

### 4.3 Mock + Chromaモード起動

repositoryには`data/seed/`と再生成元の`assets/source/business_tools/`が含まれている。通常はSeed再生成を省略できるが、再現性を確認する場合はコメントを外して実行する。

```bash
cp .env.example .env
uv sync --extra dev
# Seedを元Excelから再生成する場合だけ実行
# uv run python backend/scripts/import_business_tools.py export
uv run python backend/scripts/build_index.py
uv run uvicorn helpdesk.main:app --app-dir backend/src --reload --host 127.0.0.1 --port 8000
```

Browserで`http://127.0.0.1:8000`を開く。

### 4.4 watsonx.ai接続

```bash
cp .env.example .env
```

`.env`で`LLM_PROVIDER=watsonx`、`EMBEDDING_PROVIDER=watsonx`、`VECTOR_STORE_PROVIDER=chroma`とし、watsonx.aiの値とEmbedding次元を設定する。ファイル権限を可能な範囲で所有者だけに制限する。

```bash
chmod 600 .env
uv sync --extra watsonx --extra dev
uv run python backend/scripts/build_index.py
uv run uvicorn helpdesk.main:app --app-dir backend/src --host 127.0.0.1 --port 8000
```

別Terminalで確認する。

```bash
curl http://127.0.0.1:8000/api/v1/health/live
curl http://127.0.0.1:8000/api/v1/health/ready
```

## 5. Windows

### 5.1 CloneまたはZIP展開

Git repositoryをCloneするか、Explorerで`sample_asset.zip`の「すべて展開」を選択する。OneDrive配下、空白や日本語を多く含む深いpathを避ける。

Cloneする場合はPowerShellで実行する。

```powershell
git clone <repository-url> C:\work\sample_asset
Set-Location C:\work\sample_asset
```

ZIPの場合は`C:\work\sample_asset`へ展開して同じディレクトリへ移動する。

### 5.2 uvの導入

組織のsoftware配布手順がある場合はそれを優先する。公式installerを使用する場合:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

新しいPowerShellを開き、確認する。

```powershell
uv --version
uv python install 3.14
```

### 5.3 Mock + Chromaモード起動

repositoryには`data/seed/`と再生成元の`assets/source/business_tools/`が含まれている。通常はSeed再生成を省略できるが、再現性を確認する場合はコメントを外して実行する。

```powershell
Copy-Item .env.example .env
uv sync --extra dev
# Seedを元Excelから再生成する場合だけ実行
# uv run python backend/scripts/import_business_tools.py export
uv run python backend/scripts/build_index.py
uv run uvicorn helpdesk.main:app --app-dir backend/src --reload --host 127.0.0.1 --port 8000
```

Browserで`http://127.0.0.1:8000`を開く。

### 5.4 watsonx.ai接続

```powershell
Copy-Item .env.example .env -Force
# .envでwatsonx.aiの値とEMBEDDING_DIMENSIONを設定する
uv sync --extra watsonx --extra dev
uv run python backend/scripts/build_index.py
uv run uvicorn helpdesk.main:app --app-dir backend/src --host 127.0.0.1 --port 8000
```

`.env`は利用者本人と必要な管理者だけが読める場所に置く。確認:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/live
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready
```

### 5.5 セットアップ完了条件

Mac／Windowsともに次をすべて満たすこと。

1. `http://127.0.0.1:8000`でFrontendが表示される。
2. `/api/v1/health/live`がHTTP 200と`status=ok`を返す。
3. `/api/v1/health/ready`がHTTP 200と`status=ready`を返す。
4. ナレッジ検索を実行し、エラーにならず結果が表示される。
5. API KeyがBrowser、画面、ログへ出力されていない。

## 6. 任意のコンテナ実行

Python直接実行ができる場合、Docker／Podmanは必須ではない。利用する場合だけ次を実施する。

Docker:

```bash
docker compose config
docker compose up --build -d
docker compose logs -f app
docker compose down
```

PodmanをmacOS／Windowsで使用する場合は、事前にPodman machineを起動する。

```bash
podman machine init
podman machine start
podman compose config
podman compose up --build -d
```

## 7. Proxy／Firewall

次のOutbound通信を許可する。watsonx.aiのhostは`.env`の`WATSONX_URL`を確認する。

- watsonx.ai: HTTPS／TCP 443
- Python dependency取得: 初回setup時だけPyPI等へのHTTPSが必要

組織Proxyを使用する場合は、資格情報をsourceやREADMEへ書かず、OSまたはprocess環境変数で設定する。

## 8. 終了・削除

1. FastAPIまたはComposeを停止する。
2. `.env`をGitや共有ZIPへ含めない。
3. 使用終了後、不要な`.env`とruntimeデータを削除する。
4. 不要な`data/index/chroma/`を削除し、使用しないAPI Keyを失効する。

## 9. トラブルシューティング

| 症状 | 確認内容 |
|---|---|
| `uv sync`がPython version error | Python 3.14をインストールしているか。`uv python install 3.14`を実行する |
| `/health/ready`が503 | `.env`、Seed、`data/index/chroma/`を確認し、`build_index.py`を再実行 |
| watsonx.aiが401／403 | API Key、Project権限、Project ID、URLを確認 |
| Chromaを開けない | FastAPIを停止し、`data/index/`を再構築。複数processから同時更新しない |
| Browserから開けない | FastAPIが起動し、`127.0.0.1:8000`を使用しているか |
| Windowsでpath error | 短いASCII pathへ展開し直す |

## 10. 公式資料

- [uv installation](https://docs.astral.sh/uv/getting-started/installation/)
- [uv Python installation](https://docs.astral.sh/uv/guides/install-python/)
- [Podman installation](https://podman.io/docs/installation)
