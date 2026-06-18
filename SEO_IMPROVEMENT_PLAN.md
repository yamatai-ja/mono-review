# SEO Improvement Plan

`problem_solution` 記事のSEO品質を上げるため、本文生成前に競合分析と検索意図整理を挟む運用計画です。

今回は実装ではなく、運用標準化のための設計です。

## Current Flow

```text
problem_keyword_candidates.csv
↓
problem_prompt_builder.py
↓
GPTs本文生成
↓
article_quality_checker.py
↓
astro_markdown_builder.py
↓
process_article.py
↓
Astro下書き
```

現在の課題:

- 検索意図の優先順位がプロンプト前に十分整理されていない
- 読者の不安やFAQ候補が記事ごとにばらつく
- 競合記事が弱い論点を事前に拾いにくい
- NotebookLM分析をどこに挟むかが未標準化

## Recommended Flow

```text
keyword
↓
SERP確認
↓
上位記事・公式情報・FAQ・比較記事を収集
↓
NotebookLM分析
↓
SERP分析レポート作成
↓
problem_prompt_builder.py
↓
GPTs本文生成
↓
article_quality_checker.py
↓
astro_markdown_builder.py / process_article.py
↓
Astro下書き
```

競合分析の挿入位置は `problem_prompt_builder.py` の前です。

理由:

- 本文生成前に検索意図と読者不安を固定できる
- FAQと購入前チェック項目をプロンプトへ渡せる
- 商品押し売りを避け、悩み解決記事として構成しやすい
- GPTs本文生成後の大幅修正を減らせる

## SERP Analysis Outputs

記事ごとに以下の形式で保存します。

```text
output/serp_analysis/{slug}.md
```

保存する内容:

- 対象キーワード
- 検索意図の優先順位
- 読者の不安
- 上位記事の共通見出し
- FAQ候補
- 比較軸
- 購入前チェック項目
- 公式確認が必要な情報
- 競合が弱い論点
- 自サイトの差別化ポイント
- `problem_prompt_builder.py` へ渡す要点

## What To Pass Into problem_prompt_builder

将来的に `problem_prompt_builder.py` へ渡すとよい情報です。

- target_keyword
- search_intent
- reader_concerns
- common_headings
- faq_candidates
- comparison_axes
- purchase_checklist
- competitor_gaps
- differentiation_points
- avoid_claims
- official_check_required
- related_internal_links
- related_product_hint

初期運用では自動連携せず、人間が `SERP_ANALYSIS.md` の要点を確認してからプロンプトへ反映します。

## NotebookLM Usage

NotebookLMは以下の用途に使います。

- 上位記事の共通見出しを抽出する
- FAQ候補を整理する
- 読者の不安を洗い出す
- 比較軸を整理する
- 購入前チェック項目を抽出する
- 競合が弱い論点を探す

NotebookLMに投入する情報:

- 上位記事
- FAQ
- 公式情報
- 比較記事
- 関連記事
- 販売ページ確認メモ

重要:

- NotebookLM出力は事実ではない
- 公式確認が必要な項目は本文で断定しない
- NotebookLMの文章を本文へそのまま貼らない
- 人間が確認した要点だけをプロンプト素材にする

## Human Review Required

以下は自動化せず、人間確認を必須にします。

- SERP上位記事の妥当性
- 公式情報の確認
- 価格、在庫、保証、対応サービス、対応バンド、販売モデル
- NotebookLM出力の事実性
- 競合が弱い論点の妥当性
- GPTsへ渡す素材の取捨選択

## Can Be Automated Later

### `serp_report_builder.py`

目的:

- `keyword` と `slug` からSERP分析テンプレートを生成する
- `output/serp_analysis/{slug}.md` を作る
- NotebookLM投入用の項目を整理する

初期機能案:

- `--keyword`
- `--slug`
- `--article-type problem_solution`
- `--related-product`
- `--parent-url`

### `serp_analyzer.py`

目的:

- 人間が保存したNotebookLM出力を読み込む
- `problem_prompt_builder.py` に渡しやすい形式へ整形する

初期機能案:

- `--serp-report`
- `--notebooklm-note`
- `--output`

出力:

- search intent summary
- FAQ candidates
- purchase checklist
- avoid claims
- differentiation points

## Operating Rule

`problem_solution` 記事では、本文生成前に以下が埋まっていることを目標にします。

- 検索意図の優先順位
- 読者の不安
- FAQ候補
- 購入前チェック項目
- 競合が弱い論点
- 自サイトの差別化ポイント

これらが不足している場合は、GPTs本文生成へ進めず、追加調査を行います。

## Success Criteria

- GPTs本文生成後の大幅修正が減る
- FAQが検索意図に近づく
- 購入前チェック項目が明確になる
- 関連商品が押し売りにならない
- 自サイトの内部リンクが自然に入る
- 公開前チェックで内部語・強CTA・未確認断定が出にくくなる
