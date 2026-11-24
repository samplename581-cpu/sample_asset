# FAQ Chatbot — 仕様書兼実装計画

## 概要

**目的**  
問い合わせ窓口社員が、顧客から届いた問い合わせ内容のキーワードを入力するだけで、
既存 FAQ に基づく「問い合わせ内容の候補」が表示され、
候補をクリックすると「コピペ可能な回答文」が表示されるチャットボット UI を追加する。

**スコープ（今回対象）**
- 新規の画面「FAQ キーワード検索」の追加（`frontend/`）
- バックエンド側の新 API エンドポイント `GET /api/v1/faq/suggest` の追加（`backend/`）
- 既存の FAQ データ（`data/seed/documents.json`）をそのまま使用

**スコープ外（将来対応）**
- ログイン認証・ロール制御
- FAQ 管理画面（追加・編集・削除）
- AI/類義語によるあいまい検索（現在はシンプルな部分一致）
- CSV インポート機能（現在は既存 JSON をそのまま活用）

---

## アーキテクチャ概要

```
[社員ブラウザ]
  ↓ キーワード入力
[frontend/faq.html + faq.js]
  ↓ GET /api/v1/faq/suggest?q=キーワード
[backend: api/faq.py]
  ↓ documents.json を部分一致検索
[data/seed/documents.json] ← FAQデータ（既存）
  ↑ { faq_id, title, answer } リスト返却
[frontend] 候補リスト表示
  ↓ 候補クリック
[frontend] 回答文をテキストエリアに展開 → コピーボタンで即コピー
```

---

## データ構造

**既存 FAQ データ（`data/seed/documents.json`）の構造（抜粋）：**

```json
{
  "document_id": "faq:FAQ-01",
  "title": "配送予定日はいつ分かりますか",
  "body": "質問: 配送予定日はいつ分かりますか\n回答: ご注文の確定後、3営業日以内に配送予定日をメールでお知らせいたします。\n窓口対応: はい",
  "document_type": "faq",
  "category": "配送関連",
  "faq_id": "FAQ-01",
  "completion_policy": "はい"
}
```

**データ確認結果（全15件を目視確認済み）：**

| 項目 | 確認結果 |
|------|----------|
| `body` のフォーマット | 全件 `質問: …\n回答: …\n窓口対応: …` の3行構造で**完全に統一** |
| コロンの種類 | 全件 **半角コロン** `:`（全角 `：` は使われていない） |
| 回答の後続テキスト | 全件 `\n窓口対応: …` が続く → 回答の終端を安全に判定できる |
| 検索対象タイプ | `document_type == "faq"` のみ（`classification_rule` / `priority_rule` は除外） |

**回答文の抽出ロジック（バックエンド・フロントエンド共通の仕様）：**

1. `body` 中の `\n回答: ` を検索する
2. 見つかった場合、その直後から `\n窓口対応:` の直前までを回答文とする
3. 手順1または2でマーカーが見つからない場合は `answer` を `null` とする
4. フロントエンドは `answer == null` のとき、コピーボタンを非表示にし、
   「回答文を抽出できませんでした」と表示する

---

## サブタスク

---

### サブタスク 1 — バックエンド: FAQ 候補検索 API の追加

**ステータス:** [ ] pending

**Intent**  
キーワードを受け取り、FAQ タイトル・本文に対してシンプルな部分一致検索を行い、
マッチした FAQ の一覧（faq_id, title, answer）を返す API エンドポイントを追加する。

**Expected Outcomes**
- `GET /api/v1/faq/suggest?q=配送` を呼ぶと、"配送" を含む FAQ の一覧が JSON で返る
- 各アイテムには `faq_id`, `title`, `answer`（顧客向け回答文のみ、抽出失敗時は `null`）, `category` が含まれる
- 検索対象は `document_type == "faq"` かつ `is_active == true` のドキュメントのみ
- マッチ件数の上限は 20 件（`limit` クエリパラメータで変更可能、最大 50）
- 大文字小文字を区別しない（`casefold()` による正規化）

**ランキングルール：**
- スコアリング: `title` のキーワード出現数 × 2 + `body` のキーワード出現数 × 1
  （キーワードが複数ある場合は各語のスコアを合算）
- 同スコアの場合は `faq_id` の昇順（元の順序を維持）

**回答文の抽出ロジック（バックエンド側で実行）：**
- `body` から `\n回答: ` の直後から `\n窓口対応:` の直前までを切り出す
- どちらかのマーカーが見つからない場合は `answer = null` を返す

**Todo List**
1. `backend/src/helpdesk/api/faq.py` を新規作成
   - `GET /faq/suggest` エンドポイントを定義
   - クエリパラメータ: `q: str`（1〜200文字）、`limit: int`（デフォルト20、最大50）
   - 起動時に `SEED_DATA_DIR/documents.json` をメモリに読み込む（`lifespan` または起動処理に追加）
   - `document_type == "faq"` かつ `is_active == true` でフィルタ
   - キーワード部分一致とスコアリングを適用し、上位 `limit` 件を返す
   - 回答文は `body` から抽出。失敗時は `answer: null`
   - レスポンス: `{ items: [ { faq_id, title, answer, category } ] }`
2. `backend/src/helpdesk/main.py` に `faq_router` を import して `include_router` に追加

**Relevant Context**
- 参照ファイル: `backend/src/helpdesk/api/rag.py`（エンドポイントのパターン）
- 参照ファイル: `backend/src/helpdesk/main.py`（ルーター登録方法・`lifespan` の書き方）
- 参照ファイル: `data/seed/documents.json`（FAQ データ構造・全15件確認済み）
- 参照ファイル: `backend/src/helpdesk/config.py`（`SEED_DATA_DIR` の設定値確認）

---

### サブタスク 2 — フロントエンド: FAQ キーワード検索ページの追加

**ステータス:** [ ] pending

**Intent**  
社員が使う「FAQ キーワード検索」の画面を新規 HTML/JS ファイルとして追加する。
既存の `index.html` のデザイン（CSSクラス）を流用し、UI の一貫性を保つ。

**Expected Outcomes**
- `frontend/faq.html` を開くと、キーワード入力欄と候補リストが表示される
- キーワードを入力するたびに（入力から 300ms の debounce で）API を呼びリストを更新する
- 候補リストの各アイテムには **FAQ タイトルとカテゴリ** が表示される
- アイテムをクリックすると、右ペインにタイトルと回答文がテキストエリアで表示される
- `answer != null` のときのみコピーボタンを表示。クリックするとクリップボードにコピーされ、
  ボタンのラベルが一時的に「コピーしました ✓」に変わる
- `answer == null` のときは「回答文を抽出できませんでした」と表示し、コピーボタンは非表示
- キーワードが空のとき、またはマッチ件数が 0 のときは適切なメッセージを表示する

**Todo List**
1. `frontend/faq.html` を新規作成
   - ヘッダーに「FAQ キーワード検索」タイトルと、`index.html` へ戻るリンク（`<a href="/">`）
   - 左ペイン: キーワード入力欄 + 候補リスト（`<ul id="faqList" class="ticket-list">`）
   - 右ペイン: 選択した FAQ のタイトル・回答テキストエリア・コピーボタン
   - `style.css`（既存）と `faq.js`（新規）を参照
2. `frontend/faq.js` を新規作成
   - `API_BASE` の定義（`app.js` と同じ方式）
   - キーワード入力イベントに 300ms debounce を設定
   - `fetchSuggestions(q)`: `GET /api/v1/faq/suggest?q=...` を呼びリストを描画
     - 各 `<li>` にはタイトル（`.t-title`）とカテゴリ（`.t-status`）を表示
   - `selectFaq(item)`: 右ペインにタイトルと回答文を表示、`answer` の null チェックでコピーボタン表示制御
   - `copyAnswer()`: `navigator.clipboard.writeText()` でコピー、ボタンラベルを「コピーしました ✓」に変更後 2 秒で戻す
3. `frontend/index.html` のトップバーに「FAQ 検索」リンクボタン（`<a>` タグ）を追加する
   - 既存の `<button id="btnNewInquiry">` の左隣に配置

**Relevant Context**
- 参照ファイル: `frontend/index.html`（レイアウト・CSSクラスのパターン）
- 参照ファイル: `frontend/app.js`（`apiFetch`関数・DOM操作パターン・`API_BASE`定義）
- 参照ファイル: `frontend/style.css`（使用可能なCSSクラス一覧 — 確認済み）
  - 再利用するクラス: `.topbar`, `.app-title`, `.layout`, `.pane-left`, `.pane-right`, `.filter-row`,
    `.ticket-list`, `.t-title`, `.t-status`, `.ticket-list li.active`, `.btn-primary`, `.btn-secondary`,
    `.hidden`, `.loading`, `.error-box`, `.description`, `.meta-text`, `textarea`, `.warning-box`
  - FAQ ページ専用の追加スタイルは `faq.html` の `<style>` タグ内に `.faq-` プレフィックスで記述
- XSS 対策のため、回答文の表示は `<textarea>.value` を使う（`innerHTML` 不可）

---

### サブタスク 3 — 動作確認・調整

**ステータス:** [ ] pending

**Intent**  
追加した API とUI が正しく連携して動作することを確認し、
ユーザーが実際に使える状態に仕上げる。

**Expected Outcomes**
- `make index`（またはサーバー起動）後、ブラウザで `faq.html` を開いて検索が動作する
- キーワード「配送」で FAQ-01〜FAQ-04 など複数の候補が表示される
- 候補をクリックすると回答文が表示され、コピーボタンが機能する
- 検索結果が 0 件のとき「見つかりませんでした」と表示される

**Todo List**
1. ローカル環境でサーバーを起動し、ブラウザで `http://localhost:8000/faq.html` を開く
2. キーワード「配送」→ FAQ-01〜05 が表示されることを確認
3. キーワード「キャンセル」→ FAQ-10・11 が表示されることを確認
4. `title` にキーワードを含む FAQ が `body` のみ一致の FAQ より上位に表示されることを確認
5. 各候補をクリックして回答文が正しく表示されることを確認
6. コピーボタンを押してテキストが実際にクリップボードに入ることを確認
7. 空文字列・記号のみ入力など境界値のUIが崩れないことを確認
8. `index.html` のトップバーから `faq.html` へのリンクが正常に動作することを確認

**Relevant Context**
- サーバー起動方法は `README.md` または `Makefile` を参照
- バックエンドの確認には `curl 'http://localhost:8000/api/v1/faq/suggest?q=配送'` を使用可能

---

## 非機能要件

| 項目 | 仕様 |
|------|------|
| 検索方式 | 部分一致（`casefold()` で正規化、大文字小文字区別なし）|
| ランキング | `title` ヒット数 × 2 + `body` ヒット数 × 1 の合計スコアで降順ソート |
| 検索対象フィールド | `title` と `body` |
| 検索対象ドキュメント | `document_type == "faq"` かつ `is_active == true` のみ |
| 最大表示件数 | 20 件（`limit` パラメータ最大 50） |
| 回答文の抽出 | `\n回答: ` ～ `\n窓口対応:` 間のテキスト。失敗時は `answer: null` |
| コピー対象 | `answer != null` のとき限定。`null` のときはコピーボタン非表示 |
| レスポンス時間 | JSON の線形スキャン（全15件）のため < 10ms を期待 |
| セキュリティ | XSS 対策: 全 DOM 書き込みは `textContent` / `<textarea>.value` を使用 |
| ブラウザ対応 | Chrome / Firefox / Edge 最新版（Clipboard API 対応必須） |
| 認証 | なし（社内ネットワーク前提・将来追加可能な構造にしておく） |

---

## ファイル変更一覧

| ファイル | 変更種別 | 説明 |
|----------|----------|------|
| `backend/src/helpdesk/api/faq.py` | 新規作成 | FAQ 候補検索 API |
| `backend/src/helpdesk/main.py` | 変更 | `faq_router` を登録 |
| `frontend/faq.html` | 新規作成 | FAQ 検索 UI |
| `frontend/faq.js` | 新規作成 | FAQ 検索ロジック |
| `frontend/index.html` | 変更（任意） | FAQ 検索ページへのリンク追加 |
