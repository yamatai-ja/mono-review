# GPTs to Astro 投稿ワークフロー

この手順書は、GPTsで作成した原稿をAstroの記事として下書き化し、確認後に公開状態へ切り替えるための運用チェックリストです。

## 1. 前提

- [ ] 作業リポジトリは OneDrive 側のみを使う。
  - `C:\Users\shiga\OneDrive\ドキュメント\antigravity\astro-management\mono-review-fresh`
- [ ] Codex側コピーリポジトリでは作業しない。
- [ ] push / deploy は別判断にする。
- [ ] `input/`、`output/`、`data/`、`.bak` は原則コミットしない。
- [ ] `git add .` は使わない。
- [ ] 1記事ずつ処理する。
- [ ] 既存記事をまとめて変更しない。

## 2. GPTs原稿の配置

GPTsで作成した原稿を `input/` に置く。

例:

```powershell
input/q000004_draft.md
```

確認:

- [ ] UTF-8で保存されている。
- [ ] 原稿本文に編集メモが残っていないか軽く確認する。
- [ ] queue_id と入力ファイル名が対応している。

## 3. Astro候補記事の生成

まずは `--copy` なしで候補記事だけ生成する。

例:

```powershell
python src\gpts_draft_to_astro.py --queue-id q000004 --input-file input\q000004_draft.md --slug example-slug
```

生成先:

```powershell
output/astro_articles/example-slug.md
```

確認:

- [ ] `output/astro_articles/example-slug.md` が生成された。
- [ ] `src/content/posts/example-slug.md` はまだ生成されていない。
- [ ] `output/gpts_draft_to_astro_report.md` の errors がない。
- [ ] `copy_requested: no` になっている。

## 4. 下書きコピー

候補記事を下書きとして `src/content/posts/` にコピーする場合だけ `--copy` を付ける。

例:

```powershell
python src\gpts_draft_to_astro.py --queue-id q000004 --input-file input\q000004_draft.md --slug example-slug --copy
```

コピー先:

```powershell
src/content/posts/example-slug.md
```

注意:

- [ ] `draft:true` のままコピーされる。
- [ ] 既存ファイルは上書きしない。
- [ ] pre-copy check が fail したらコピーされない。
- [ ] コピー失敗時は先に原稿や候補記事を確認する。
- [ ] 自動で `draft:false` にはしない。

## 5. 候補記事チェック

`src/content/posts/` にコピーされた下書きを candidate validator で確認する。

例:

```powershell
python src\astro_candidate_validator.py --file src\content\posts\example-slug.md
```

見ること:

- [ ] `draft:true` になっている。
- [ ] H2がある。
- [ ] H1が本文に残っていない。
- [ ] 編集メモが残っていない。
- [ ] `p_test_` が残っていない。
- [ ] `pubDate` がない。
- [ ] 単数 `category` がない。
- [ ] 裸URLがない。
- [ ] 文字化け疑いがない。
- [ ] `output/astro_candidate_validation_report.md` を確認した。

## 6. draft-preview確認

ローカル表示で下書きを確認する。

例:

```text
/draft-preview/example-slug/
```

見ること:

- [ ] タイトルが正しく表示される。
- [ ] PR表記が過不足なく表示される。
- [ ] 目次が出る。
- [ ] H2/H3の階層が自然。
- [ ] 表が崩れていない。
- [ ] FAQが読める。
- [ ] 編集メモが残っていない。
- [ ] テストタグが残っていない。
- [ ] スマホ表示で大きく崩れていない。

## 7. 公開切替

下書き確認が終わったら、対象記事1本だけ手動で変更する。

変更前:

```yaml
draft: true
```

変更後:

```yaml
draft: false
```

注意:

- [ ] 自動ではやらない。
- [ ] 1記事ずつ行う。
- [ ] 他記事を触らない。
- [ ] `pubDate` を追加しない。
- [ ] 単数 `category` に変えない。

## 8. 公開記事チェック

公開状態の記事を publish validator で確認する。

例:

```powershell
python src\astro_publish_validator.py --file src\content\posts\example-slug.md
```

見ること:

- [ ] `draft:false` になっている。
- [ ] 公開用 error がない。
- [ ] PR表記 warning はテンプレート側の `AffiliateDisclosure` でカバーされるなら許容する。
- [ ] 編集メモがない。
- [ ] `sourceQueueId` がない。
- [ ] `p_test_` がない。
- [ ] `output/astro_publish_validation_report.md` を確認した。

## 9. Astro検証

公開状態にしたらAstro側の検証を行う。

例:

```powershell
npm run check
npm run build
```

確認:

- [ ] `npm run check` が成功する。
- [ ] `npm run build` が成功する。
- [ ] `dist/blog/example-slug/index.html` が生成される。
- [ ] 通常URL `/blog/example-slug/` で表示できる。
- [ ] `draft-preview` は公開後に404になる場合があると理解している。
- [ ] タイトル、PR表記、目次、表、FAQ、スマホ表示を確認した。

## 10. コミット方針

記事公開コミットは記事ファイルだけにする。

例:

```powershell
git add src/content/posts/example-slug.md
git commit -m "Add example article"
```

ツール変更コミットは記事とは分ける。

対象例:

- `src/gpts_draft_to_astro.py`
- `src/astro_candidate_validator.py`
- `src/astro_publish_validator.py`

確認:

- [ ] `git diff --cached --name-only` で対象ファイルだけになっている。
- [ ] `git add .` を使っていない。
- [ ] `input/`、`output/`、`data/` を add していない。

## 11. コミットしないもの

原則として以下はコミットしない。

- `input/`
- `output/`
- `data/`
- `.bak`
- `__pycache__`
- 一時テスト記事
- レポートmd

確認:

- [ ] `git status --short` で不要ファイルが staged されていない。
- [ ] `git diff --cached --stat` を確認した。
- [ ] `git diff --cached --name-only` を確認した。

## 12. よくある事故

- 別リポジトリで作業する。
- `git add .` する。
- `draft:true` のまま公開URLが出ないと勘違いする。
- `draft:false` 後に candidate validator が fail して混乱する。
- `output/astro_articles/` の記事をそのまま公開して編集メモが残る。
- テストslugを本番に使う。
- `input/`、`output/`、`data/`、`.bak` をまとめて add する。
- 公開記事とツール変更を同じコミットに混ぜる。

## 13. 今後の改善候補

- 2本目の記事で再現テストする。
- `.gitignore` を整理する。
- publish切替専用スクリプトを作る。
- 内部リンク候補生成を追加する。
- 商品リンク候補生成を追加する。
