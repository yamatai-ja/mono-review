# SERP Analysis Template

`problem_solution` 記事を作る前に、検索意図・読者不安・FAQ・購入前チェック項目を整理するためのテンプレートです。

NotebookLMや検索結果の要約は、事実としてそのまま扱いません。公開本文へ反映する前に、公式情報・販売ページ・メーカー情報・人間確認で裏取りしてください。

## Basic Info

- keyword:
- slug:
- article_type: problem_solution
- related_product:
- related_parent_article:
- analysis_date:
- checked_by:

## Search Intent Priority

検索意図を優先順位順に整理します。本文では上位の検索意図から先に答えます。

| Priority | Search Intent | Reader Situation | Must Answer |
| --- | --- | --- | --- |
| 1 |  |  |  |
| 2 |  |  |  |
| 3 |  |  |  |

## Reader Concerns

読者が購入前・比較前に不安に思っていることを整理します。

- 
- 
- 

確認ポイント:

- 不安は商品名ではなく、悩み・用途・失敗回避を主語にする
- 価格、在庫、保証、対応サービス、仕様は断定しない
- 公式確認が必要な不安には `要確認` を付ける

## Top SERP Notes

検索上位記事の特徴を短く整理します。長い本文コピーは残さず、要点だけにします。

| Rank | Page Type | Main Angle | Strong Points | Weak Points |
| --- | --- | --- | --- | --- |
| 1 |  |  |  |  |
| 2 |  |  |  |  |
| 3 |  |  |  |  |

## Common Headings

上位記事に共通して出てくる見出しです。

- 
- 
- 

## FAQ Candidates

読者が検索しそうな質問、上位記事で繰り返し出てくる質問を整理します。

| Question | Intent | Needs Official Check |
| --- | --- | --- |
|  |  | yes/no |
|  |  | yes/no |
|  |  | yes/no |

## Purchase Checklist

購入前に確認すべき項目です。

- 
- 
- 

商品・カテゴリによって特に確認する項目:

- 価格
- 在庫
- 保証
- 対応サービス
- 対応バンド
- 販売モデル
- 返品条件
- 付属品

## Comparison Axes

比較記事ではなくても、選び方記事の中で必要になる比較軸を整理します。

- 
- 
- 

## Competitor Gaps

競合記事が弱い、または曖昧にしている論点を整理します。

- 
- 
- 

注意:

- 競合の不足は推測で断定しない
- 自サイトで補える場合だけ本文候補にする
- 公式確認が必要な論点は本文で断定しない

## Differentiation Points

自サイトで差別化するポイントを整理します。

- 
- 
- 

差別化の方向性:

- 読者の不安を先に解消する
- 購入前チェックリストを明確にする
- 商品を押し売りせず、候補の一つとして紹介する
- 関連親記事へ自然に内部リンクする

## Official Check Required

本文に反映する前に人間確認が必要な情報です。

| Item | Source To Check | Status |
| --- | --- | --- |
|  |  | unchecked |
|  |  | unchecked |
|  |  | unchecked |

## Input For problem_prompt_builder

`problem_prompt_builder.py` やGPTs用プロンプトに渡す要点だけを整理します。

- target_keyword:
- search_intent:
- primary_reader_concern:
- must_include_points:
- faq_candidates:
- comparison_axes:
- avoid_claims:
- related_internal_links:
- related_product_hint:

## Human Review Checklist

- NotebookLM出力を事実扱いしていない
- 公式情報が必要な項目を分けた
- 未確認情報を断定しない方針にした
- 商品押し売りではなく悩み解決記事になっている
- FAQ候補が検索意図に沿っている
- 自サイトの差別化ポイントがある
