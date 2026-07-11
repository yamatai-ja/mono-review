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
        "androidスマホ": "android-smartphone",
        "android": "android",
        "スマートフォン": "smartphone",
        "スマホ": "smartphone",
        "外付けssd": "external-ssd",
        "usb-cハブ": "usb-c-hub",
        "usbハブ": "usb-hub",
        "選び方": "selection",
        "接続が切れる": "disconnects",
        "対策": "solutions",
        "対応": "",
    }
    for before, after in replacements.items():
        text = text.replace(before, after)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "problem-solution"


def prompt_filename(keyword: str) -> str:
    return f"{slugify(keyword)}_prompt.md"


def infer_category(keyword: str) -> str:
    lowered = keyword.lower()
    if "felica" in lowered or "スマホ" in keyword or "android" in lowered:
        return "smartphone"
    if "ssd" in lowered:
        return "storage"
    if "usbハブ" in lowered or "usb-cハブ" in lowered:
        return "pc_accessory"
    return "general"


def find_candidate(keyword: str, *, allow_synthetic: bool = False) -> dict[str, str]:
    _, rows = read_csv(PROBLEM_CANDIDATES)
    for row in rows:
        if row.get("problem_keyword") == keyword:
            return {**row, "_candidate_source": "csv"}
    if allow_synthetic:
        return {
            "problem_keyword": keyword,
            "article_type": "problem_solution",
            "category": infer_category(keyword),
            "search_intent": keyword,
            "recommended_product_hint": "",
            "_candidate_source": "synthetic",
        }
    raise SystemExit(f"Keyword not found in problem_keyword_candidates.csv: {keyword}")


def find_article_by_product_hint(product_hint: str) -> dict[str, str]:
    _, rows = read_csv(ARTICLE_QUEUE)
    needle = (product_hint or "").lower()
    for row in rows:
        haystack = " ".join(
            [row.get("keyword", ""), row.get("article_title", ""), row.get("notes", "")]
        ).lower()
        if needle and needle in haystack:
            return row
    return {}


def find_product(product_hint: str) -> dict[str, str]:
    _, rows = read_csv(PRODUCTS_CSV)
    needle = (product_hint or "").lower()
    for row in rows:
        haystack = " ".join(
            [
                row.get("product_id", ""),
                row.get("name", ""),
                row.get("title", ""),
                row.get("tags", ""),
            ]
        ).lower()
        if needle and needle in haystack:
            return row
    return {}


def parent_slug(article: dict[str, str], product_hint: str) -> str:
    if "motorola edge 60" in (product_hint or "").lower():
        return "motorola-edge-60"
    title = article.get("article_title") or product_hint
    return slugify(title) if title else ""


def topic_context(keyword: str) -> dict[str, object]:
    lowered = keyword.lower()
    if "felica" in lowered:
        return {
            "kind": "felica",
            "title": "FeliCa対応Androidスマホの選び方と購入前チェック",
            "reader_problem": "FeliCa対応Androidスマホをどう選べばよいか分からない",
            "focus": "FeliCa、おサイフケータイ、Suica、国内販売モデル、対応バンド、保証を購入前に確認する",
            "outline": [
                "結論と購入前チェックリスト",
                "FeliCa・おサイフケータイ・Suicaの違い",
                "国内モデルと販売ページで確認する項目",
                "候補機種を比較するときの注意点",
                "FAQ",
            ],
            "safety": [
                "FeliCaやSuicaへの対応を未確認のまま断定しない",
                "価格、在庫、保証、対応バンド、販売モデルは公式情報の確認を促す",
                "候補機種は押し売りせず、確認できた国内モデルだけを比較対象にする",
            ],
        }
    if "ssd" in lowered and ("接続" in keyword or "切れる" in keyword):
        return {
            "kind": "external_ssd_disconnect",
            "title": "外付けSSDの接続が切れる原因と対策",
            "reader_problem": "外付けSSDが途中で切断される、認識が不安定、データ転送中に止まる",
            "focus": "ケーブル、USBポート、電力不足、ハブ、スリープ設定、SSDケース、発熱、ファイルシステム、PC側設定を順に切り分ける",
            "outline": [
                "最初にデータ保護と再現条件を確認する",
                "ケーブル・USBポート・ハブ・電力を切り分ける",
                "スリープ設定・PC側設定を確認する",
                "SSDケース・発熱・ファイルシステムを確認する",
                "改善しない場合の判断とFAQ",
            ],
            "safety": [
                "初期化やファイルシステム変更の前にバックアップを促す",
                "商品紹介は必要最小限にし、特定商品を押し売りしない",
                "価格、保証、個別製品仕様を未確認のまま断定しない",
            ],
        }
    if "usbハブ" in lowered or "usb-cハブ" in lowered:
        return {
            "kind": "usb_hub_selection",
            "title": "USBハブの選び方と確認ポイント",
            "reader_problem": "必要な端子や給電方式、転送速度、機器との相性をどう確認すればよいか分からない",
            "focus": "端子数、給電方式、転送速度、映像出力、有線LAN、対応OSと接続機器の仕様を用途別に確認する",
            "outline": [
                "用途と必要な端子を整理する",
                "給電方式と消費電力を確認する",
                "転送速度・映像出力・有線LANを確認する",
                "PCや接続機器との互換性を確認する",
                "購入前チェックリストとFAQ",
            ],
            "safety": [
                "商品候補は必要最小限にし、用途に合う確認項目を優先する",
                "転送速度や映像出力は接続機器を含む条件で変わると説明する",
                "価格、保証、在庫、個別製品仕様を未確認のまま断定しない",
            ],
        }
    return {
        "kind": "generic",
        "title": f"{keyword}を解決するための確認ポイント",
        "reader_problem": f"{keyword}について原因や選び方が分からない",
        "focus": "原因または選定条件を整理し、読者が安全に次の行動を選べるようにする",
        "outline": [
            "結論と最初に確認すること",
            "主な原因または選定条件",
            "順番に試す確認方法",
            "改善しない場合の判断",
            "FAQ",
        ],
        "safety": [
            "未確認の仕様、価格、保証、在庫を断定しない",
            "特定商品を押し売りせず、問題解決を優先する",
        ],
    }


def product_supplement(product_hint: str, product: dict[str, str]) -> str:
    if not product_hint or not product:
        return "- 特定商品の紹介は必須ではありません。問題解決と確認手順を優先してください。"
    return (
        f"- 関連商品候補: {product_hint}（products.csvで確認済み）\n"
        "- 商品は解決候補の一つとして必要最小限に紹介し、公式ページで最新情報を確認するよう促してください。"
    )


def build_prompt(
    candidate: dict[str, str],
    article: dict[str, str],
    product: dict[str, str],
    slug: str,
) -> tuple[str, str, str]:
    keyword = candidate.get("problem_keyword", "")
    product_hint = candidate.get("recommended_product_hint", "")
    context = topic_context(keyword)
    title = str(context["title"])
    prompt_file = str(PROMPT_DIR / prompt_filename(keyword))
    parent_link = f"/blog/{slug}/" if slug else "なし"
    search_intent = candidate.get("search_intent", "") or keyword
    post_exists = "yes" if slug and (POSTS_DIR / f"{slug}.md").exists() else "no"
    outline = "\n".join(f"- {item}" for item in context["outline"])
    safety = "\n".join(f"- {item}" for item in context["safety"])

    prompt = f"""# GPTs本文生成プロンプト: {title}

以下の条件を守り、悩み解決型の記事本文をMarkdownで作成してください。

## 対象キーワード

- problem_keyword: {keyword}
- article_type: problem_solution
- candidate_title: {title}
- search_intent: {search_intent}

## 記事の主旨

- 読者の悩み: {context['reader_problem']}
- 扱う内容: {context['focus']}
- 商品名を主キーワードにせず、読者の問題解決と判断支援を主役にしてください。
- 特定商品の押し売りはしないでください。

## 商品情報の扱い

{product_supplement(product_hint, product)}

## 関連記事

- 関連記事タイトル: {article.get('article_title', '') or 'なし'}
- 関連記事slug: {slug or 'なし'}
- 関連記事URL候補: {parent_link}
- 関連記事ファイル存在: {post_exists}

関連記事がある場合のみ、本文中で自然に1回リンクする想定にしてください。

## 推奨構成

{outline}

## 安全ルール

{safety}
- 実体験や検証をしていない内容を、体験談として書かないでください。
- 不明な情報は補完せず、読者に公式情報の確認を促してください。

## 本文に出してはいけない内部語

- ProductCard
- frontmatter
- queue_id
- draft
- source_title
- product_status
- amazon_url_status
- notes
- Not in products.csv
- RSS source candidate

## 出力形式

- 記事本文Markdownのみを出力してください。
- H1は使わず、見出しはH2/H3のみを使ってください。
- タイトルはAstro側で管理するため、本文冒頭に記事タイトルを再掲しないでください。
- FAQとまとめを含めてください。
- SEO descriptionはfrontmatter側で管理するため、本文には出力しないでください。
- このプロンプトの内部メモや処理語を本文に出さないでください。
"""
    return title, prompt_file, prompt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build one GPTs prompt for a problem_solution keyword candidate."
    )
    parser.add_argument(
        "--keyword",
        required=True,
        help="Target problem_keyword. Dry-run also accepts an unregistered keyword.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="Preview without writing. Default.")
    group.add_argument(
        "--apply", action="store_true", help="Write a registered candidate prompt to output/."
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    candidate = find_candidate(args.keyword, allow_synthetic=not args.apply)
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
    print(f"candidate_source={candidate.get('_candidate_source', 'csv')}")
    print(f"template_kind={topic_context(args.keyword)['kind']}")
    print(f"article_type={candidate.get('article_type') or 'problem_solution'}")
    print(f"candidate_title={title}")
    print(f"prompt_file={prompt_file}")
    print(f"parent_slug={slug or 'none'}")
    print(f"parent_link={f'/blog/{slug}/' if slug else 'none'}")
    print(f"related_product={product_hint if product else 'none'}")
    print(f"product_found={'yes' if product else 'no'}")
    print(f"parent_article_found={'yes' if article else 'no'}")
    print(f"written={'yes' if args.apply else 'no'}")


if __name__ == "__main__":
    main()
