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

実行順:

1. `article_quality_checker.py`
2. `astro_markdown_builder.py --apply`
3. `npm run check`
4. `npm run build`

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

1. `final_status=ready_for_publish_review` を確認
2. `src/content/posts/{slug}.md` を目視確認
3. `draft: true` のままローカル確認
4. 必要に応じて公開前チェック用スクリプトを実行
5. 公開してよい場合のみ、別工程で `draft: false` へ変更
6. `npm run check`
7. `npm run build`
8. ローカル表示確認
9. commit
10. push

公開前に確認すること:

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
- `process_article.py`: 品質チェックから build までの一括実行
- 人間: 内容確認、公開判断、commit、push、deploy判断

`process_article.py` は公開、commit、deploy を実行しません。
