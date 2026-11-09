# リソース一覧と配置先ガイド

出力先: `docs/fde/02_resources.md`

## 1. リソース一覧の書き方

| 列 | 内容 |
|---|---|
| リソース ID | R-01 のように振る |
| リソース | 名前 |
| 種別 | データ / 文書 / コード / 設定 / 外部サービス / IBM 製品 / ドキュメント |
| 紐づく要件 | FR-xxx |
| 状態 | 既存 / 要作成 / 要依頼 |
| 配置先 | 具体的なパス |
| 機密区分 | 架空データ / 内部 / 秘密（`.env` のみ） |
| 反映手順 | 追加後に必要な操作 |

## 2. 配置先の早見表

### A. サンプルアセット（RAG）をベースにする場合

パスはサンプルアセットのリポジトリルート基準。

| リソース | 配置先 | 反映手順・備考 |
|---|---|---|
| 検索対象の文書（FAQ・分類基準） | `assets/source/business_tools/*.xlsx`（正本）→ `data/seed/documents.json`（生成物） | `uv run python backend/scripts/import_business_tools.py validate` → `export` → `uv run python backend/scripts/build_index.py` |
| xlsx 以外の文書（手順書など） | `data/seed/documents.json` に追記 | `document_id` を重複させない。追記後に `build_index.py` を再実行 |
| チケット | `assets/source/business_tools/inquiry_management.xlsx` → `data/seed/tickets*.json` | 画面は `tickets_app.json` を使用。実行時データは `data/runtime/`（Git 管理外） |
| マスタ（カテゴリ・緊急度・担当） | `data/seed/masters.json`（生成物） | 新しい値は `backend/scripts/import_business_tools.py` の対応表（`CATEGORY_IDS`、`TEAM_IDS` など）を更新。未知の値はエラーになる |
| 評価用の正解データ | `data/evaluation/` | 例: `triage_eval.json`。架空データのみ |
| 新しい API | `backend/src/helpdesk/api/<機能>.py` | `main.py` の `include_router` に追加。`openapi/helpdesk-api.yaml` も更新し、`backend/tests/contract/` を通す |
| 業務ロジック | `backend/src/helpdesk/services/<機能>_service.py` | LLM・検索は ports 経由で呼ぶ |
| 外部サービスの差し替え | `ports/`（インターフェース）+ `adapters/`（実装） | LLM は `adapters/factory.py` の `create_llm`、Embedding と Vector は `main.py` の `_create_embedding` / `_load_rag_service` |
| 画面 | `frontend/`（`index.html` / `app.js` / `style.css`） | `main.py` が `/` で静的配信 |
| 設定値 | `backend/src/helpdesk/config.py` と `.env.example` | `.env.example` にはキー名のみ。値は書かない |
| 認証情報（API Key、Project ID など） | `.env` | Git 管理外。Bob からは `.bobignore` で隔離。チャットに貼らない |
| テスト | `backend/tests/unit` / `integration` / `contract` | 新機能ごとに追加 |
| FDE ドキュメント | `docs/fde/` | 評価、要件、リソース、定着と還元 |
| Bob 拡張 | `.bob/` | `skills/`、`custom_modes.yaml`、`rules-fde-dev/` |

サンプルデータは架空の家具通販会社「トヨスナ」の問い合わせ業務（配送関連、商品不良・破損など）。
別の業務に変える場合は、xlsx と `import_business_tools.py` の対応表を同時に更新する。

### B. RAG ベースでない場合・新規構成の場合

既存の構成がない場合は次を推奨する。

| リソース | 推奨配置 |
|---|---|
| ソースコード | `src/` |
| テスト | `tests/` |
| 架空データ | `data/seed/` |
| 実行時データ | `data/runtime/`（Git 管理外） |
| 外部サービスの接続部 | `src/adapters/`（差し替えやすいように分ける） |
| 設定と秘密 | `.env`（Git 管理外）、`.env.example`（キー名のみ） |
| FDE ドキュメント | `docs/fde/` |

### C. IBM 製品・クラウドリソース

自分で用意できないものは、状態を「要依頼」にして運営へ依頼する。

| リソース | 受け取るもの | 配置先 |
|---|---|---|
| watsonx.ai | URL、Project ID、API Key、生成モデル ID、Embedding モデル ID と出力次元 | `.env`（コードは `adapters/`） |
| Cloud Object Storage、Db2、Milvus など | 接続情報 | `.env`（コードは `adapters/`） |
| watsonx Orchestrate | 利用環境と権限 | 運営に確認 |

## 3. チェックリスト

- [ ] すべての Must 要件に、1 つ以上のリソースが紐づいている
- [ ] すべてのリソースに、具体的なパスと状態が書いてある
- [ ] 秘密情報の配置先が `.env` のみになっている
- [ ] 「要依頼」のリソースに、依頼先と期限の目安がある
- [ ] 個人情報を含むデータがない（架空データのみ）
