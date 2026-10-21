# Helpdesk RAG Starter

ヘルプデスクの問い合わせに対して、関連文書を検索し、回答案を生成するRAGアプリケーションです。

- Frontend: HTML / CSS / JavaScript
- Backend: Python 3.14 / FastAPI
- Vector DB: Chroma（ローカル保存）
- LLM / Embedding: watsonx.ai、または動作確認用Mock

最初はAPI Key不要のMock構成で起動します。起動を確認した後、必要に応じてwatsonx.aiへ切り替えてください。

> このアプリケーションはローカル開発用です。`127.0.0.1`のまま起動し、ネットワークへ公開しないでください。

## 1. 前提条件

| 項目 | 条件 |
|---|---|
| OS | macOS、または64bit Windows 11 |
| Terminal | macOS Terminal、またはWindows PowerShell |
| Git／ZIP | GitでCloneできること。Gitを使わない場合はZIPを展開できること |
| Browser | Chrome、Edge、Firefox、Safariのいずれか |
| Network | Git repository、`astral.sh`、PyPIへHTTPS接続できること |
| PC | 空き容量1GB以上、メモリ4GB以上 |
| Port | TCP 8000番が空いていること |

Python、uv、Docker、Node.jsの事前インストールは不要です。セットアップの目安は30～90分です。

## 2. セットアップ

### macOS（Terminal）

repositoryの画面にある「Code」からClone URLを取得し、次の`<repository-url>`へ指定します。

```bash
git clone <repository-url> ~/sample_asset
cd ~/sample_asset
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Terminalを開き直してから、Cloneしたディレクトリへ移動して続けます。

```bash
cd ~/sample_asset
uv python install 3.14
cp .env.example .env
uv sync
uv run python backend/scripts/build_index.py
uv run uvicorn helpdesk.main:app --app-dir backend/src --reload --host 127.0.0.1 --port 8000
```

### Windows（PowerShell）

repositoryの画面にある「Code」からClone URLを取得し、次の`<repository-url>`へ指定します。

```powershell
git clone <repository-url> C:\work\sample_asset
Set-Location C:\work\sample_asset
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

PowerShellを開き直してから続けます。

```powershell
Set-Location C:\work\sample_asset
uv python install 3.14
Copy-Item .env.example .env
uv sync
uv run python backend/scripts/build_index.py
uv run uvicorn helpdesk.main:app --app-dir backend/src --reload --host 127.0.0.1 --port 8000
```

Gitを利用しない場合は、repositoryをZIPでダウンロードし、`C:\work\sample_asset`など日本語や空白を含まない短いパスへ展開してください。展開後は`uv python install 3.14`以降を実行します。

## 3. 起動確認

サーバーを起動したまま、ブラウザで次を開きます。

- アプリケーション: <http://127.0.0.1:8000>
- API仕様・試行画面: <http://127.0.0.1:8000/docs>

画面からナレッジ検索を実行し、検索結果が表示されることを確認してください。初期設定では、回答案に`[MOCK]`と表示されます。

macOSでは別のTerminalで確認できます。

```bash
curl http://127.0.0.1:8000/api/v1/health/live
curl http://127.0.0.1:8000/api/v1/health/ready
```

Windowsでは別のPowerShellで確認できます。

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/live
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready
```

次の両方が返ればセットアップ完了です。

- `/health/live`: `status`が`ok`
- `/health/ready`: HTTP 200かつ`status`が`ready`

サーバーは、起動したTerminalまたはPowerShellで`Ctrl+C`を押すと停止します。

## 4. watsonx.aiへの切り替え

watsonx.aiを利用する場合は、管理者から次の値を受け取ってください。

- Project ID
- IBM Cloud API Key
- watsonx.ai URL
- 生成モデルID
- EmbeddingモデルIDと出力次元

依存関係を追加します。

```bash
uv sync --extra watsonx
```

`.env`の次の項目を編集します。

```dotenv
LLM_PROVIDER=watsonx
EMBEDDING_PROVIDER=watsonx
VECTOR_STORE_PROVIDER=chroma
WATSONX_URL=https://jp-tok.ml.cloud.ibm.com
WATSONX_PROJECT_ID=<Project ID>
WATSONX_API_KEY=<API Key>
WATSONX_MODEL_ID=<生成モデルID>
WATSONX_EMBEDDING_MODEL_ID=<EmbeddingモデルID>
EMBEDDING_DIMENSION=<Embeddingの出力次元>
```

`.env`はGitへ登録しないでください。API KeyはFrontendへ記載せず、Terminalやチャットにも貼り付けないでください。

Embeddingを変更したため、インデックスを再構築してから起動します。

```bash
uv run python backend/scripts/build_index.py
uv run uvicorn helpdesk.main:app --app-dir backend/src --reload --host 127.0.0.1 --port 8000
```

## 5. アプリケーション構成

```text
Browser
  └─ frontend/                 画面
       ↓ HTTP / JSON
FastAPI
  └─ backend/src/helpdesk/
       ├─ api/                 APIの入口
       ├─ services/            Ticket・RAG処理
       ├─ ports/               外部サービスのインターフェース
       └─ adapters/            Chroma・watsonx.ai・Mockの実装
            ↓
data/seed/                     初期データ・検索文書
data/index/chroma/             Chromaインデックス（自動生成）
```

主なAPIは次のとおりです。

| API | 用途 |
|---|---|
| `GET /api/v1/tickets` | チケット一覧 |
| `POST /api/v1/search` | 関連文書のVector検索 |
| `POST /api/v1/answers/draft` | 検索結果を使用した回答案生成 |
| `GET /api/v1/health/ready` | 起動準備状態の確認 |

画面の使い方は[GUI操作ガイド](./docs/GUI_USER_GUIDE.md)、詳細なAPIは起動後の`/docs`を参照してください。

## 6. 開発時の基本操作

```bash
make dev        # アプリケーション起動
make index      # Chromaインデックス再構築
make test       # テスト
make lint       # Lintと自動修正
make typecheck  # 型チェック
```

`make`が利用できないWindows環境では、対応するコマンドを直接実行してください。

```powershell
uv run uvicorn helpdesk.main:app --app-dir backend/src --reload --host 127.0.0.1 --port 8000
uv run python backend/scripts/build_index.py
uv run pytest backend/tests
uv run ruff check backend/src backend/scripts backend/tests --fix
uv run mypy backend/src --ignore-missing-imports
```

テスト・Lint・型チェック用の依存関係が未導入の場合は、先に次を実行します。

```bash
uv sync --extra dev
```

## 7. トラブルシューティング

| 症状 | 対応 |
|---|---|
| `uv`が見つからない | Terminal／PowerShellを開き直す |
| 8000番Portを使用できない | 既に起動しているアプリを停止する |
| `/health/ready`が503 | `.env`を確認し、サーバー停止後に`build_index.py`を再実行する |
| Chromaを開けない | 複数のFastAPI processを停止し、インデックスを再構築する |
| watsonx.ai接続に失敗する | URL、Project ID、モデルIDを確認する。API Keyは画面やログへ出力しない |

Mac／Windows別の補足は[環境構築手順](./docs/環境構築手順_Mac_Windows.md)を参照してください。

## 8. （オプション）検索文書再構築手順

RAGの検索対象は`data/seed/documents.json`です。検索文書を追加・変更した場合は、Chromaインデックスを再構築します。

### JSONを直接編集する場合

1. 起動中のサーバーを`Ctrl+C`で停止します。
2. `data/seed/documents.json`を編集します。
3. 次のコマンドでインデックスを再構築します。
4. サーバーを起動し、変更した文書を検索できることを確認します。

```bash
uv run python backend/scripts/build_index.py
uv run uvicorn helpdesk.main:app --app-dir backend/src --reload --host 127.0.0.1 --port 8000
```

文書は次の形式で追加します。`document_id`は重複させず、既存文書を更新するときは同じIDを維持してください。

```json
{
  "document_id": "faq:vpn-01",
  "title": "VPNに接続できない場合",
  "body": "ネットワーク接続を確認し、VPNクライアントを再起動してください。",
  "document_type": "faq",
  "source": "internal-helpdesk",
  "category": "技術的障害",
  "updated_at": "2026-10-21",
  "access_scope": "student",
  "is_active": true
}
```

削除する文書は、履歴を残す場合は`is_active`を`false`にします。

### Excelを正本として編集する場合

`assets/source/helpdesk_documents.xlsx`を編集した後、次を実行します。

```bash
uv run python backend/scripts/export_seed_data.py
uv run python backend/scripts/build_index.py
```

`export_seed_data.py`は検索文書だけでなく、`assets/source/`にあるTicketとMasterのExcelから対応するSeed JSONも再生成します。意図しない上書きを避けるため、実行前に差分をCommitするかバックアップしてください。GitでCloneした場合は、実行後に`git diff -- data/seed data/evaluation`で変更内容を確認します。

## 9. （オプション）拡張構成

- Docker／Podman: `Dockerfile`と`compose.yaml`
- IBM Cloud Milvus: `.env.container.example`
- ローカルEmbedding: `uv sync --extra local-embedding`
- 構成・設計の詳細: [構成設計書](./docs/構成設計書.md)、[要件定義書](./docs/要件定義書.md)

これらは初回セットアップには不要です。
