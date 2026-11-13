# FDE ソリューション開発キット for Bob

> **【インターン用コンテンツ】** このフォルダは、IBMのインターンシップ（FDE体験）の参加者向けに作成した教材です。IBMの製品や公式のテンプレートではありません。内容は予告なく変更することがあります。リポジトリ全体の案内は、[ルートのREADME](../README.md)を参照してください。

業務観察で作ったソリューション案を、Bob と一緒に「評価 → 要件 → リソース配置 → 実装 → 定着と還元」まで進めるための素材一式です。
Step 4 の「スキル」と「カスタムモード」の演習で、`sales-api` の代わりに使います。

## 0. このキットの位置付け

| 項目 | 内容 |
|---|---|
| 対象 | 業務観察を終え、ソリューション案を持っているインターン参加者 |
| 使うタイミング | ソリューション案を評価し、要件とリソースを整理して、開発に入る前後 |
| できること | 案の評価、機能要件の一覧化、必要リソースと配置先の指定、RAGの要否判定、実装、定着と還元の整理 |
| 前提 | [Bobの環境構築](../Day2開発案内/IBMBob開発環境構築手順.md)が済んでいること |
| 関連 | RAGベースの案では、[サンプルアセット](../README.md)を土台にできる。RAGベースでない案では、使わなくてよい |

最初に読むのは、[1. 中身](#1-中身)と[3. 使い方](#3-使い方)です。Bobへの適用方法は、[2. Bob への適用手順](#2-bob-への適用手順)にあります。

## 1. 中身

```text
fde_bob_kit/
├── README.md                          ← この説明書
└── bob_template/                      ← 開発するアプリのルートへコピーする
    ├── .bobignore                     ← Bob に見せないファイル（.env など）
    └── .bob/
        ├── custom_modes.yaml          ← カスタムモード「🧭 FDE開発者」
        ├── rules-fde-dev/
        │   └── 01-fde-principles.md   ← このモード専用の行動指針（FDE の考え方）
        └── skills/
            └── fde-solution-dev/
                ├── SKILL.md               ← スキル本体（進め方 Step 0〜6）
                ├── evaluation-criteria.md ← ソリューション検討の評価基準
                ├── requirements-template.md ← 機能要件一覧のテンプレート
                └── resource-placement.md  ← リソース一覧と配置先ガイド
```

| 部品 | 役割 | 呼ばれ方 |
|---|---|---|
| スキル `fde-solution-dev` | 手順書。何を、どの順で、どの形式で出すかを Bob に教える | Bob が自動判断、または `/fde-solution-dev` |
| モード `fde-dev` | 役割。FDE 開発者として振る舞い、ルールを常に守らせる | モード選択で切り替え |
| 評価基準 | 案を比較・絞り込む物差し | スキルが参照 |

## 2. Bob への適用手順

### 2.1 全体像と用語

Bob は、プロジェクトのルートにある `.bob/` フォルダを読み込みます。ファイルを正しい場所に置けば適用されます。

| 区分 | 置き場所(アプリのルートからの相対パス) | Bob での扱い |
|---|---|---|
| スキル | `.bob/skills/<スキル名>/SKILL.md`(補助ファイルは同じフォルダ) | 依頼内容に合うと Bob が自動で有効化する。`/スキル名` で明示的にも呼べる |
| モード(いわゆる agents) | `.bob/custom_modes.yaml` | モード選択に「🧭 FDE開発者」が追加される |
| モード専用ルール | `.bob/rules-<モードのslug>/*.md` | そのモードのときだけ、ファイル名順に読み込まれる |
| アクセス制限 | `.bobignore`(ルート直下) | 書かれたファイルを Bob が読めなくなる |

- 「agents.md」と呼ばれているものは、このキットでは**カスタムモード**(`custom_modes.yaml` と `rules-fde-dev/`)です。
- Bob には別に `AGENTS.md` というファイルがあります。これは全モード共通でプロジェクトの説明や規約を伝えるもので、ルートに置くと自動で読み込まれます。このキットには含めていません。必要なら Bob のチャットで `/init` を実行すると生成されます。
- スキルとモードの違い: スキルは「手順書」、モードは「役割と使える道具」です。FDE の進め方(手順)はスキルに、守るべき姿勢(役割)はモードに置いています。

### 2.2 方法A: ファイルをコピーする(推奨)

最も確実で、チームに配るときも同じ手順で済みます。

**手順1. 適用先のアプリのルートを決める**

Bob IDE で開いているフォルダがルートです。例として、サンプルアセットに適用する場合は `sample_asset/` です。ここでは `<アプリのルート>` と書きます。

**手順2. 既存の `.bob/` と `.bobignore` を確認する**

```bash
ls -a <アプリのルート> | grep -E '^\.bob'
```

何も出なければ手順3へ進みます。既にある場合は、コピーで上書きされないように、手順5の「マージ」を読んでください。

**手順3. コピーする**

```bash
cp -R sample_asset/fde_bob_kit/bob_template/.bob <アプリのルート>/
cp -n sample_asset/fde_bob_kit/bob_template/.bobignore <アプリのルート>/
```

`sample_asset/` 自体に適用する場合は、`sample_asset/` で次のようにします。

```bash
cp -R fde_bob_kit/bob_template/.bob .
cp -n fde_bob_kit/bob_template/.bobignore .
```

**手順4. コピー結果を確認する**

```bash
find <アプリのルート>/.bob -type f | sort
```

次の 6 ファイルが表示されれば成功です。

```text
.bob/custom_modes.yaml
.bob/rules-fde-dev/01-fde-principles.md
.bob/skills/fde-solution-dev/SKILL.md
.bob/skills/fde-solution-dev/evaluation-criteria.md
.bob/skills/fde-solution-dev/requirements-template.md
.bob/skills/fde-solution-dev/resource-placement.md
```

**手順5. 既存ファイルがある場合のマージ**

| 既存のファイル | 対応 |
|---|---|
| `.bob/custom_modes.yaml` | 上書きしない。キットの `customModes:` 配下の `- slug: fde-dev` から始まる 1 件を、既存の `customModes:` の配列に追加する。`slug` が重複すると読み込めない |
| `.bob/skills/` | 同じ名前のスキルがなければ、`fde-solution-dev` フォルダだけをコピーする |
| `.bob/rules-fde-dev/` | 通常は存在しないので、そのままコピーする |
| `.bobignore` | `cp -n` で上書きされない。キットの内容を既存ファイルの末尾に追記する |

**手順6. Bob に読み込ませる**

1. Bob IDE でそのアプリのフォルダを開く(別のフォルダを開いている場合は、`ファイル > フォルダーを開く` で開き直す)。
2. 反映されないときは、Bob のパネルを閉じて開き直す。それでも出ないときは、IDE のウィンドウを再読み込みするか、IDE を再起動する。
3. `.bobignore` は、変更後およそ 30 秒で自動的に反映される。

### 2.3 方法B: Bob の画面から作る

ファイルをコピーせず、画面で入力して作る方法です。内容は `bob_template/` 内のファイルをコピー&ペーストします。方法Aで読み込めなかったときの確認にも使えます。

**B-1. スキルを作る**

1. Bob のチャット欄の下にある **Bob Settings**(歯車)をクリックする。
2. 左のメニューから **Skills** を選び、**+** をクリックする。
3. 次のとおり入力する。

| 項目 | 入力する内容 |
|---|---|
| Skill Name | `fde-solution-dev` |
| Description | `SKILL.md` の先頭にある `description:` の文章 |
| Allow Bob to use this skill | On |
| Scope & Location | このプロジェクトのフォルダ名(`.bob/skills/` に保存され、Git でチームに共有できる)。自分の全プロジェクトで使うなら `Global (all workspaces)`(`~/.bob/skills/` に保存) |
| Skill Instructions | `SKILL.md` の `---` より下の本文 |

4. 保存する。
5. この画面では補助ファイルを作れません。次のコマンドで、補助 3 ファイルをスキルのフォルダへコピーします。本文中の `evaluation-criteria.md` などへのリンクが、これで機能します。

```bash
cp sample_asset/fde_bob_kit/bob_template/.bob/skills/fde-solution-dev/{evaluation-criteria,requirements-template,resource-placement}.md <アプリのルート>/.bob/skills/fde-solution-dev/
```

> 補助ファイルまで含めて使うなら、方法Aのほうが簡単です。

**B-2. カスタムモードを作る**

1. **Bob Settings** を開き、**Modes** タブを選ぶ。
2. **+**(追加)をクリックする。
3. 次のとおり入力する。値は `custom_modes.yaml` からコピーします。

| 項目 | 入力する内容 |
|---|---|
| Name | `🧭 FDE開発者` |
| Slug | `fde-dev` |
| Save Location | このプロジェクト(`.bob/custom_modes.yaml` に保存される) |
| Role Definition | `roleDefinition:` の文章 |
| When to Use | `whenToUse:` の文章 |
| Available Tools | read、edit、execute、skill、todo、subtask、mode |
| Custom Instructions | `customInstructions:` の文章 |

4. **Save** をクリックする。
5. モード専用ルール(`rules-fde-dev/01-fde-principles.md`)は、画面からは作れません。次のコマンドでコピーします。

```bash
cp -R sample_asset/fde_bob_kit/bob_template/.bob/rules-fde-dev <アプリのルート>/.bob/
```

**ヒント**: **Modes** タブの **Edit Project Modes** をクリックすると、`.bob/custom_modes.yaml` が直接開きます。マージ作業はここから行えます。

### 2.4 適用できたかを確認する

**スキルの確認**

1. **Bob Settings > Skills** を開く。
2. `fde-solution-dev` が一覧にあることを確認する。
3. 場所が「project」(`.bob/skills/`)になっていること、**Allow Bob to use this skill** が On であることを確認する。

**モードの確認**

1. チャット欄の下のモード選択(Agent、Plan、Ask が並んでいる場所)を開く。
2. 「🧭 FDE開発者」が一覧にあることを確認し、選択する。
3. **Bob Settings > Modes** にも同じモードが表示される。

**動作の確認**

モードを「🧭 FDE開発者」にして、次のように入力します。

```text
/fde-solution-dev
ソリューション案を評価したいです。まず必要な入力を教えてください。
```

次の応答になれば、スキルとモードの両方が効いています。

- 「スキルを有効化した」旨が表示され、対象業務、課題と根拠、ソリューション案を質問してくる(Step 0)
- 評価の話になると、ゲート G1〜G4 と 6 観点の表が出てくる

`.bobignore` の確認は、チャットで `@/.env` を指定して内容を読もうとします。読めない、またはアクセスが拒否されれば成功です。`.env` が存在しないアプリでは、このテストは省略してかまいません。

### 2.5 うまくいかないとき

| 症状 | 原因と対処 |
|---|---|
| モードが一覧に出ない | `.bob/custom_modes.yaml` が、開いているフォルダの直下の `.bob/` にあるか確認する。YAML のインデントが崩れていないか確認する。`slug` が重複していないか確認する。手順6の再読み込みを行う |
| スキルが一覧に出ない | フォルダ名が小文字のケバブケース(`fde-solution-dev`)か、`SKILL.md` の `name` と一致しているかを確認する。`SKILL.md` の先頭に `---` で囲んだ `name` と `description` があるか確認する。開いているフォルダが信頼済みか確認する |
| スキルが自動で有効化されない | モードの `groups` に `skill` があるか確認する(このキットのモードにはあり)。Agent など別のモードでも `skill` が許可されているか確認する。Skills 画面で **Allow Bob to use this skill** が On か確認する。確実に使いたいときは、依頼の先頭に `/fde-solution-dev` を付ける |
| 「スキルは組み込み登録対象外のため、ファイルから直接読み込んで適用する」と表示される | 正常。ファイルとして読み込まれて機能している |
| モード専用ルールが効いていない | フォルダ名が `rules-` + モードの `slug`(`rules-fde-dev`)になっているか確認する |
| 補助ファイルが読まれない | 補助 3 ファイルが `SKILL.md` と同じフォルダにあるか確認する |
| `.env` を読めてしまう | `.bobignore` がアプリのルート直下にあるか確認する。変更後、約 30 秒待つ |

### 2.6 チームに配る・更新する

- **配る**: `.bob/` と `.bobignore` を Git にコミットします。`git pull` したメンバーは、同じスキルとモードをそのまま使えます。
- **自分の全プロジェクトで使う**: スキルは `~/.bob/skills/fde-solution-dev/`、モードは `~/.bob/settings/custom_modes.yaml`(Bob Settings > Modes > Edit Global Modes)に置きます。同じ名前がある場合は、プロジェクトのものが優先されます。
- **更新する**: ファイルを直接編集して保存します。スキルは `SKILL.md` や補助ファイルを、モードは `custom_modes.yaml` や `rules-fde-dev/` を直します。画面を開いたままで反映されないときは、手順6の再読み込みを行います。

> Step 4 の本文には `.bob/skills/sales-api.md` とありますが、現行の Bob はフォルダ形式(`.bob/skills/<スキル名>/SKILL.md`)です。補助ファイルを同じフォルダに置けるため、このキットはフォルダ形式にしています。

## 3. 使い方

1. チャット下部のモード選択から **🧭 FDE開発者** を選びます。
2. 観察の成果物とソリューション案を渡して依頼します。例:

```text
@/ohno/FDEインターン_業務観察企画.md
@/ohno/FDEインターン_業務フロー詳細設計.md
ソリューション案は「AIチケットトリアージ支援」です。
/fde-solution-dev に従って、評価と機能要件の一覧化から始めてください。
```

3. Bob は次の順で進め、各段階で止まって確認します。

| Step | 内容 | 成果物 |
|---|---|---|
| 0 | 入力の確認(対象業務、課題と根拠、案) | — |
| 1 | 案の評価と絞り込み(ゲートと採点) | `docs/fde/00_evaluation.md` |
| 2 | 機能要件の一覧化 | `docs/fde/01_requirements.md` |
| 3 | RAG 要否の判定 | — |
| 4 | 必要リソースの一覧化と配置先の指定 | `docs/fde/02_resources.md` |
| 5 | 実装と検証(テスト、Lint、型チェック) | コード |
| 6 | 現場への定着と知見の還元 | `docs/fde/03_adoption_and_learnings.md` |

### RAG の分岐(Step 3)

| 場合 | Bob の動き |
|---|---|
| RAG ベース(FAQ・手順書・過去チケットの検索で回答や判断の根拠を出す) | サンプルアセットの `README.md` → `Day2開発案内/サンプルアセットアプリ紹介.md` → `openapi/helpdesk-api.yaml` → `backend/src/helpdesk/` の順に読み、再利用できる部分は流用して差分だけ作る |
| RAG ベースでない | サンプルアセットは読まず、そのまま Step 4 以降へ進む |

サンプルアセットの利用は必須ではありません。案に合う部分だけ使ってください。

## 4. 評価基準(要約)

詳細は [evaluation-criteria.md](bob_template/.bob/skills/fde-solution-dev/evaluation-criteria.md) を参照してください。

**ゲート(1 つでも「いいえ」なら先に修正)**

| ID | 確認事項 |
|---|---|
| G1 | 観察した事実に紐づいている |
| G2 | 架空データ等のみを使い、個人情報・機密を LLM・ログ・Git に渡さない |
| G3 | AI の出力を人が確認・承認する境界がある |
| G4 | 期間内に動くプロトタイプを見せられる |

**採点(100 点満点)**

| 観点 | 重み | FDE の考え方との対応 |
|---|---|---|
| 深く理解する | 20 | 観察の事実から真の困りごとを説明できるか |
| 早く解決する | 20 | 最小機能で素早く動かし、効果を測れるか |
| 現場に定着する | 20 | 既存運用に載り、現場が自走できるか |
| 知見を還元する | 15 | 次の現場で再利用できる部品や手順が残るか |
| 武器を活かす | 15 | IBM 製品やサンプルアセットを再利用しているか |
| スコープとオーナーシップ | 10 | やる/やらないが明確で、リスクを自分で説明できるか |

AI を含む案は、評価用データで判定の一致率、根拠の付与率、情報不足の検知、人の修正率も測ります。

## 5. 各部品の編集ポイント

| やりたいこと | 編集するファイル |
|---|---|
| 評価の観点や重みを変える | `skills/fde-solution-dev/evaluation-criteria.md` |
| 要件の書式を変える | `skills/fde-solution-dev/requirements-template.md` |
| 配置先をアプリの構成に合わせる | `skills/fde-solution-dev/resource-placement.md` |
| 進め方の順序を変える | `skills/fde-solution-dev/SKILL.md` |
| モードの名前、役割、使えるツールを変える | `custom_modes.yaml` |
| 常に守らせたいルールを足す | `rules-fde-dev/` に `02-xxx.md` を追加(ファイル名順に読み込まれる) |

モードの `groups` は `read`、`edit`、`execute`、`skill`、`todo`、`subtask`、`mode` を許可しています。
`mcp` や `subagent` は許可していません。必要になったら追加してください。

## 6. 注意

- `.env` は `.bobignore` で Bob から隠しています。API Key をチャットに貼らないでください。
- 先に手元で内容を読み、チームの方針に合わせて直してから配ってください。
- 配布対象の `.bobignore` は、サンプルアセットの構成(`data/runtime/`、`data/index/`)に合わせています。別構成のアプリでは見直してください。
- AI が作った要件、コード、評価は、そのまま信頼せず、人が確認してください。

## 7. 動作確認

1. モード一覧に「🧭 FDE開発者」が表示される。
2. 「ソリューション案の評価をしたい」と依頼すると、スキル `fde-solution-dev` が使われ、ゲートと採点の表が出る。
3. `.env` を `@` で渡しても、Bob が読めない(`.bobignore` が効いている)。

## 8. 用語の補足

| 用語 | 簡単な説明 |
|---|---|
| FDE | 顧客の現場に入り、業務課題の理解から解決策の実装・定着までを一貫して進めるエンジニアの役割。 |
| スキル | Bobに、特定の作業をどの手順・形式で進めるかを教える手順書。 |
| カスタムモード | Bobの役割、行動指針、利用できるツールを作業目的に合わせて切り替える設定。 |
| プロジェクトルート | 対象アプリの最上位フォルダー。`.bob/`や`README.md`などを置く基準位置。 |
| Workspace | IDEで現在開いている作業対象のフォルダーやフォルダー群。 |
| Scope | 設定を現在のプロジェクトだけに適用するか、すべてのプロジェクトに適用するかという範囲。 |
| YAML／Slug | YAMLは設定を記述する形式、Slugは設定項目を内部で一意に識別する短い名前。 |
| GitのCommit／Pull | Commitは変更履歴を記録する操作、Pullは共有先の最新変更を手元へ取り込む操作。 |
| ゲート | 採点の前に、案を進めてよいか最低条件を確認する判定。 |
| プロトタイプ | 解決策の価値や実現性を確かめるために作る試作品。完成品や本番運用を前提としない。 |
| RAG | 関連文書を検索し、その内容を根拠としてAIに回答を作らせる方式。 |
| LLM | 入力された文章をもとに、回答などの文章を生成するAIモデル。 |
| Lint／型チェック | Lintは書式や問題のある書き方を、型チェックはデータ型の不整合を検査する。 |
| `.bobignore` | Bobに読み込ませないファイルやフォルダーを指定する設定ファイル。 |
