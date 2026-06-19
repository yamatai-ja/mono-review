# Article Pipeline

このドキュメントは、`problem_solution` 記事を GPTs 本文ドラフトから Astro 下書きへ変換し、ビルド確認まで進めるための運用手順です。

## 対象スクリプト

### `src/article_quality_checker.py`

記事本文ドラフトを `article_type` 別の品質ルールで検査します。

- 入力: `output/drafts/{slug}_draft.md`
- ルール: `src/article_profiles/{article_type}.yaml`
- 出力:
  - `output/article_quality_report.csv`
  - `output/article_quality_report.md`
- 主な出力値:
  - `quality_score`
  - `decision`
  - `failed_checks`
  - `warnings`

`problem_solution` では、`decision=ready_for_astro_candidate` になった場合のみ Astro 化へ進めます。

### `src/astro_markdown_builder.py`

品質チェック済みの本文ドラフトから、Astro 投稿用 Markdown を生成します。

- 入力:
  - `output/article_quality_report.csv`
  - `output/drafts/{slug}_draft.md`
- 出力:
  - `src/content/posts/{slug}.md`
- 生成方針:
  - `draft: true`
  - H1 は追加しない
  - `title` は frontmatter で管理
  - 本文は `draft_file` をそのまま利用
  - 既存ファイルがある場合は通常エラー
  - `--overwrite` 指定時のみ上書き

### `src/process_article.py`

単一記事の処理をまとめて実行します。

通常の生成フロー:

1. 公開前リスク判定
2. `article_quality_checker.py`
3. `astro_markdown_builder.py --apply`
4. `npm run check`
5. `npm run build`

既存記事を変更せず確認する場合は `--check-only` を使います。このモードは品質判定、公開前リスク判定、Markdown監査をメモリ上で実行し、記事、CSV、`output/`、Astroファイルを書き換えません。subprocess、`npm run check`、`npm run build` も実行しません。

主なチェック専用出力:

- `quality_score` / `quality_decision`
- `publication_risk` / `detected_terms`
- `required_human_checks` / `research_notes_required`
- `markdown_audit_decision` / `draft`

最終状態:

- `ready_for_publish_review`: 品質チェック、Astro生成、check、build がすべて成功
- `needs_edit`: 品質チェックで `ready_for_astro_candidate` にならなかった
- `build_failed`: Astro生成、check、build のいずれかで失敗

`npm` 実行時は `ASTRO_TELEMETRY_DISABLED=1` を付与します。Windows では `npm` が見つからない場合に `npm.cmd` へフォールバックします。

### `src/article_profiles/problem_solution.yaml`

`problem_solution` 記事の品質基準です。

Hard Fail:

- H1 がある
- FAQ がない
- 内部語がある
- 強すぎる CTA がある
- 体験レビュー表現がある

Warning:

- H2 が少ない
- メタディスクリプション案がない
- まとめがない
- 内部リンクがない
- URL が本文に直接貼られている

スコア:

- 初期値: 100
- Hard Fail ごとに -25
- Warning ごとに -5
- 0〜100 に丸める

判定:

- Hard Fail あり: `needs_edit`
- Hard Fail なし、かつ score >= 95: `ready_for_astro_candidate`
- それ以外: `needs_edit`


## problem_solution 推奨フロー

1. GPTsで本文ドラフトを生成する
2. `process_article.py` で `draft: true` のAstro下書きを生成する
3. 生成後の記事を `process_article.py --check-only` で確認する
4. `publication_risk` に応じた人手確認だけを行う
5. `npm run check` を実行する
6. `npm run build` を実行する
7. 目視確認と必要な公式確認が完了してから、`draft: false` にするか人間が判断する

`quality_score` は記事構造・表現の品質です。`publication_risk` は公開前に必要な確認の強度です。品質スコアが高くても、公開前リスクの確認は省略できません。

### publication_risk の意味

| risk | 対象 | 必要な確認 |
| --- | --- | --- |
| `low` | 通常の選び方、使い方、原因対策記事 | quality score、Markdown監査、check/build、目視確認 |
| `medium` | 商品候補や比較要素を含む記事 | lowの確認 + 商品公式ページ確認 |
| `high` | 通信、決済、保証、契約、価格、在庫、キャンペーン、口コミ、評判、医療、金融、法律などを含む記事 | mediumの確認 + 公式情報確認メモまたは`research_notes`必須 |

### high判定の例: FeliCa記事

`src/content/posts/felica-android-smartphone-selection.md` は、FeliCa、おサイフケータイ、Suica、通信、決済、保証、契約が関係するため `high` になります。

公開前に行うこと:

- 商品・サービスの公式ページを確認する
- 一次情報との照合結果を公式確認メモまたは`research_notes`に残す
- 未確認の価格、在庫、保証、対応バンド、キャンペーンを断定しない
- 公式確認が終わるまで `draft: true` を維持する

## 実行例

### 1. 品質チェックのみ

```powershell
python src\article_quality_checker.py `
  --article-type problem_solution `
  --draft-file output\drafts\felica-android-smartphone-selection_draft.md `
  --slug felica-android-smartphone-selection
```

成功目安:

```text
quality_score=100
decision=ready_for_astro_candidate
failed_checks=none
warnings=none
```

### 2. Astro下書き生成のみ

```powershell
python src\astro_markdown_builder.py `
  --article-type problem_solution `
  --slug felica-android-smartphone-selection `
  --title "FeliCa対応Androidスマホの選び方と購入前チェック" `
  --draft-file output\drafts\felica-android-smartphone-selection_draft.md `
  --category "スマホ" `
  --tags "FeliCa,Androidスマホ,スマホ,おサイフケータイ" `
  --apply
```

既存ファイルを明示的に置き換える場合のみ `--overwrite` を追加します。

```powershell
python src\astro_markdown_builder.py `
  --article-type problem_solution `
  --slug felica-android-smartphone-selection `
  --title "FeliCa対応Androidスマホの選び方と購入前チェック" `
  --draft-file output\drafts\felica-android-smartphone-selection_draft.md `
  --category "スマホ" `
  --tags "FeliCa,Androidスマホ,スマホ,おサイフケータイ" `
  --apply `
  --overwrite
```

### 3. 一括処理

```powershell
python src\process_article.py `
  --article-type problem_solution `
  --slug felica-android-smartphone-selection `
  --title "FeliCa対応Androidスマホの選び方と購入前チェック" `
  --draft-file output\drafts\felica-android-smartphone-selection_draft.md `
  --category "スマホ" `
  --tags "FeliCa,Androidスマホ,スマホ,おサイフケータイ"
```

既存の Astro Markdown を上書きする場合のみ:

```powershell
python src\process_article.py `
  --article-type problem_solution `
  --slug felica-android-smartphone-selection `
  --title "FeliCa対応Androidスマホの選び方と購入前チェック" `
  --draft-file output\drafts\felica-android-smartphone-selection_draft.md `
  --category "スマホ" `
  --tags "FeliCa,Androidスマホ,スマホ,おサイフケータイ" `
  --overwrite
```

成功目安:

```text
quality_score=100
decision=ready_for_astro_candidate
generated_file=...\src\content\posts\felica-android-smartphone-selection.md
npm_check_result=success
npm_build_result=success
final_status=ready_for_publish_review
```

### 4. 既存Astro記事のチェック専用確認

```powershell
python src\process_article.py `
  --check-only src\content\posts\felica-android-smartphone-selection.md
```

成功例:

```text
quality_score=100
quality_decision=ready_for_astro_candidate
publication_risk=high
research_notes_required=yes
markdown_audit_decision=draft_ok
draft=true
```

`--check-only` はファイルを変更せず、`npm run check` と `npm run build` も実行しません。必要に応じて後から個別に実行します。

### 5. frontmatterなし本文のチェック専用確認

```powershell
python src\process_article.py `
  --check-only body.md `
  --article-type problem_solution
```

frontmatterがないため `draft=unknown` になりますが、品質と公開前リスクは確認できます。タイトルも判定対象に含める場合は `--title` を追加します。

## エラー時の対処

### `final_status=needs_edit`

品質チェックで止まっています。

確認するもの:

- `quality_score`
- `decision`
- `failed_checks`
- `warnings`
- `output/article_quality_report.md`

対応:

- Hard Fail がある場合は、本文ドラフトを GPTs 側で修正する
- Codex では本文の大幅リライトをしない
- 修正後、`article_quality_checker.py` または `process_article.py` を再実行する

### `output file already exists`

`src/content/posts/{slug}.md` が既にあります。

対応:

- 意図しない上書きを避けるため、まず既存ファイルを確認する
- 上書きしてよい場合のみ `--overwrite` を付ける

### `final_status=build_failed`

Astro生成、`npm run check`、`npm run build` のいずれかで止まっています。

確認するもの:

- `astro_builder_output`
- `npm_check_output`
- `npm_build_output`

対応:

- frontmatter の構文エラーがないか確認
- `category` / `tags` の形式を確認
- 本文中に Astro/Markdown を壊す記法がないか確認
- `npm run check` が telemetry 権限で失敗する場合は、`ASTRO_TELEMETRY_DISABLED=1` が有効か確認

### H1 関連エラー

`problem_solution` 記事では H1 を本文に入れません。

対応:

- 本文冒頭の `# タイトル` を削除
- タイトルは frontmatter の `title` にだけ置く

### 内部語検出

本文に次のような管理語があると Hard Fail になります。

- `ProductCard`
- `frontmatter`
- `queue_id`
- `draft`
- `rel=`
- `CTA挿入候補`
- `HTMLで挿入`
- `URL確認後`

対応:

- 読者向けの自然な表現へ置き換える
- 管理メモは本文に残さない

## 公開手順

`process_article.py` は公開処理までは行いません。

1. `final_status=ready_for_publish_review` を確認する
2. `process_article.py --check-only` で品質、リスク、Markdown監査、draft状態を確認する
3. `publication_risk` に応じた人手確認を完了する
4. `src/content/posts/{slug}.md` を目視確認する
5. `draft: true` のままローカル確認する
6. 公開してよい場合のみ、明示指示を受けた別工程で `draft: false` へ変更する
7. `npm run check`
8. `npm run build`
9. ローカル表示確認
10. commit
11. push

公開前に確認すること:

- `quality_score` と `publication_risk` を別々に確認したか
- `high` の場合、公式確認メモまたは`research_notes`があるか
- `high` の場合、未確認の価格、在庫、保証、対応バンド、キャンペーンを断定していないか
- `high` を品質スコアだけで自動公開しようとしていないか
- `draft: true` で下書きのままか
- H1 が本文にないか
- noindex 下書き表示で確認できるか
- 内部語が本文にないか
- 強すぎる CTA がないか
- 既存公開記事を意図せず変更していないか

## Commit推奨手順

### 1. 状態確認

```powershell
git status --short
git diff --stat
```

### 2. ドキュメント・ツール系

品質チェックやビルダーなど、共通ツールは記事本文とは別コミットにします。

例:

```powershell
git add ARTICLE_RULES.md src\article_profiles\problem_solution.yaml src\article_quality_checker.py src\astro_markdown_builder.py src\process_article.py
git commit -m "feat: add problem solution article pipeline tools"
```

### 3. 記事ファイル

Astro記事ファイルは、記事ごとに別コミットにします。

例:

```powershell
git add src\content\posts\felica-android-smartphone-selection.md
git commit -m "content: add FeliCa Android smartphone selection draft"
```

### 4. コミットしないもの

原則コミットしません。

- `output/`
- `input/`
- `dist/`
- `.bak`
- `__pycache__/`
- 生成レポート
- 一時プロンプト

## 現在の責務分離

- GPTs: 本文作成
- `article_quality_checker.py`: 本文品質チェック
- `astro_markdown_builder.py`: Astro Markdown 生成
- `publication_risk_checker.py`: 公開前確認強度と必要な人手確認の判定
- `process_article.py`: 品質チェックからbuildまでの一括実行、および書き込みなしの`--check-only`
- 人間: risk別の公式確認、内容確認、公開判断、commit、push、deploy判断

`process_article.py` は公開、commit、deploy を実行しません。
