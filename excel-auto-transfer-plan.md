# Excel自動転記機能 実装プラン（改訂版）

## 概要

**目標：** アプリの問い合わせフォーム（「＋新規問い合わせ」）から受け付けた問い合わせを、手動転記なしで問い合わせ管理シート（`inquiry_management.xlsx` 形式）に自動で反映する。

**背景・制約：**
- インターン課題のMock環境であり、実際にメールは送受信しない
- フォーム送信からチケット保存（`POST /api/v1/tickets` → `data/runtime/tickets.json`）は**既存機能をそのまま使う**。新しい受付口は作らない
- **正（マスター）は `tickets.json`** とし、Excelはそこから作る「出力」と位置付ける。Excelへの書き込みが失敗しても、`tickets.json` から作り直せる状態を保つ
- 現場の運用（1枚の一覧に上から順に記録し、黄色セルは窓口担当が判定する）を変えない
- `openpyxl` はすでに [`pyproject.toml`](pyproject.toml) に含まれており追加不要
- 氏名・メールアドレスはExcel（`data/runtime/`、Git管理対象外）にのみ保存する。LLM・ログ・Gitには渡さない

**スコープ外（今後の課題）：**
- 実際のメール受信、メールフォームサービス（Formspree等）・Webhookとの連携
- 新しい受付エンドポイントの追加（Webhookのモックを含む）
- 月別・日別のシート自動作成、集計シートの数式の書き換え
- 担当者がExcel上で入力した判定結果をアプリへ取り込む処理
- LLMによるカテゴリ・緊急度の自動判定、内容の要約
- 認証・アクセス制御

---

## 用語

| 用語 | 意味 |
|---|---|
| テンプレート | `assets/source/business_tools/inquiry_management.xlsx`。書式・入力規則・集計シートの元。**このファイルには書き込まない** |
| 出力ファイル | `data/runtime/inquiry_management.xlsx`。本機能が書き込むファイル |
| 見出し行 | A列の値が「受付番号」である行 |
| データ行 | 見出し行の次の行から、入力規則の最終行（現行テンプレートでは5〜204行目）まで |
| 空き行 | データ行のうち、「受付番号」列が空の行 |

---

## アーキテクチャ

```
アプリ画面「＋新規問い合わせ」（既存）
    ↓ POST /api/v1/tickets（既存）
TicketService.create_ticket()       ← 既存
    ↓
tickets.json に保存                  ← 既存（正）
    ↓
SheetExportService.append_ticket()  ← 今回新規作成
    ↓
data/runtime/inquiry_management.xlsx（出力ファイル）

【復旧・再同期】
backend/scripts/export_inquiry_sheet.py   ← 今回新規作成
    tickets.json の全件 → 出力ファイルを作り直す
```

---

## フィールド対応表

列は**列の記号（A, B…）ではなく、見出し行の見出し名で特定する**。テンプレートによって列の位置が異なるため（受領した管理シートは「メールアドレス」列を含む14列、サンプルアセットのテンプレートは13列）。

| 見出し名 | Ticketモデルのフィールド | 自動 / 手動 | 書き込む値 |
|---|---|---|---|
| 受付番号 | `ticket_id` | 自動 | Backendが発行した値をそのまま（例：`TKT-…`） |
| 受付日時 | `created_at` | 自動 | 日本時間（Asia/Tokyo）に変換し、`yyyy/mm/dd hh:mm` 形式で表示 |
| お客様名 | `customer_name` | 自動 | フォーム入力値 |
| メールアドレス | `customer_email` | 自動 | フォーム入力値。**見出しがあるテンプレートの場合のみ**書き込む |
| 注文番号 | `order_number` | 自動 | フォーム入力値。未入力なら「—」 |
| 商品名 | `product_name` | 自動 | フォーム入力値。未入力なら「—」 |
| 問い合わせ内容（要約） | `description` | 自動 | **フォーム入力の原文をそのまま**入れる（要約はしない） |
| カテゴリ | `category` | 手動 | 空欄（窓口担当が判定） |
| 緊急度 | `priority` | 手動 | 空欄（窓口担当が判定） |
| 対応区分 | `handling_type` | 手動 | 空欄（窓口担当が判定） |
| 担当 | `assigned_team` | 手動 | 空欄（窓口担当が判定） |
| ステータス | `status` | 自動 | チケットの値（作成時は「未対応」） |
| FAQ番号 | `faq_id` | 手動 | 空欄（窓口担当が判定） |
| 備考 | `notes` | 手動 | 空欄。ただし `has_attachment` が真なら「写真あり」 |

※ 再出力（サブタスク3）では、手動列もチケットに値があればその値を書き込む。

---

## 書き込みルール

1. **追記位置**：最初の空き行に書き込む。**行の挿入はしない**（集計シートの数式・入力規則・黄色セルの書式がずれるため）。新着は下に追記される。担当者はExcelの並び替え・絞り込み機能で対応する
2. **書式**：テンプレートの書式・入力規則（プルダウン）を残したまま、セルの値だけを書き込む
3. **重複防止**：「受付番号」列に同じ値がすでにある場合は書き込まない（何度実行しても結果が同じになる）
4. **出力ファイルがない場合**：テンプレートをコピーし、テンプレートに入っている既存データ行をすべて空にしてから書き込む
5. **保存方法**：一時ファイルに保存してから置き換える（`ticket_json.py` の `_save_atomic` と同じ方針）。同時書き込みはスレッドロックで防ぐ
6. **例外時の振る舞い**

| 状況 | 振る舞い |
|---|---|
| 出力ファイルが開かれていて保存できない | Excelへの書き込みを諦め、エラーをログに記録する。チケットの保存とAPIの応答は成功のまま |
| 空き行がない（データ行の上限に達した） | 同上 |
| 見出し行が見つからない、必要な見出しがない | 同上。起動時にも検査し、問題があれば起動ログに警告を出す |
| 上記いずれの場合も | 復旧は再出力スクリプト（サブタスク3）で行う。**失敗したまま放置しない運用**を README に書く |

7. **ログ**：ログに出すのは `ticket_id` とエラーの種類だけ。氏名・メールアドレス・問い合わせ内容は出さない

---

## サブタスク一覧

---

### サブタスク 1：Excel書き出し部品（ポートとアダプター）を作成する

**Status:** `[ ] pending`

**Intent:**
チケット1件を、書き込みルールに従って出力ファイルの空き行に書き込む部品を作る。既存のポートとアダプターの構成にならう。

**Expected Outcomes:**
- `append_ticket(ticket)` を呼ぶと、出力ファイルの最初の空き行にデータが入る
- 同じチケットを2回渡しても、行は1行しか増えない
- 受領した管理シート（14列）とサンプルアセットのテンプレート（13列）のどちらをテンプレートにしても動く
- 集計シートの「未判定」が、書き込んだ件数だけ増える

**Todo List:**
1. `backend/src/helpdesk/ports/sheet_exporter.py` にポート（抽象基底クラス）を定義する（`append_ticket(ticket)`、`rebuild(tickets)`）
2. `backend/src/helpdesk/adapters/sheet_excel.py` に `ExcelSheetExporter` を実装する
   - 見出し行の検出と、見出し名から列番号への対応表づくり
   - 空き行の検出、重複チェック、値の書き込み
   - 一時ファイル経由の保存、スレッドロック
3. `backend/src/helpdesk/config.py` に `SHEET_TEMPLATE_PATH` と `SHEET_OUTPUT_PATH` を追加する（既定値は上記の用語表のパス）
4. `.env.example` に上記2項目を追記する
5. 単体テストを `backend/tests/unit/test_sheet_excel.py` に追加する（受け入れ条件を参照）

**Relevant Context:**
- [`assets/source/business_tools/inquiry_management.xlsx`](assets/source/business_tools/inquiry_management.xlsx) ← テンプレート（見出し・入力規則・集計シート）
- [`backend/src/helpdesk/adapters/ticket_json.py`](backend/src/helpdesk/adapters/ticket_json.py) ← `_save_atomic` と `_lock` のパターンを踏襲する
- [`backend/src/helpdesk/domain/models.py`](backend/src/helpdesk/domain/models.py) ← `Ticket` モデル
- [`backend/src/helpdesk/config.py`](backend/src/helpdesk/config.py) ← 設定追加先

---

### サブタスク 2：チケット作成時に自動で書き出す

**Status:** `[ ] pending`

**Intent:**
`POST /api/v1/tickets` でチケットが作成されたら、サブタスク1の部品を呼んで出力ファイルに追記する。

**Expected Outcomes:**
- アプリ画面から送信 → `tickets.json` に保存 → 出力ファイルに1行追記、が一連で動く
- Excelへの書き込みに失敗しても、チケットは保存され、APIは成功を返す（失敗はログに記録）
- FastAPIの起動時に部品が初期化され、見出しの検査が行われる

**Todo List:**
1. [`backend/src/helpdesk/main.py`](backend/src/helpdesk/main.py) の `lifespan` 関数で `ExcelSheetExporter` を初期化し、`app.state.sheet_exporter` に格納する（`app.state.ticket_repository` の初期化パターンを踏襲）
2. [`backend/src/helpdesk/api/tickets.py`](backend/src/helpdesk/api/tickets.py) の `create_ticket` で、チケット作成後に `append_ticket(ticket)` を呼ぶ。例外は捕まえてログに記録する
3. 結合テストを `backend/tests/integration/` に追加する

**Relevant Context:**
- [`backend/src/helpdesk/main.py`](backend/src/helpdesk/main.py) ← `lifespan` 関数
- [`backend/src/helpdesk/api/tickets.py`](backend/src/helpdesk/api/tickets.py) ← `create_ticket` エンドポイント
- [`frontend/app.js`](frontend/app.js) ← 送信元（「＋新規問い合わせ」）。**変更しない**

---

### サブタスク 3：再出力スクリプトを作る（復旧・再同期用）

**Status:** `[ ] pending`

**Intent:**
`tickets.json` の全件から出力ファイルを作り直すスクリプトを用意し、書き込み失敗やファイル破損から復旧できるようにする。

**Expected Outcomes:**
- `uv run python backend/scripts/export_inquiry_sheet.py` を実行すると、テンプレートから出力ファイルが作り直され、全チケットが受付日時の古い順に並ぶ
- 何度実行しても同じ結果になる
- 実行前に出力ファイルが開かれている場合は、分かりやすいメッセージを出して終了する（上書きしない）

**Todo List:**
1. `backend/scripts/export_inquiry_sheet.py` を新規作成する（サブタスク1の `rebuild(tickets)` を呼ぶ）
2. README の「8. 検索文書再構築手順」の後ろに、使い方と「書き込み失敗時はこのスクリプトを実行する」旨を追記する
3. 単体テストを追加する

**Relevant Context:**
- [`backend/scripts/build_index.py`](backend/scripts/build_index.py) ← スクリプトの書き方を踏襲する
- [`backend/src/helpdesk/adapters/ticket_json.py`](backend/src/helpdesk/adapters/ticket_json.py) ← チケット全件の読み込み

---

## 実装順序

```
サブタスク1（書き出し部品）
    ↓
サブタスク2（作成時の自動書き出し）
    ↓
サブタスク3（再出力スクリプト）
```

サブタスク1は新規ファイルのみ、サブタスク2は既存ファイルへの小さな追加、サブタスク3は新規スクリプト。各サブタスクは独立してレビュー・確認できる。

---

## 受け入れ条件（テストで確認すること）

| # | 条件 |
|---|---|
| 1 | 1件送信すると、出力ファイルの行が1行増え、集計シートの「未判定」と「未対応」がそれぞれ1増える |
| 2 | 同じチケットを2回書き出しても、行は1行のまま |
| 3 | 追記してもテンプレートのプルダウン（カテゴリ・緊急度など）と黄色セルの書式が残っている |
| 4 | 14列のテンプレートでは「メールアドレス」列に、13列のテンプレートでは書き込まずに正常終了する |
| 5 | 受付日時が日本時間で表示される |
| 6 | 出力ファイルを開いたまま送信しても、チケットは保存され、APIは成功を返す。ログに個人情報が出ていない |
| 7 | 空き行がない状態で送信しても、チケットは保存され、APIは成功を返す |
| 8 | 再出力スクリプトを実行すると、全チケットが古い順に並び、2回実行しても結果が同じ |
| 9 | テンプレートファイルの中身が変わっていない |
| 10 | `make test`、`make lint`、`make typecheck` がすべて成功する |

---

## 確認事項（実装前にチームで決める）

| # | 確認事項 | 暫定の決定 |
|---|---|---|
| 1 | テンプレートは、受領した管理シート（14列、メールアドレスあり）とサンプルアセット（13列）のどちらを正とするか | 見出し名で列を特定するため、どちらでも動く作りにする。リポジトリにはサンプルアセットのものを置く |
| 2 | 担当者は出力ファイルを直接編集してよいか（サーバーの追記と人の保存が競合し、行が消えるおそれがある） | **出力ファイルは閲覧用とし、直接編集しない**。判定結果はアプリ（既存の `PATCH /api/v1/tickets`）で入力し、再出力でExcelに反映する。現場が受け入れない場合は、書き込み先を「新着取込」用の別シートにする案に切り替える |
| 3 | 管理シートの題名が「（2026年11月19日分）」となっており日別運用に見える。日付が変わったときの扱いは | 今回はスコープ外。1つの出力ファイルに追記し続ける。データ行の上限（200行）に達したら書き込み失敗として扱う |
| 4 | 受付番号の形式（現行の `Q1119-01` 形式に合わせるか） | Backendの `ticket_id` をそのまま使う |

---

## 将来の課題（スコープ外）

- メール受信・Webhookサービスとの連携と、受信時の署名検証
- 日別・月別のシート管理と集計範囲の自動更新
- Excelファイルのダウンロード用APIエンドポイント
- LLMによるカテゴリ・緊急度の判定案の書き込み（既存のRAG機能との統合。確定は人が行う）
