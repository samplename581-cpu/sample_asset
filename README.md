# Helpdesk RAG 共通基盤

社内ヘルプデスク向け RAG（Retrieval-Augmented Generation）共通基盤 Starter です。
標準構成は、Mac／Windows上でHTML Frontend・Python／FastAPI Backend・Chroma Vector DBを実行し、生成LLMとEmbeddingだけIBM Cloudのwatsonx.aiへ接続する構成です。IBM Cloudへのアプリ配備とwatsonx.dataは必須ではありません。Mock LLM／EmbeddingとNumPy検索は、API Keyなしでの学習・テスト用代替として残しています。

| 項目 | 標準仕様 |
|---|---|
| 言語 | HTML、Python 3.14 |
| フレームワーク | FastAPI |
| LLM／Embedding | Watson Machine Learning（watsonx.ai Runtime）のwatsonx.ai API |
| Project管理 | watsonx.ai Studio |
| Project関連ストレージ | Cloud Object Storage |
| Vector DB | Chroma（ローカル永続DB） |
| アプリ実行場所 | 学生のMac／Windows |
| コンテナ | 任意 |

利用期間は2026年10月10日から12月31日までです。申請対象と数量算定は[IBM Cloud申請・利用見積](./docs/IBM_Cloud申請見積.md)を参照してください。

利用者は8名（4名×2グループ）、IBM Cloudリージョンは東京（`jp-tok`）です。生成ModelとEmbedding Modelは東京リージョンで利用可能なものを選択します。

標準構成のIBM Cloud申請対象は、`Watson Machine Learning（watsonx.ai Runtime）`、`watsonx.ai Studio`、`Cloud Object Storage`です。FastAPIが実行時に直接接続するのはwatsonx.ai Runtimeだけです。watsonx.data／Milvusは、クラウドVector DBも追加検証する場合の任意サービスです。

> ⚠️ **注意**: 本アプリはローカル学習用です。ネットワーク上へ公開しないでください。デフォルトで認証なしで動作します。

---

## Vector DBの選定結果

| 候補 | Mac | Windows | 導入負荷 | 判定 |
|---|---|---|---|---|
| Chroma PersistentClient | 対応 | 対応 | `uv sync`だけ。別server不要 | **標準採用** |
| Milvus Lite | 対応 | Windows nativeは公式対応外 | WindowsではLinux／containerが必要 | 標準不採用 |
| Milvus Standalone | containerで対応 | Docker Desktop／WSL 2が必要 | 学習用PCには構成が重い | 発展用途 |
| NumPy検索 | 対応 | 対応 | 最軽量だがVector DBではない | test用fallback |

ChromaはApache 2.0のOSSで、`PersistentClient`がDBを`data/index/chroma/`へ自動永続化します。Embedding生成はChromaへ任せず、既存のMock／ローカルモデル／watsonx.ai Adapterで生成したVectorを登録します。

- [Chroma PersistentClient](https://docs.trychroma.com/docs/run-chroma/cloud-client?lang=python)
- [Chroma Python package](https://pypi.org/project/chromadb/)
- [Milvus Lite supported environments](https://milvus.io/docs/milvus_lite.md)

## セットアップの前提条件

Mock + Chromaでの初回起動は**30～90分、トラブル対応を含めて2時間以内**を目安とします。watsonx.aiのサービス作成や社内ソフトウェア申請は、この時間に含みません。運営担当は演習開始前に申請と資格情報の配布を完了してください。

### 必須

| 項目 | 前提条件・確認内容 |
|---|---|
| OS | 組織でサポートされているmacOS、または64bit Windows 11 |
| Shell | macOS Terminal、またはWindows PowerShell |
| Git／ZIP | GitでCloneできること。Gitがない場合はZIPを展開できればよい |
| Browser | 最新版のChrome、Edge、Firefox、Safariのいずれか |
| ネットワーク | 初回構築時にGit repository、`astral.sh`、PyPI、`files.pythonhosted.org`へHTTPS接続できること |
| 権限 | ユーザー領域へのuv／Python導入と、Clone先へのファイル作成・実行が許可されていること |
| PCリソース | 空き容量1GB以上、メモリ4GB以上を目安とする |
| Port | localhostのTCP 8000番が他processに使用されていないこと |

Python、uv、Docker／Podman、Node.jsの事前インストールは不要です。Python 3.14とuvは以下の手順で導入します。Docker／Podmanは任意の発展構成でのみ使用します。

### watsonx.aiを利用する場合のみ必要

| 項目 | 運営担当から受領する値 |
|---|---|
| watsonx.ai Runtime | 東京リージョンで利用可能なProjectとサービス |
| 認証 | IBM Cloud API Key、Project ID、watsonx.ai URL |
| Model | 生成Model ID、Embedding Model ID、Embedding出力次元 |
| ネットワーク | `https://jp-tok.ml.cloud.ibm.com`へのHTTPS／TCP 443接続 |

API KeyなしでもMock + Chromaで画面、Ticket API、Vector検索、回答下書き生成を確認できます。組織Proxy、SSL inspection、PowerShell実行制限、ソフトウェア導入申請がある場合は、演習日前に運営担当へ確認してください。

### 所要時間の目安

| 作業 | 目安 |
|---|---:|
| CloneまたはZIP展開 | 5～10分 |
| uv／Python 3.14導入 | 10～30分 |
| Python依存関係導入 | 5～30分 |
| Chroma Index構築 | 1～5分 |
| Mock起動・画面確認 | 5～10分 |
| watsonx.ai設定・接続確認 | 15～30分 |

## 最短セットアップ（API Keyなし）

### macOS（Terminal）

```bash
git clone <repository-url> sample_asset
cd sample_asset
curl -LsSf https://astral.sh/uv/install.sh | sh
# uvを認識させるため、新しいTerminalで同じdirectoryへ移動する
uv python install 3.14
cp .env.example .env
uv sync --extra dev
uv run python backend/scripts/build_index.py
uv run uvicorn helpdesk.main:app --app-dir backend/src --reload --host 127.0.0.1 --port 8000
```

### Windows（PowerShell）

GitでCloneするか、`sample_asset.zip`をExplorerの「すべて展開」で`C:\work\sample_asset`などの短いpathへ展開します。

```powershell
git clone <repository-url> C:\work\sample_asset
Set-Location C:\work\sample_asset
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# uvを認識させるため、新しいPowerShellを開いてから次を実行する
uv python install 3.14
Copy-Item .env.example .env
uv sync --extra dev
uv run python backend/scripts/build_index.py
uv run uvicorn helpdesk.main:app --app-dir backend/src --reload --host 127.0.0.1 --port 8000
```

起動後、ブラウザで `http://127.0.0.1:8000` を開くと最小 UI が表示されます。

Gitを使わずZIPから開始する場合も、展開後の`sample_asset`ディレクトリで同じコマンドを実行します。元ExcelからSeed JSONを再生成する場合は、同梱された`assets/source/`を使用して次を実行します。

```bash
uv run python backend/scripts/export_seed_data.py
uv run python backend/scripts/build_index.py
```

### セットアップ完了条件

次をすべて満たせばローカル環境構築は完了です。

- `http://127.0.0.1:8000`で画面が表示される
- `GET /api/v1/health/live`がHTTP 200と`{"status":"ok"}`を返す
- `GET /api/v1/health/ready`がHTTP 200と`{"status":"ready", ...}`を返す
- ナレッジ検索でエラーにならず検索結果が表示される
- Terminal／PowerShellにAPI Keyやstack traceが表示されていない

macOS:

```bash
curl http://127.0.0.1:8000/api/v1/health/live
curl http://127.0.0.1:8000/api/v1/health/ready
```

Windows PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/live
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready
```

---

## 実行モード

配布直後の`.env.example`は、Mock LLM／EmbeddingとローカルChromaで安全に動作確認できる設定です。本演習の標準は、ローカルFastAPI／Chromaからwatsonx.aiを利用する構成です。

| 環境変数 | デフォルト | 説明 |
|---|---|---|
| `LLM_PROVIDER` | `mock` | 標準は`watsonx`、ローカル確認は`mock`。`openai_compatible`は発展課題用 |
| `EMBEDDING_PROVIDER` | `mock` | `mock` / `local` / `watsonx` |
| `EMBEDDING_DIMENSION` | `64` | 利用するEmbedding modelと一致させる |
| `VECTOR_STORE_PROVIDER` | `chroma` | `chroma`（標準）/ `numpy`（test）/ `milvus`（任意） |
| `CHROMA_COLLECTION` | `helpdesk_knowledge` | ローカルcollection名 |

## watsonx.aiへ接続する標準起動

LLMとEmbeddingにwatsonx.ai、Vector DBにローカルChromaを使用します。ChromaにAPI Keyやpasswordは不要です。

`.env.example`を`.env`へコピーし、次の値を変更します。API KeyはBrowserやFrontendへ渡さず、FastAPI processだけが読み取ります。

```dotenv
LLM_PROVIDER=watsonx
EMBEDDING_PROVIDER=watsonx
VECTOR_STORE_PROVIDER=chroma
WATSONX_URL=https://jp-tok.ml.cloud.ibm.com
WATSONX_PROJECT_ID=運営担当から受領した値
WATSONX_API_KEY=運営担当から受領した値
WATSONX_MODEL_ID=使用する生成モデルID
WATSONX_EMBEDDING_MODEL_ID=使用するEmbeddingモデルID
EMBEDDING_DIMENSION=使用するEmbeddingモデルの出力次元
```

設定後、Chromaを同じEmbedding modelで再構築してから起動します。

```bash
uv sync --extra watsonx --extra dev
uv run python backend/scripts/build_index.py
uv run uvicorn helpdesk.main:app --app-dir backend/src --host 127.0.0.1 --port 8000
```

起動確認:

```bash
curl http://127.0.0.1:8000/api/v1/health/ready
```

### 任意のIBM Cloud Milvus／コンテナ検証

現在の`compose.yaml`は、発展構成としてwatsonx.data Milvusへ接続する場合の定義です。ローカルChromaの標準手順にはDocker／Podmanは不要です。利用する場合だけ`.env.container.example`から`.env`を作成し、Docker／Podmanを起動します。

```bash
# .env設定後

# Docker
docker compose config
docker compose up --build -d

# Podmanの場合
podman compose config
podman compose up --build -d
```

設定ファイル名を変える場合は、`APP_ENV_FILE=.env.container` のように指定できます。`compose.yaml`はこのファイルをコンテナの環境変数として読み込みます。

停止:

```bash
docker compose down
# または podman compose down
```

API KeyやMilvus passwordはDockerfile、compose.yaml、Gitへ記録しません。本構成の詳細は`docs/要件定義書.md`と`docs/構成設計書.md`を参照してください。

JSON Ticket Repositoryを使うMVPはUvicorn workerを1に固定します。`VECTOR_MIN_SCORE=0.45`は調整開始値であり、45%の正答率や確率を意味しません。Embedding modelと評価データごとに調整してください。

### テスト用ローカルEmbeddingを使う場合

```bash
uv sync --extra local-embedding --extra dev
# .env を編集して EMBEDDING_PROVIDER=local, EMBEDDING_DIMENSION=384 に変更
make index   # インデックスを再構築
make dev
```

Embedding provider、model、出力次元のいずれかを変更した場合は、必ず`build_index.py`を再実行してください。登録時と検索時で異なるEmbedding設定を使用してはいけません。

---

## 動作確認コマンド

```bash
# ヘルスチェック
curl http://127.0.0.1:8000/api/v1/health/live
# → {"status":"ok"}

curl http://127.0.0.1:8000/api/v1/health/ready
# → {"status":"ready","checks":{...}}

# チケット一覧
curl "http://127.0.0.1:8000/api/v1/tickets?limit=5"

# チケット作成
curl -X POST http://127.0.0.1:8000/api/v1/tickets \
  -H "Content-Type: application/json" \
  -d '{"title":"VPN接続できない","description":"在宅勤務中にVPNが使えません","requester_department":"営業部"}'

# ナレッジ検索
curl -X POST http://127.0.0.1:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query":"パスワードリセット方法","top_k":3}'

# 回答下書き生成（RAG + LLM）
curl -X POST http://127.0.0.1:8000/api/v1/answers/draft \
  -H "Content-Type: application/json" \
  -d '{"question":"VPNに接続できません","top_k":3}'
```

---

## テスト・Lint・型チェック

```bash
make test        # pytest (unit / contract / integration)
make lint        # ruff --fix
make typecheck   # mypy
```

個別実行:

```bash
uv run pytest backend/tests/unit -v
uv run pytest backend/tests/contract -v
uv run pytest backend/tests/integration -v
```

---

## ディレクトリ構成

```
sample_asset/
├── .env.example          # 環境変数テンプレート（デフォルト: Mock モード）
├── .env.container.example # 任意のwatsonx.ai + IBM Cloud Milvus検証用
├── .env                  # 実行時設定（gitignore）
├── Dockerfile            # 非rootのアプリケーション image
├── compose.yaml          # Docker / Podman共通の起動定義
├── pyproject.toml        # プロジェクト設定・依存定義
├── uv.lock               # 依存バージョン固定
├── Makefile              # setup / seed / index / dev / test / lint / typecheck
├── assets/
│   └── source/           # Seed再生成用Excel（架空教材データ）
│       ├── helpdesk_tickets.xlsx
│       ├── helpdesk_documents.xlsx
│       └── helpdesk_master.xlsx
├── openapi/
│   └── helpdesk-api.yaml # OpenAPI 3.1 仕様書
├── frontend/             # ビルド不要の最小 UI（HTML + CSS + JS）
│   ├── index.html
│   ├── style.css
│   └── app.js
├── data/
│   ├── seed/             # 元データ（tickets.json, tickets_student.json, documents.json, masters.json）
│   ├── runtime/          # 実行時チケットデータ（gitignore）
│   ├── index/            # ベクトルインデックス（gitignore）
│   └── evaluation/       # 正解ラベル – 学生に配布しないこと
│       └── ticket_gold.json
└── backend/
    ├── scripts/
    │   ├── export_seed_data.py  # Excel → seed JSON（学生用と評価用を分離して出力）
    │   └── build_index.py       # documents.json → ベクトルインデックス
    ├── src/helpdesk/
    │   ├── main.py        # FastAPI アプリケーション（Frontend 配信含む）
    │   ├── config.py      # pydantic-settings（watsonx 使用時の必須チェック含む）
    │   ├── domain/        # モデル・エラー定義（extra=forbid）
    │   ├── ports/         # LLMPort / EmbeddingPort / VectorStorePort / TicketRepository
    │   ├── adapters/      # JSON, Chroma/NumPy/Milvus, Mock/watsonx/OpenAI-compatible LLM・Embedding
    │   ├── services/      # TicketService / RagService（draft_answer 含む）
    │   └── api/           # FastAPI ルーター（health / tickets / masters / rag）
    └── tests/
        ├── conftest.py         # 共通フィクスチャ（Mock モード固定・一時ディレクトリ）
        ├── test_api.py         # API smoke tests
        ├── unit/               # モデル / config / ticket_json / vector_chroma / rag_service
        ├── contract/           # OpenAPI 契約テスト
        └── integration/        # /answers/draft エンドポイント E2E
```

---

## Git公開・学生配布時の注意

`sample_asset`単体をGit repositoryまたはZIPとして配布します。`assets/source/`の元Excelと`data/evaluation/`には正解ラベルが含まれるため、学生から閲覧可能です。これらは自己評価用教材として扱い、ブラインド評価用データには使用しません。非公開評価が必要な場合は、このrepository外で管理してください。

| ファイル | 配布可否 |
|---|---|
| `assets/source/*.xlsx` | ✅ Seed再生成用。正解ラベルを含む教材 |
| `data/seed/tickets_student.json` | ✅（正解ラベルなし） |
| `data/seed/tickets.json` | ✅ 正解ラベルを含む教材 |
| `data/evaluation/ticket_gold.json` | ✅ 自己評価用として扱う |
| `.env`、API Key、更新済みruntime、cache | ❌ ZIP作成時に除外する |

### ZIP作成時の除外必須ファイル

`.gitignore` はZIP作成時に自動適用されません。ZIP化の前に以下を必ず除外してください。現在の`sample_asset/`には`.venv/`だけで約300MB弱あります。

```text
.env
.venv/
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
data/runtime/*  （.gitkeep は残してよい）
*.log
.DS_Store
```

ZIP作成例（`sample_asset`の親ディレクトリで実行）:

```bash
zip -r sample_asset.zip sample_asset/ \
  -x "**/.git/*" \
  -x "**/.env" \
  -x "**/.venv/*" \
  -x "**/__pycache__/*" \
  -x "**/.pytest_cache/*" \
  -x "**/.mypy_cache/*" \
  -x "**/.ruff_cache/*" \
  -x "**/data/runtime/*" \
  -x "**/*.log" \
  -x "**/.DS_Store"
```

Cloneまたは展開後に、repository外のファイルを参照せず`uv sync`、`make seed`、`make index`、`make dev`を実行できることを、配布前に別端末で必ず確認してください。

---

## LLM プロバイダーの切り替え

学生向け標準手順では`watsonx`を使用し、IBM Cloudを利用できない確認・テスト時だけ`mock`を使用します。`openai_compatible`はAdapter拡張例として残しますが、標準セットアップの選択肢には含めません。

| `LLM_PROVIDER` | 必要な設定 |
|---|---|
| `mock` (デフォルト) | なし |
| `watsonx` | `WATSONX_URL`, `WATSONX_PROJECT_ID`, `WATSONX_API_KEY`, `WATSONX_MODEL_ID` |
| `openai_compatible` | `OPENAI_COMPATIBLE_BASE_URL`, `OPENAI_COMPATIBLE_MODEL_ID` |

---

## エラーレスポンス形式（RFC 9457）

```json
{
  "type": "https://helpdesk.example.com/problems/not-found",
  "title": "Not Found",
  "status": 404,
  "detail": "Ticket with ID 'TKT-99999999' not found",
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

| HTTP | エラー種別 |
|---|---|
| 404 | `NotFoundError` |
| 409 | `ConflictError`（version 衝突） |
| 422 | バリデーション失敗（余分フィールドも 422） |
| 503 | `ProviderError`、RAG インデックス未構築 |
