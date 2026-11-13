# Helpdesk RAG Starter

> **【インターン用コンテンツ】**
> このリポジトリは、IBMのインターンシップ（FDE体験）で参加者が使用する教材・サンプルアセットです。**インターン参加者向けに作成したものであり、IBMの製品、サービス、公式サンプルではありません。** 内容は予告なく変更・削除することがあります。
>
> - 登場する会社名、商品名、人名、注文番号、問い合わせ内容は**すべて架空**です。実在の顧客データは含みません。
> - 本番環境での利用、実データの投入は想定していません。
> - 認証情報（API Key、Project IDなど）はこのリポジトリに含まれていません。各自で受け取った値を、自分の`.env`にだけ設定してください。
> - インターンの参加者以外の方は、参照のみとしてください。サポートは提供していません。

ヘルプデスクの問い合わせに対して、関連文書を検索し、回答案を生成するRAGアプリケーションです。

- Frontend: HTML / CSS / JavaScript
- Backend: Python 3.14 / FastAPI
- Vector DB: Chroma（ローカル保存）
- LLM / Embedding: watsonx.ai、または動作確認用Mock

最初はAPI Key不要のMock構成で起動します。起動を確認した後、必要に応じてwatsonx.aiへ切り替えてください。

> このアプリケーションはローカル開発用です。`127.0.0.1`のまま起動し、ネットワークへ公開しないでください。

## リポジトリの内容

このリポジトリには、アプリのソースコードに加えて、インターンの進め方を説明する資料と、AIコーディングエージェント（IBM Bob）の設定例が入っています。目的に合う項目を選んで参照してください。

### 目的別の入口

| やりたいこと | 見る場所 |
|---|---|
| 開発環境をつくる（Bobのサインインを含む） | [IBMBob開発環境構築手順](./Day2開発案内/IBMBob開発環境構築手順.md) → [環境構築手順（Mac／Windows）](./Day2開発案内/環境構築手順_Mac_Windows.md) |
| このアプリで何ができるかを知る | [サンプルアセットアプリ紹介](./Day2開発案内/サンプルアセットアプリ紹介.md) |
| 開発の進め方と考え方を知る | [開発方針](./Day2開発案内/開発方針.pdf)（PPTX版: [開発方針.pptx](./Day2開発案内/開発方針.pptx)） |
| アプリを起動して動かす | このREADMEの[1. 前提条件](#1-前提条件)〜[3. 起動確認](#3-起動確認)、画面の使い方は[GUI操作ガイド](./Day2開発案内/GUI_USER_GUIDE.md) |
| AI駆動開発とIBM Bobの使い方を学ぶ | [Day3講座資料](./Day3開発案内/Day3_AI駆動開発とIBMBob講座.pptx) |
| 業務観察で作ったソリューション案を、Bobと一緒に具体化する | [FDE開発キット](./fde_bob_kit/README.md) |
| アプリを改造・拡張する | このREADMEの[5. アプリケーション構成](#5-アプリケーション構成)と[8. 検索文書再構築手順](#8-オプション検索文書再構築手順) |
| 検索対象の文書やデータを差し替える | `assets/source/business_tools/`（Excelの正本）と`data/seed/`（生成されるJSON） |

### フォルダの構成

```text
sample_asset/
├── README.md               このファイル（概要・セットアップ）
├── Day2開発案内/            環境構築・アプリ紹介・開発方針・GUI操作ガイド・画面イメージ（helpdesk-rag.html）
├── Day3開発案内/            AI駆動開発とIBM Bobの講座資料（PPTX）
├── fde_bob_kit/            Bob用のスキル・カスタムモードの例と、導入手順
├── backend/                サーバー側（Python / FastAPI）
│   ├── src/helpdesk/         アプリ本体（api / services / ports / adapters / domain）
│   ├── scripts/              インデックス構築、Excel取り込みのスクリプト
│   └── tests/                テスト（unit / integration / contract）
├── frontend/               画面（HTML / CSS / JavaScript）
├── openapi/                API仕様（helpdesk-api.yaml）
├── assets/source/business_tools/  架空の業務ツール（FAQ回答集、分類基準表、問い合わせ管理シート、問い合わせフォーム）
├── data/seed/              検索文書・チケット・マスタの初期データ（Excelから生成）
├── picture/                環境構築手順で使う画面キャプチャ
├── pyproject.toml, uv.lock 依存関係（uvで管理）
├── Makefile                開発用コマンドの短縮
├── .env.example            設定の見本（秘密値は空。実際の値は`.env`に書き、Gitに登録しない）
└── Dockerfile, compose.yaml  任意のローカルコンテナ実行（初回は不要）
```

### 想定している進め方

1. **業務観察**: 架空の問い合わせ業務を観察し、課題を見つける。
2. **ソリューション案づくり**: 課題を解く案を考え、評価して絞り込む。
3. **環境構築**: Bobをインストールし、サインインする。リポジトリをCloneして、Mockで起動する。
4. **開発**: Bobを使って、サンプルアセットを土台に（または別の構成で）アプリをつくる。
5. **定着と振り返り**: 現場で使われ続ける形にし、学びをまとめる。

> サンプルアセットの利用は必須ではありません。グループの案に合う部分だけを使い、合わない場合は別の構成・言語を選んでかまいません。

### 扱いの注意

- **GitHub Enterprise上で参加者に共有するリポジトリです。** 社内の情報、実在の個人情報、認証情報を、コミット・Issue・Pull Requestに書かないでください。
- 資料（`Day2開発案内/`、`Day3開発案内/`）には、IBM社内でのみ開けるリンクが含まれる場合があります。参加者以外は開けません。
- ライセンスは設定していません。インターン以外での再利用や再配布は、想定していません。

## 1. 前提条件

| 項目 | 条件 |
|---|---|
| OS | macOS、または64bit Windows 11 |
| Terminal | macOS Terminal、またはWindows PowerShell |
| Git／ZIP | GitでCloneできること。Gitを使わない場合はZIPを展開できること |
| Browser | Chrome、Edge、Firefox、Safariのいずれか |
| Network | Git repository、`astral.sh`、PyPIへHTTPS接続できること |
| PC | 空き容量2GB以上、メモリ4GB以上 |
| Port | TCP 8000番が空いていること |

Python、uv、Docker、Node.jsの事前インストールは不要です。セットアップの目安は30～90分です。

## 2. セットアップ

### macOS（Terminal）

次のコマンドでrepositoryをCloneします。

```bash
git clone https://github.ibm.com/Shin-Sakamoto1/sample_asset.git ~/sample_asset
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
uv run uvicorn helpdesk.main:app --app-dir backend/src --host 127.0.0.1 --port 8000
```

### Windows（PowerShell）

次のコマンドでrepositoryをCloneします。

> ChromaのファイルをOneDriveが同期すると、インデックス構築時に`WinError 5`が発生することがあります。OneDrive配下ではなく、`C:\work\sample_asset`のような短いローカルパスを使用してください。

```powershell
git clone https://github.ibm.com/Shin-Sakamoto1/sample_asset.git C:\work\sample_asset
Set-Location C:\work\sample_asset
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

インストール直後のPowerShellで`uv`が見つからない場合は、インストール先を現在のセッションのPATHへ追加します。

```powershell
$uvBin = Join-Path $HOME ".local\bin"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (($userPath -split ";") -notcontains $uvBin) {
    $newUserPath = if ([string]::IsNullOrWhiteSpace($userPath)) { $uvBin } else { "$userPath;$uvBin" }
    [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
}
$env:Path = "$uvBin;$env:Path"
uv --version
```

続けて、次のコマンドを順番に実行します。

```powershell
Set-Location C:\work\sample_asset
uv python install 3.14
Copy-Item .env.example .env
uv sync
uv run python backend/scripts/build_index.py
```

`Index written to ...\data\index`と表示されたことを確認してから、サーバーを起動します。`PermissionError`やTracebackが表示された場合は起動せず、後述のトラブルシューティングを確認してください。

```powershell
uv run uvicorn helpdesk.main:app --app-dir backend/src --host 127.0.0.1 --port 8000
```

Gitを利用しない場合は、repositoryをZIPでダウンロードし、`C:\work\sample_asset`などOneDrive外かつ日本語や空白を含まない短いパスへ展開してください。展開後は`uv python install 3.14`以降を実行します。

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

watsonx.aiを利用する場合は、インターン運営者から次の値を受け取ってください。

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
uv run uvicorn helpdesk.main:app --app-dir backend/src --host 127.0.0.1 --port 8000
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
| `GET /api/v1/health/providers` | 動作中の接続先（LLM・埋め込み・ベクトルストア）の確認。画面右上の接続先バッジはこの値を表示する |

画面の使い方は[GUI操作ガイド](./Day2開発案内/GUI_USER_GUIDE.md)、詳細なAPIは起動後の`/docs`を参照してください。

## 6. 開発時の基本操作

### 6.1 アプリケーションの確認コマンド

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

### 6.2 Gitを使う理由

Gitは、ファイルを共有するだけでなく、誰が何を変更したかを履歴として残すために使用します。チーム開発では、次の目的があります。

- 変更を小さな単位で記録し、問題が起きた箇所を調べやすくする
- メンバーごとにブランチを分け、同じコードを並行して変更できるようにする
- Pull Requestで変更内容、テスト結果、セキュリティ上の問題を実装前後に確認する
- レビュー済みの変更だけを共有ブランチへ取り込み、動作する状態を保つ

最低限、次のルールを守ります。

- `main`ブランチでは直接開発せず、作業ごとにブランチを作る
- 1つのブランチには、1つの目的に関係する変更だけを含める
- コミット前に差分を確認し、テスト、Lint、型チェックを実行する
- `.env`、API Key、パスワード、個人情報、実在の顧客情報、不要な生成物をコミットしない
- `main`への取り込みは、原則としてPull Requestとレビューを通して行う

### 6.3 最小のGit作業手順

以下は、`feature/search-filter`という作業ブランチを作る例です。ブランチ名は、`feature/機能名`または`fix/修正内容`のように、目的が分かる短い英数字にします。

#### 1. 作業開始前に`main`を最新にする

```bash
git status
git switch main
git pull --ff-only origin main
```

| コマンド | 意味 |
|---|---|
| `git status` | 現在のブランチと、未コミットの変更を確認する |
| `git switch main` | 作業ブランチを`main`へ切り替える |
| `git pull --ff-only origin main` | GitHub上の最新`main`を取得する。履歴が分岐している場合は自動マージせず停止する |

`git status`で未コミットの変更が表示された場合は、その変更の担当者と扱いを確認してから切り替えます。別の人の変更を削除・上書きしてはいけません。

#### 2. 作業用ブランチを作る

```bash
git switch -c feature/search-filter
```

`-c`は、新しいブランチを作成して、そのブランチへ切り替える指定です。既に同名のブランチがある場合は`git switch feature/search-filter`を使用します。開発では作業項目、開発者ごとに個別のブランチを切り出して開発していくのが基本です。

#### 3. 変更内容を確認し、コミットする

```bash
git status
git diff
git add frontend/app.js
git add backend/tests/test_api.py
git diff --staged
git commit -m "feat: add ticket search filter"
```

| コマンド | 意味 |
|---|---|
| `git diff` | まだステージしていない変更内容を表示する |
| `git add <ファイル>` | 次のコミットへ含めるファイルをステージする |
| `git diff --staged` | コミット予定の差分を表示する |
| `git commit -m "..."` | ステージした変更を、説明メッセージ付きで履歴へ記録する |

意図しないファイルをステージした場合は、ファイル自体を削除せず、次のコマンドでコミット対象から外します。

```bash
git restore --staged <ファイル>
```

`git add .`は秘密情報や無関係なファイルまで含める可能性があるため、最初は対象ファイルを指定してください。コミットメッセージには、`feat:`（機能追加）、`fix:`（不具合修正）、`docs:`（文書変更）、`test:`（テスト変更）など、変更の種類と目的を短く書きます。

#### 4. `main`の最新変更を作業ブランチへ取り込む

Pull Requestを作る前に、共有ブランチの最新状態を取得し、作業ブランチへマージします。

```bash
git fetch origin
git merge origin/main
```

`git fetch origin`はGitHubの最新履歴を取得しますが、作業中のファイルは変更しません。`git merge origin/main`は、取得した`main`の変更を現在の作業ブランチへ統合します。統合後はテスト、Lint、型チェックを再実行してください。

同じ箇所が別々に変更されていると、マージコンフリクトが発生します。その場合は次の順で対応します。

1. `git status`で競合したファイルを確認する。
2. ファイル内の`<<<<<<<`、`=======`、`>>>>>>>`で囲まれた箇所を確認し、残す内容をチームで決める。
3. 修正後に`git add <ファイル>`を実行する。
4. すべて解決したら`git commit`でマージを完了する。

解決方針が分からない場合は、無理に進めず`git merge --abort`でマージ開始前へ戻し、チームへ確認します。

#### 5. ブランチをGitHubへ送る

```bash
git push -u origin feature/search-filter
```

`push`はローカルのコミットをGitHubへ送る操作です。`-u`を最初の1回だけ付けると、次回から同じブランチでは`git push`だけで送れます。

### 6.4 Pull Requestを作成してマージする

Pull RequestはGitコマンドではなく、GitHub上で「このブランチの変更を`main`へ取り込んでほしい」と依頼し、レビューする仕組みです。

1. GitHubで対象リポジトリを開く。
2. `Compare & pull request`、または`Pull requests`の`New pull request`を選ぶ。
3. 取り込み先を`main`、比較元を作業ブランチにする。
4. 目的、主な変更、確認方法、テスト結果、未解決事項を書く。
5. 変更ファイルに`.env`、秘密情報、個人情報、不要な生成物がないことを確認する。
6. レビューを依頼し、指摘があれば同じブランチで修正・コミット・Pushする。
7. 承認後にGitHub上でマージする。コンフリクトやテスト失敗がある状態ではマージしない。

Pull Requestの記載例:

```text
目的:
チケットをステータスで絞り込めるようにする。

主な変更:
- 絞り込みUIを追加
- API呼び出しへstatusを追加
- 関連テストを追加

確認結果:
- make test: 成功
- make lint: 成功
- make typecheck: 成功

未解決事項:
なし
```

マージ後は、手元の`main`を最新にし、不要になったローカルブランチを削除します。

```bash
git switch main
git pull --ff-only origin main
git branch -d feature/search-filter
```

秘密情報を誤ってコミットした場合は、履歴から見えなくするだけでは不十分です。直ちにチームと管理者へ連絡し、API Keyやパスワードを失効・再発行してください。

## 7. トラブルシューティング

| 症状 | 対応 |
|---|---|
| Windowsで`uv`が見つからない | `$env:Path = "$(Join-Path $HOME '.local\bin');$env:Path"`を実行してから`uv --version`で確認する |
| 8000番Portを使用できない | 既に起動しているアプリを停止する |
| `/health/ready`が503 | `.env`を確認し、サーバー停止後に`build_index.py`を再実行する |
| Chromaを開けない | 複数のFastAPI processを停止し、インデックスを再構築する |
| Windowsで`WinError 5` | FastAPIを`Ctrl+C`で停止し、OneDrive外の`C:\work\sample_asset`へ展開し直す。残った`data\index`、`data\index.new`、`data\index.old`は生成物なので削除してから再構築する |
| `WatchFiles detected changes in '.venv'`が繰り返される | 初回確認では`--reload`を付けずに起動する。起動中のprocessは`Ctrl+C`で停止してから再実行する |
| `/favicon.ico`が404 | Browserのアイコン要求であり、アプリケーション動作には影響しない |
| watsonx.ai接続に失敗する | URL、Project ID、モデルIDを確認する。API Keyは画面やログへ出力しない |

Mac／Windows別の補足は[環境構築手順](./Day2開発案内/環境構築手順_Mac_Windows.md)を参照してください。

## 8. （オプション）検索文書再構築手順

RAGの検索対象は`data/seed/documents.json`です。検索文書は、業務ツールのうちFAQ回答集と問い合わせ分類基準表から生成します。問い合わせ管理シートはTicket、問い合わせフォームはMasterの生成に使用します。検索文書を変更した場合は、Chromaインデックスを再構築します。

### 業務ツールのExcelを正本として編集する場合

`assets/source/business_tools/`のファイルを編集した後、次を実行します。実行時に親ディレクトリは参照しません。コマンドはmacOSのTerminalとWindows PowerShellで共通です。

```bash
uv run python backend/scripts/import_business_tools.py validate   # 検証のみ。出力は変更しない
uv run python backend/scripts/import_business_tools.py export     # 検証後、Seedを一括置換
uv run python backend/scripts/build_index.py                      # Chromaインデックス再構築
```

| ファイル | repository内の名前 | 用途 |
|---|---|---|
| `FAQ回答集.xlsx` | `faq_answers.xlsx` | 検索文書（FAQ） |
| `問い合わせ分類基準表.xlsx` | `inquiry_classification.xlsx` | 検索文書（分類基準）、Master |
| `問い合わせ管理シート.xlsx` | `inquiry_management.xlsx` | Ticket初期データ（「集計」Sheetは対象外） |
| `問い合わせフォーム.html` | `inquiry_form.html` | お問い合わせ種類のMaster |

- 検証エラーは`file`／`sheet`／`row`／`column`／`error_code`だけを出力し、セルの内容は出力しません。
- 未知のカテゴリ・担当などはエラーになります。`import_business_tools.py`内の対応表を更新してください。
- `export`は`data/seed/`を再生成します。実行前に差分をCommitするかバックアップし、実行後は`git diff -- data/seed`で確認してください。

### JSONを直接編集する場合

1. 起動中のサーバーを`Ctrl+C`で停止します。
2. `data/seed/documents.json`を編集します。
3. 次のコマンドでインデックスを再構築します。
4. サーバーを起動し、変更した文書を検索できることを確認します。

```bash
uv run python backend/scripts/build_index.py
uv run uvicorn helpdesk.main:app --app-dir backend/src --host 127.0.0.1 --port 8000
```

文書は次の形式で追加します。`document_id`は重複させず、既存文書を更新するときは同じIDを維持してください。

```json
{
  "document_id": "faq:FAQ-16",
  "title": "配送日を変更したい",
  "body": "質問: 配送日を変更したい\n回答: ...\n窓口対応: はい",
  "document_type": "faq",
  "source": "FAQ回答集.xlsx#FAQ回答集!20",
  "category": "配送関連",
  "updated_at": "2026-10-21",
  "access_scope": "default",
  "is_active": true,
  "faq_id": "FAQ-16",
  "completion_policy": "はい"
}
```

`document_type`は`faq`、`classification_rule`、`priority_rule`です。削除する文書は、履歴を残す場合は`is_active`を`false`にします。

### 個人情報の取扱い

氏名、メールアドレス、注文番号、備考、添付はTicketにのみ保存し、Embedding、Chroma、LLM Prompt、Logへ渡しません。RAGへ渡す情報は「お問い合わせ種類」「商品名」「問い合わせ内容」に限定しています。`data/runtime/`と`data/index/`はGit管理対象外です。不要になった時点で削除してください。

## 9. （オプション）拡張構成

- Docker／Podman（ローカルのみ）: `Dockerfile`と`compose.yaml`。クラウドへのデプロイは想定していません。
- ローカルEmbedding: `uv sync --extra local-embedding`

これらは初回セットアップには不要です。基本はPythonでの直接実行です。

### コンテナで実行する場合（任意）

ホストでインデックスを作成してから、そのディレクトリをコンテナへマウントします。`.env`は`uv run`と同じものを使います。

```bash
uv run python backend/scripts/build_index.py   # data/indexを作成
docker compose up --build -d                   # Podmanの場合は podman compose
docker compose logs -f app
docker compose down
```

- 起動後は`http://127.0.0.1:8000`で開きます（`127.0.0.1`のみに公開します）。
- `data/index/`は書き込み可能でマウントします。Chromaは検索時にもSQLiteへ書き込むためです。それ以外の場所は読み取り専用です。
- `.env`の`LLM_PROVIDER`と`EMBEDDING_PROVIDER`の設定に従います。インデックス作成時と同じEmbedding設定で起動してください。

## 用語の補足

| 用語 | 簡単な説明 |
|---|---|
| RAG | 質問に関係する文書を検索し、その内容を根拠としてAIに回答を作らせる方式。 |
| LLM | 大量の文章を学習し、文章の理解や生成を行うAIモデル。 |
| Embedding（埋め込み） | 文章の意味を、似ているか計算できる数値の並びに変換する処理。 |
| Vector DB／Chroma | Embeddingを保存し、意味の近い文書を検索するデータベース。Chromaは本アプリで使う製品名。 |
| Frontend／Backend | Frontendは利用者が操作する画面側、Backendはデータ処理や外部サービス連携を行うサーバー側。 |
| API | アプリケーション同士が、決められた形式で機能やデータをやり取りする窓口。 |
| API Key | 外部サービスを利用する権限を確認するための秘密の文字列。パスワードと同様に扱う。 |
| Mock | 本物の外部サービスを呼ばず、決められた疑似結果を返す動作確認用の代替実装。 |
| Repository／Clone | Repositoryはコードや変更履歴の保管場所、Cloneはその内容をPCへ複製する操作。 |
| Branch（ブランチ） | 他の作業へ影響させずに変更するため、履歴を分けた作業場所。 |
| Stage／Commit | Stageは次の記録へ含める変更を選ぶ操作、Commitは選んだ変更を履歴へ記録する操作。 |
| Merge／コンフリクト | Mergeは別のブランチの変更を統合する操作、コンフリクトは同じ箇所の変更が競合して自動統合できない状態。 |
| Pull／Push | Pullは共有先の変更を手元へ取り込み、Pushは手元のコミットを共有先へ送る操作。 |
| Pull Request | 作業ブランチの変更を共有ブランチへ取り込む前に、内容確認やレビューを依頼するGitHubの仕組み。 |
| `origin` | Clone元など、Gitに登録されたリモートリポジトリの標準的な名前。 |
| Seed | 初回起動やテストで使う、あらかじめ用意した初期データ。 |
| インデックス | 検索を速くするために、文書やEmbeddingを検索しやすい形へ整理したデータ。 |
| `.env`／環境変数 | 実行環境ごとに変わる設定をコードと分けて管理する仕組み。`.env`には秘密情報が入るためGitへ登録しない。 |
| Port（ポート） | 同じPC上の複数サービスを見分ける番号。本アプリはTCP 8000番を使う。 |
| ヘルスチェック | アプリが起動中か、必要な接続やデータの準備ができているかを確認する処理。 |
| Lint／型チェック | Lintは書式や問題のある書き方を検査し、型チェックはデータ型の不整合を検査する。 |
| コンテナ／マウント | コンテナはアプリの実行環境をまとめた単位、マウントはホスト側のファイルをコンテナから使えるようにする設定。 |
