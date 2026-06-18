# Search Console Review Template

`problem_solution` 記事を公開した後、Search Console の実績を見て改善判断するための運用テンプレートです。

対象:

- `problem_solution` 記事
- 下書きから公開した記事
- NotebookLM / SERP_ANALYSIS を使って作成した記事

Search Console の数値は改善判断の材料です。単独で結論を出さず、SERP、本文内容、公式情報、内部リンク状況と合わせて確認します。

## Basic Info

- article_title:
- slug:
- url:
- article_type: problem_solution
- published_at:
- review_date:
- review_timing: 30_days / 90_days
- related_product:
- related_parent_article:
- SERP_ANALYSIS file:
- NotebookLM used: yes / no

## Search Console Metrics

| Metric | Value | Notes |
| --- | ---: | --- |
| clicks |  |  |
| impressions |  |  |
| CTR |  |  |
| average_position |  |  |
| indexed | yes/no |  |
| main_query_count |  |  |
| unexpected_query_count |  |  |

## Main Queries

想定していた検索意図と一致するクエリを記録します。

| Query | Clicks | Impressions | CTR | Position | Intent Match |
| --- | ---: | ---: | ---: | ---: | --- |
|  |  |  |  |  | high/medium/low |
|  |  |  |  |  | high/medium/low |
|  |  |  |  |  | high/medium/low |

## Unexpected Queries

想定外だが拾えているクエリを記録します。

| Query | Clicks | Impressions | CTR | Position | Action |
| --- | ---: | ---: | ---: | ---: | --- |
|  |  |  |  |  | keep/rewrite/new_article |
|  |  |  |  |  | keep/rewrite/new_article |

## 30-Day Review

公開30日後は、初動確認と検索意図のズレ確認を中心に見ます。

### Check Items

- インデックスされているか
- 想定クエリで表示されているか
- 表示回数が発生しているか
- タイトルと検索意図がズレていないか
- FAQ系クエリを拾っているか
- 親記事・関連商品記事との内部リンクが機能しているか
- NotebookLMで想定した読者不安と実クエリが一致しているか
- SERP_ANALYSISで想定したFAQ候補が当たっているか

### 30-Day Decision

| Decision | Condition | Action |
| --- | --- | --- |
| keep | impressionsが出始め、想定クエリと合っている | 90日まで様子見 |
| title_meta_review | impressionsあり、CTRが低い | title/description候補を見直す |
| intent_adjust | 想定外クエリが多い | 見出し・FAQの追加候補を検討 |
| internal_link_add | 表示が弱いが関連親記事がある | 内部リンク追加を検討 |
| hold | impressionsが少ない | 90日まで様子見 |

## 90-Day Review

公開90日後は、リライト・関連記事追加・内部リンク強化の判断を行います。

### Check Items

- 主要クエリの平均掲載順位
- 表示回数の伸び
- CTRの低さ
- クリックが発生しているクエリ
- 想定外クエリの有望度
- SERP上位との差分
- FAQの不足
- 購入前チェック項目の不足
- 関連商品への導線が自然か
- 追加すべきproblem_solution記事があるか

### 90-Day Decision

| Decision | Condition | Action |
| --- | --- | --- |
| keep | 順位・CTR・検索意図が安定 | 維持 |
| rewrite_light | 8〜30位で表示あり、CTR低め | title/見出し/FAQを軽く改善 |
| rewrite_deep | 表示あり、順位が伸びない | SERP再分析、構成見直し |
| add_support_article | 想定外クエリに需要あり | 新規problem_solution候補へ |
| merge_or_hold | 表示が少なく意図も弱い | 保留または関連記事へ統合検討 |

## Improvement Target Rules

改善対象にする条件です。

### High Priority

- impressions が多いが CTR が低い
- average_position が 8〜30 位
- 想定クエリと本文内容がズレている
- FAQ系クエリが多いのにFAQが弱い
- 購入前チェック系クエリが多いのにチェックリストが弱い
- 親記事・関連商品記事へ内部リンクできる余地がある

### Medium Priority

- impressions は中程度
- average_position が 20〜50 位
- 想定外クエリが多い
- NotebookLM分析で拾った論点と実クエリが一部ズレている

### Low Priority

- impressions が少ない
- query が曖昧
- サイト方針とズレる
- 公式確認が多く、リライト負荷が高い

## Rewrite Candidate Rules

リライト候補として抽出する条件です。

### Title / Description Rewrite

- impressions はあるが CTR が低い
- query と title の表現がズレている
- 「選び方」「注意点」「対策」などの検索語が title に反映されていない

### FAQ Rewrite

- FAQ系クエリが出ている
- `とは`, `違い`, `使える`, `できない`, `必要か` が含まれる
- 現本文に該当FAQがない

### Section Rewrite

- 購入前不安のクエリが出ている
- 本文中で回答が浅い
- 公式確認が必要な情報を断定している可能性がある

### New Article Candidate

- 想定外クエリの impressions が多い
- 既存記事に入れると主題がブレる
- `対策`, `原因`, `選び方`, `比較`, `必要か` のように独立記事化しやすい

## NotebookLM Effectiveness Review

NotebookLM分析が有効だったか確認します。

| Item | Result | Notes |
| --- | --- | --- |
| Search intent matched actual queries | yes/no/partial |  |
| FAQ candidates matched queries | yes/no/partial |  |
| Reader concerns matched queries | yes/no/partial |  |
| Competitor gaps helped differentiation | yes/no/partial |  |
| Missing topics found after publish | yes/no |  |

改善判断:

- NotebookLMが拾ったFAQが実クエリと合っているなら継続
- 実クエリとズレているなら、投入資料や質問テンプレートを見直す
- 公式確認が必要な情報が多すぎる場合は、NotebookLM出力を本文素材にしすぎない

## SERP_ANALYSIS Improvement Review

`SERP_ANALYSIS.md` の精度を確認します。

- Search Intent Priority は合っていたか
- Reader Concerns は実クエリと一致したか
- FAQ Candidates は検索クエリに出たか
- Purchase Checklist は本文内で役に立ったか
- Competitor Gaps は差別化につながったか
- Differentiation Points は本文に自然に反映できたか

改善メモ:

- 
- 
- 

## Action Plan

次に行う作業を決めます。

| Action | Target | Priority | Owner | Notes |
| --- | --- | --- | --- | --- |
| keep |  |  |  |  |
| rewrite |  |  |  |  |
| add_internal_link |  |  |  |  |
| new_article |  |  |  |  |

## Final Decision

- final_decision: keep / rewrite_light / rewrite_deep / add_support_article / hold
- reason:
- next_review_date:
