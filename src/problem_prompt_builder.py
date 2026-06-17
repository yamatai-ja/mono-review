from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROBLEM_CANDIDATES = ROOT / "output" / "problem_keyword_candidates.csv"
ARTICLE_QUEUE = ROOT / "data" / "article_queue.csv"
PRODUCTS_CSV = ROOT / "data" / "products.csv"
POSTS_DIR = ROOT / "src" / "content" / "posts"
PROMPT_DIR = ROOT / "output" / "problem_body_prompts"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = [{key: (value or "") for key, value in row.items()} for row in reader]
        return list(reader.fieldnames or []), rows


def slugify(value: str) -> str:
    text = (value or "").lower()
    replacements = {
        "felica": "felica",
        "android": "android",
        "スマホ": "smartphone",
        "選び方": "selection",
        "対応": "",
    }
    for before, after in replacements.items():
        text = text.replace(before, after)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "problem-solution"


def prompt_filename(keyword: str) -> str:
    if keyword == "FeliCa対応 Androidスマホ 選び方":
        return "felica-android-smartphone-selection_prompt.md"
    return f"{slugify(keyword)}_prompt.md"


def find_candidate(keyword: str) -> dict[str, str]:
    _, rows = read_csv(PROBLEM_CANDIDATES)
    for row in rows:
        if row.get("problem_keyword") == keyword:
            return row
    raise SystemExit(f"Keyword not found in problem_keyword_candidates.csv: {keyword}")


def find_article_by_product_hint(product_hint: str) -> dict[str, str]:
    _, rows = read_csv(ARTICLE_QUEUE)
    needle = (product_hint or "").lower()
    for row in rows:
        haystack = " ".join([
            row.get("keyword", ""),
            row.get("article_title", ""),
            row.get("notes", ""),
        ]).lower()
        if needle and needle in haystack:
            return row
    return {}


def find_product(product_hint: str) -> dict[str, str]:
    _, rows = read_csv(PRODUCTS_CSV)
    needle = (product_hint or "").lower()
    for row in rows:
        haystack = " ".join([
            row.get("product_id", ""),
            row.get("name", ""),
            row.get("title", ""),
            row.get("tags", ""),
        ]).lower()
        if needle and needle in haystack:
            return row
    return {}


def parent_slug(article: dict[str, str], product_hint: str) -> str:
    if "motorola edge 60" in (product_hint or "").lower():
        return "motorola-edge-60"
    title = article.get("article_title") or product_hint
    return slugify(title)


def build_prompt(
    candidate: dict[str, str],
    article: dict[str, str],
    product: dict[str, str],
    slug: str,
) -> tuple[str, str, str]:
    keyword = candidate.get("problem_keyword", "")
    product_hint = candidate.get("recommended_product_hint", "")
    title = "FeliCa対応Androidスマホの選び方と購入前チェック"
    prompt_file = str(PROMPT_DIR / prompt_filename(keyword))
    parent_link = f"/blog/{slug}/" if slug else ""
    source_title = candidate.get("source_title", "")
    search_intent = candidate.get("search_intent", "")

    product_notes = product.get("notes", "")
    product_status = product.get("status", "")
    amazon_url_status = "確認済み" if product.get("amazon_url") else "未確認"
    post_exists = "yes" if slug and (POSTS_DIR / f"{slug}.md").exists() else "no"

    prompt = f"""# GPTs本文生成プロンプト: {title}

このMarkdownは記事本文ではありません。GPTsに渡すための本文生成プロンプトです。
以下の条件を守り、悩み解決記事として本文Markdownを作成してください。

## 対象キーワード

- problem_keyword: {keyword}
- article_type: problem_solution
- candidate_title: {title}
- search_intent: {search_intent}
- source_title: {source_title}

## 記事の位置づけ

- 商品名記事ではなく、悩み解決記事として書く
- 商品を押し売りせず、選択肢の一つとして扱う
- 商品名を主キーワードにしない
- 読者の悩み: FeliCa対応のAndroidスマホをどう選べばよいか知りたい

## 関連商品候補

- product_name: {product_hint}
- product_status: {product_status}
- amazon_url_status: {amazon_url_status}
- notes: {product_notes}

## 内部リンク候補

- 親記事: {article.get('article_title', '')}
- 親記事slug: {slug}
- 親記事URL候補: {parent_link}
- 親記事ファイル存在: {post_exists}

本文中では、自然な文脈で親記事へ1回だけ内部リンクする想定にしてください。
ただし、ProductCard、frontmatter、queue_id、draft、rel= などの内部語は本文に出さないでください。

## 想定読者

- FeliCa対応Androidスマホを探している人
- Suicaやおサイフケータイを使いたい人
- 対応バンドや販売モデルの違いで失敗したくない人
- キャッシュレス決済と普段使いのバランスを重視する人

## 検索意図

FeliCa対応Androidスマホを選ぶときに、FeliCa/Suica/おサイフケータイ、対応バンド、販売モデル、保証、画面サイズ、電池持ちなど、購入前に確認すべきポイントを知りたい。

## 推奨構成

- 結論
- FeliCa対応Androidスマホを選ぶ前に確認すること
- FeliCa/Suica/おサイフケータイの注意点
- 対応バンド・販売モデル・保証の確認
- 画面サイズ・電池持ち・microSDなどの比較ポイント
- motorola edge 60が候補になる人
- 他モデルも比較した方がよい人
- 購入前チェックリスト
- FAQ
- まとめ

## 安全ルール

- FeliCa/Suica対応を未確認で断定しない
- 医療・金融・法律系の話に広げない
- 「最安値」「絶対おすすめ」「今すぐ購入」は使わない
- 価格・在庫・保証・対応バンドは購入前確認を促す
- 商品は解決策候補の一つとして紹介し、押し売りしない
- 実機レビュー、使ってみた、本音レビューとして書かない
- 未確認スペックを補完しない

## 出力形式

記事本文Markdownのみを出力してください。
メタディスクリプション案、H2/H3構成、FAQを含めてください。
内部メモやこのプロンプトの管理語は本文に出さないでください。
"""
    return title, prompt_file, prompt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build one GPTs prompt for a problem_solution keyword candidate.")
    parser.add_argument("--keyword", required=True, help="Target problem_keyword from output/problem_keyword_candidates.csv.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="Preview without writing. Default.")
    group.add_argument("--apply", action="store_true", help="Write prompt file to output/problem_body_prompts/.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    candidate = find_candidate(args.keyword)
    product_hint = candidate.get("recommended_product_hint", "")
    article = find_article_by_product_hint(product_hint)
    product = find_product(product_hint)
    slug = parent_slug(article, product_hint)
    title, prompt_file, prompt = build_prompt(candidate, article, product, slug)

    if args.apply:
        PROMPT_DIR.mkdir(parents=True, exist_ok=True)
        Path(prompt_file).write_text(prompt, encoding="utf-8")

    print(f"mode={'apply' if args.apply else 'dry-run'}")
    print(f"keyword={args.keyword}")
    print(f"candidate_title={title}")
    print(f"prompt_file={prompt_file}")
    print(f"parent_slug={slug}")
    print(f"parent_link=/blog/{slug}/")
    print(f"related_product={product_hint}")
    print(f"product_found={'yes' if product else 'no'}")
    print(f"parent_article_found={'yes' if article else 'no'}")
    print(f"written={'yes' if args.apply else 'no'}")


if __name__ == "__main__":
    main()
