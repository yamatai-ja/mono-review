# Search Console Plan

Search Console の実績データを、RSS起点の記事候補・problem_solution 記事企画へ接続するための設計案です。

今回は実装しません。運用設計とCSV設計だけを定義します。

## Purpose

RSSは新商品・ニュース起点の発見に強く、Search Consoleは実際に検索されている悩み・比較・選び方の発見に強いです。

今後は以下の2系統を分けて運用します。

```text
RSS起点
新商品・新サービス・新製品ニュース
↓
商品名記事 / review / reputation / comparison
```

```text
Search Console起点
実際に表示・クリックされている検索クエリ
↓
problem_solution / FAQ / 比較補助記事 / リライト候補
```

## Metrics To Export

Search Console から取得・整理したい指標です。

| Metric | Purpose |
| --- | --- |
| query | 記事企画の元になる検索語 |
| page | 既存記事との対応確認 |
| clicks | すでに流入があるか |
| impressions | 需要の大きさ |
| ctr | タイトル・検索意図とのズレ確認 |
| position | 改善余地の大きさ |
| date_range | いつのデータか |
| device | モバイル/PC差の確認 |
| country | 日本向け確認 |

初期運用では、API連携せず Search Console からCSVエクスポートして手動投入する想定です。

## Query Types For problem_solution

problem_solution 候補に向きやすいクエリです。

| Query Pattern | Example | Article Fit |
| --- | --- | --- |
| 選び方 | `FeliCa対応 Androidスマホ 選び方` | high |
| 注意点 | `SIMフリー スマホ 注意点` | high |
| 対策 | `外付けSSD 接続が切れる 対策` | high |
| 原因 | `スマートウォッチ 通知 来ない 原因` | high |
| 比較 | `大画面スマホ 比較` | medium |
| 必要か | `microSD対応スマホ 必要か` | high |
| 使えない | `おサイフケータイ 使えない Android` | high |
| できない | `スマホ Suica 登録できない` | high |
| 代わり | `Apple Watch 高い 代わり` | medium |
| デメリット | `FeliCa Android デメリット` | medium |

商品名単体クエリは、基本的には商品記事・クラスタ記事向きです。悩み語と組み合わさっている場合のみ problem_solution 候補にします。

## output/search_console_candidates.csv Design

将来作る場合のCSV設計です。

```csv
query,page,clicks,impressions,ctr,position,date_range,detected_intent,article_type,candidate_title,target_slug,related_product_hint,related_article_slug,priority,reason,status,checked_at
```

### Columns

| Column | Role |
| --- | --- |
| query | Search Console の検索クエリ |
| page | 表示された既存URL |
| clicks | クリック数 |
| impressions | 表示回数 |
| ctr | CTR |
| position | 平均掲載順位 |
| date_range | 例: `last_28_days` |
| detected_intent | `howto`, `problem`, `comparison`, `faq`, `product`, `unknown` |
| article_type | 初期は `problem_solution` / `rewrite` / `faq_support` |
| candidate_title | 記事タイトル案 |
| target_slug | slug候補 |
| related_product_hint | 関連商品候補 |
| related_article_slug | 関連する既存記事 |
| priority | 1〜5 |
| reason | 優先度理由 |
| status | `candidate`, `needs_serp_analysis`, `ready_for_prompt`, `hold`, `reject` |
| checked_at | ISO timestamp |

### Sample Rows

```csv
query,page,clicks,impressions,ctr,position,date_range,detected_intent,article_type,candidate_title,target_slug,related_product_hint,related_article_slug,priority,reason,status,checked_at
FeliCa対応 Androidスマホ 選び方,/blog/motorola-edge-60/,3,240,1.25,18.4,last_28_days,problem,problem_solution,FeliCa対応Androidスマホの選び方と購入前チェック,felica-android-smartphone-selection,motorola edge 60,motorola-edge-60,5,impressions_high_position_improvable_problem_query,ready_for_prompt,2026-06-17T00:00:00Z
外付けSSD 接続が切れる 対策,/blog/,2,180,1.11,16.8,last_28_days,problem,problem_solution,外付けSSDの接続が切れる原因と対策,external-ssd-disconnect-fix,UGREEN Revodok Pro 314,,5,problem_query_existing_queue_match,needs_serp_analysis,2026-06-17T00:00:00Z
motorola edge 60 評判,/blog/motorola-edge-60/,4,90,4.44,9.2,last_28_days,product,rewrite,motorola edge 60の評判を見る前に知りたいポイント,motorola-edge-60-reputation,motorola edge 60,motorola-edge-60,3,product_cluster_query,hold,2026-06-17T00:00:00Z
```

## Priority Rules

初期の優先度案です。

### Priority 5

以下を満たすもの。

- impressions が多い
- position が 8〜30 位
- 悩み語がある
- 既存記事と内部リンクできる
- problem_solution にできる
- 商品押し売りなしで自然に関連商品を紹介できる

例:

- `選び方`
- `注意点`
- `対策`
- `原因`
- `必要か`
- `使えない`

### Priority 4

- impressions は中程度
- position が 10〜40 位
- FAQや補助記事に向く
- 既存記事の補完になる

### Priority 3

- 商品名クエリ寄り
- cluster記事や既存記事リライト向き
- problem_solution にはやや弱い

### Priority 2

- impressions が少ない
- 検索意図が曖昧
- 公式確認が多く必要

### Priority 1

- サイト方針とズレる
- 金融、医療、法律など対象外
- ニュース性が強すぎて長期SEOになりにくい

## Integration With product_problem_mapper.py

`product_problem_mapper.py` は現在、以下を入力にしています。

1. `data/article_queue.csv`
2. `data/products.csv`
3. `data/rss_items.csv`

将来的には第4入力として以下を追加できます。

```text
output/search_console_candidates.csv
```

連携案:

```text
Search Console CSV export
↓
search_console_candidates.csv
↓
product_problem_mapper.py
↓
output/problem_keyword_candidates.csv
↓
problem_prompt_builder.py
```

ただし、Search Console起点のクエリはすでに検索需要が見えているため、`product_problem_mapper.py` で無理にテンプレ展開しすぎない方が安全です。

おすすめ:

- Search Console起点は `problem_keyword` をそのまま活かす
- 商品名は `recommended_product_hint` に留める
- `reason` に Search Console指標を残す
- `status=needs_serp_analysis` を挟む

## RSS vs Search Console

| Source | Strength | Best Use |
| --- | --- | --- |
| RSS | 新商品・ニュース・セール発見 | 商品名記事、review、comparison、クラスタ記事 |
| Search Console | 実検索需要・改善余地発見 | problem_solution、FAQ、リライト、内部リンク補強 |
| SERP分析 | 検索意図・競合差分把握 | 本文生成前の品質向上 |
| NotebookLM | 論点整理・FAQ抽出 | SERP分析補助、人間確認前提 |

## Operating Flow

```text
Search Console export
↓
search_console_candidates.csv に整理
↓
priority 4〜5 を選ぶ
↓
SERP_ANALYSIS.md を作成
↓
NotebookLMで論点整理
↓
人間が公式確認
↓
problem_prompt_builder.py
↓
GPTs本文
↓
process_article.py
```

## Human Review Required

Search Consoleデータは検索需要のヒントであり、記事化可否の最終判断ではありません。

人間確認が必要なもの:

- クエリの検索意図
- 既存記事との重複
- 商品紹介が自然か
- 公式情報の確認
- SERP上位記事の傾向
- 競合が弱い論点の妥当性

## First 5-Article Review

Search Console活用を5記事運用したら、以下を見直します。

- `priority` ルールが実際の流入に合っているか
- impressions重視か、position改善余地重視か
- problem_solution に向かないクエリを拾いすぎていないか
- RSS起点記事との内部リンクが増えているか
- FAQ見出しがSearch Consoleクエリを拾っているか
- SERP分析にかかる手間が重すぎないか
- `search_console_candidates.csv` を自動生成する価値があるか

## Future Automation Ideas

### `search_console_candidate_builder.py`

Search ConsoleエクスポートCSVを読み、`output/search_console_candidates.csv` を生成します。

初期機能:

- query分類
- priority算出
- related article推定
- problem_solution候補抽出

### `serp_report_builder.py`

`search_console_candidates.csv` の1行から `output/serp_analysis/{slug}.md` を生成します。

### `problem_prompt_builder.py` integration

将来的に以下を受け取れるようにします。

```powershell
python src\problem_prompt_builder.py `
  --keyword "FeliCa対応 Androidスマホ 選び方" `
  --serp-report output\serp_analysis\felica-android-smartphone-selection.md `
  --apply
```

ただし初期運用では、人間確認済みの要点だけをプロンプトへ反映します。
