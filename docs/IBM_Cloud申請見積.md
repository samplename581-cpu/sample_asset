# IBM Cloud申請・利用見積

## 1. 申請目的と期間

| 項目 | 申請内容 |
|---|---|
| 目的 | 学生向けヘルプデスクRAG演習。ローカルのFastAPIアプリケーションからIBM Cloud APIを利用する |
| 利用開始 | 2026年10月10日 |
| 利用終了 | 2026年12月31日 |
| 最大期間 | 83暦日、1,992時間 |
| 利用者 | 8名（4名×2グループ） |
| リージョン | 東京（`jp-tok`） |
| 実データ | 使用しない。架空Ticket・架空社内文書のみ |
| アプリ配備 | IBM Cloudへの配備は必須ではない |
| コンテナ | 任意。Docker／Podmanを利用できる場合だけ使用する |

年度が異なる場合は日付と時間数を申請票に合わせて変更する。

## 2. 申請対象サービスと関連コンポーネント

| 区分 | コンポーネント | 申請／設定 | 用途 | 主な見積単位 |
|---|---|---:|---|---|
| IBM Cloud Catalog | Watson Machine Learning（watsonx.ai Runtime） | Yes | IBM提供の生成LLM／Embedding APIを利用するための実行・課金基盤 | Model別の入力・出力TokenまたはRU。独自モデルの学習・デプロイは行わずCUHは0 |
| IBM Cloud Catalog | watsonx.ai Studio | Yes | `WATSONX_PROJECT_ID`で使用するProjectの作成・管理 | Project数1。Notebook等を実行しない場合、Studio CUHは0 |
| IBM Cloud Catalog | Cloud Object Storage | Yes | watsonx.ai Projectの関連storage | instance数1。既存instanceを再利用する場合も申請票に明記 |
| IBM Cloud Catalog | watsonx.data | Yes | Vector Database基盤 | 契約planとsupport serviceのRU |
| watsonx.data内部 | Milvusサービス | Yes | 文書Vectorとmetadataの検索 | MilvusのRU/時、保存量。独立したCatalog serviceではない |
| IBM Cloud共通機能 | IBM Cloud IAM／Service ID／API Key／Access Policy | サービス申請不要・設定依頼のみ | アプリケーションからの認証 | Catalog serviceおよび見積対象ではない。可能ならグループ単位で2組発行し、権限と失効日を管理 |
| ローカル | FastAPIアプリケーション | Yes | UI、Ticket API、RAG orchestration | 学生のMac／Windows上で実行 |
| ローカル | `.env` | Yes | Project ID、API Key、endpoint | Git・ZIP・画面・ログへ含めない |
| ローカル | Docker／Podman | No | 任意の再現可能な実行方法 | 利用可能な端末だけで使用 |
| IBM Cloud | アプリ実行サービス | No | Cloudへアプリを配備する場合だけ | 今回の基本申請には含めない |
| IBM Cloud | Container Registry | No | Cloud配備用imageを保管する場合だけ | 今回の基本申請には含めない |

## 3. 数量見積もり

> **暫定見積の扱い**: アカウントまたは契約上の制約でwatsonx.dataをEstimatorへ追加できない場合、watsonx.data／Milvusを不要または0円とは記載しない。「未申請・未計上」としてWatson Machine Learning、watsonx.ai Studio、Cloud Object Storageの小計と分離し、制約解消後に必ず追加する。

申請前に次の変数を運営担当が記入する。

| 記号 | 内容 | 申請値 |
|---|---|---|
| `U` | 利用者数 | 8名 |
| `G` | グループ数 | 2グループ |
| `M` | 1グループあたりの人数 | 4名 |
| `D` | 実際の演習日数 | 未確定。最大83日 |
| `Q` | 1人1日あたりの回答生成回数 | 未確定 |
| `S` | 1人1日あたりの検索のみの回数 | 未確定 |
| `TI` | 1回の生成に使う平均入力Token | 実測後に確定 |
| `TO` | 1回の生成に使う平均出力Token | 実測後に確定 |
| `TE` | 1回のquery Embedding平均Token | 実測後に確定 |
| `C` | 登録Chunk数 | 文書変換後に確定 |
| `TD` | 初回文書Embeddingの総Token | 文書変換後に確定 |
| `H` | Milvusの課金対象稼働時間 | 最大1,992時間 |

計算式:

```text
回答生成API回数       = U × D × Q
検索API回数           = U × D × S
生成入力Token         = U × D × Q × TI
生成出力Token         = U × D × Q × TO
query Embedding Token = U × D × (Q + S) × TE
文書Embedding Token   = TD + 更新文書の再Embedding Token
概算Vector生データ量  = C × EMBEDDING_DIMENSION × 4 bytes
```

上式は8名が個別に操作する保守的な見積もりとする。グループごとに代表者1名だけが操作する授業では、`U`を`G=2`へ置き換えた値も併記できる。ただし、予算申請の上限は`U=8`で算定する。

Vectorの生データ量には、Milvus index、metadata、replica、backup、service overheadを含まない。保存量とRUはIBM Cloud estimatorで別途確認する。

## 4. watsonx.ai費用の算定方法

watsonx.aiの生成とEmbeddingは、選択したModel、リージョン、入力／出力Tokenで料金が変わる。申請額は次の手順で算定する。

申請画面や見積明細では`Watson Machine Learning`と表示される場合があるが、本書では現行サービス名の`watsonx.ai Runtime`を併記する。本案件では独自の機械学習モデルを構築・ホストするためには使用しない。IBMが提供済みのFoundation ModelとEmbedding ModelをAPIで呼び出すためのservice instance、利用plan、metering主体として使用する。専用model deployment、学習用compute、GPU、deployment spaceは申請対象外とする。

1. 生成Model IDとEmbedding Model IDを確定する。
2. 上記式から期間合計Tokenを求める。
3. IBMのModel別料金表から入力、出力、Embeddingの単価を取得する。
4. 10月、11月、12月の月別に分け、予備枠を加えて申請する。
5. 演習開始後はIBM Cloudのusage画面で実績を週次確認する。

```text
生成費用 = (生成入力Token ÷ 1,000 × 入力単価)
         + (生成出力Token ÷ 1,000 × 出力単価)

Embedding費用 = Embedding対象Token ÷ 1,000 × Model単価
```

料金表は更新される可能性があるため、本書へ特定Modelの固定単価を転記しない。

## 5. watsonx.data Milvus費用の算定方法

watsonx.dataは、Milvusなどのinfrastructure componentとsupport serviceの時間あたりRUを合計して算定する。

```text
watsonx.data RU = H × (Milvus RU/時 + support service RU/時 + その他component RU/時)
watsonx.data費用 = watsonx.data RU × 契約上のRU単価
```

- `H`は申請期間83日を連続稼働させる場合、最大1,992時間となる。
- Milvusを停止できてもsupport serviceの課金が継続する場合があるため、停止条件をIBM Cloud画面で確認する。
- Lite／Trialを使用する場合も、無料RU、失効条件、永続性が演習期間を満たすか確認する。
- 12月31日の演習終了後に不要なserviceを停止・削除し、Keyを失効する。

IBM公式資料の例にはMilvus starterとsupport serviceを合算する計算例があるが、例示RUをそのまま申請値にせず、申請リージョンと契約planのCatalog表示値を使用する。

## 6. 申請数量表

| 項目 | 10月 | 11月 | 12月 | 合計／上限 | 根拠 |
|---|---:|---:|---:|---:|---|
| Watson Machine Learning instance | 1 | 1 | 1 | 1 | watsonx.ai RuntimeのAPI・metering主体 |
| watsonx.ai Studio Project | 1 | 1 | 1 | 1 | 2グループで共有 |
| watsonx.ai Studio CUH | 0 | 0 | 0 | 0 | Notebook／計算環境を実行しない |
| Cloud Object Storage instance | 1 | 1 | 1 | 1 | Project関連ストレージ。既存instance再利用可 |
| Cloud Object Storage容量・request | TBD | TBD | TBD | 実利用量 | 0固定ではなくEstimatorで少量を入力 |
| watsonx.data instance | 1 | 1 | 1 | 1 | Milvus基盤。追加不能時は未申請・未計上 |
| 利用者数 | 8 | 8 | 8 | 8 | 4名×2グループ |
| 演習日数 | TBD | TBD | TBD | `D` | 授業日程 |
| 生成API回数 | TBD | TBD | TBD | `U×D×Q` | 操作シナリオ |
| 生成入力Token | TBD | TBD | TBD | `U×D×Q×TI` | pilot実測 |
| 生成出力Token | TBD | TBD | TBD | `U×D×Q×TO` | pilot実測 |
| Embedding Token | TBD | TBD | TBD | 上記計算式 | 文書・query量 |
| Milvus稼働時間 | 最大528h | 最大720h | 最大744h | 最大1,992h | 10/10開始、12/31終了 |
| Milvus／support RU | TBD | TBD | TBD | `H×RU/時` | IBM Cloud estimator |

10月は10月10日から31日までの22日として最大528時間で計算する。

## 7. 予算統制

- API Keyは学生個人へ直接配布せず、配布方法と責任者を決める。
- 8名共通のKeyを避け、サービス側の認証仕様が許す範囲で4名×2グループごとに資格情報を分離する。
- 利用上限、rate limit、異常利用時の停止手順を事前に決める。
- Token、API回数、Milvus RU、失敗率を週次確認する。
- 予算の80%到達時に警告し、90%到達時に追加利用を承認制とする。
- 12月31日に新規利用を停止し、成果確認後にAPI Keyを失効する。

## 8. 申請前チェック

- [ ] Watson Machine Learning（watsonx.ai Runtime）を申請対象に含めた
- [ ] watsonx.ai Studioを申請対象に含め、Project数を1とした
- [ ] Cloud Object StorageをProject関連ストレージとして申請対象に含めた
- [ ] watsonx.data／Milvusを申請対象に含めた。追加不能の場合は「未申請・未計上」と注記した
- [ ] `U`、`D`、`Q`、`S`を確定した
- [ ] pilotで`TI`、`TO`、`TE`を計測した
- [ ] 東京リージョン（`jp-tok`）で利用可能な生成／Embedding Model IDを確定した
- [ ] Milvusとsupport serviceのRU/時をCatalogで確認した
- [ ] 月別費用と予備枠をIBM Cloud estimatorで確認した
- [ ] API Keyの管理者、利用上限、失効日を決めた
- [ ] 2026年12月31日以降の停止・削除担当を決めた

## 9. 公式資料

- [IBM watsonx.ai: Billing details for generative AI assets](https://dataplatform.cloud.ibm.com/docs/content/wsj/getting-started/wxai-runtime-plans-genai.html?context=wx)
- [IBM watsonx.ai: Supported foundation models and prices](https://dataplatform.cloud.ibm.com/docs/content/wsj/analyze-data/fm-models.html?context=wx)
- [IBM watsonx.data: Billing and usage](https://cloud.ibm.com/docs/watsonxdata?topic=watsonxdata-manage_bill)
- [IBM Cloud watsonx.data Catalog](https://cloud.ibm.com/watsonxdata?topic=watsonxdata-getting-started)
