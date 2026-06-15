from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_REPORT = ROOT / "output" / "product_card_migration_report.csv"
POSTS_DIR = ROOT / "src" / "content" / "posts"
COMPONENT_PATH = ROOT / "src" / "components" / "ProductCard.astro"
OUTPUT_REPORT = ROOT / "output" / "product_card_preview_report.md"

MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\((https?://[^)\s]+)\)")
VAGUE_LINK_TEXTS = {
    "楽天市場で探す",
    "Amazonで探す",
    "Yahooで探す",
    "購入はこちら",
    "詳しくはこちら",
    "公式サイト",
}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def choose_target(rows: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
    candidates = [row for row in rows if row.get("candidate_status") == "candidate"]
    counts = Counter(row["file"] for row in candidates)
    if not counts:
        raise RuntimeError("No candidate links found in migration report.")
    target_file = sorted(counts.items(), key=lambda item: (item[1], item[0]))[0][0]
    return target_file, [row for row in candidates if row["file"] == target_file]


def split_frontmatter(text: str) -> tuple[dict[str, Any], str, str]:
    if not text.startswith("---"):
        return {}, "", text

    lines = text.splitlines()
    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
    if end_index is None:
        return {}, "", text

    frontmatter_text = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :])
    return parse_frontmatter(frontmatter_text), frontmatter_text, body


def parse_frontmatter(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith((" ", "\t")) or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = clean_scalar(value.strip())
    return data


def clean_scalar(value: str) -> str | bool:
    cleaned = value.strip()
    if (
        (cleaned.startswith('"') and cleaned.endswith('"'))
        or (cleaned.startswith("'") and cleaned.endswith("'"))
    ):
        cleaned = cleaned[1:-1]
    if cleaned.lower() == "true":
        return True
    if cleaned.lower() == "false":
        return False
    return cleaned


def infer_product_name(title: str, slug: str) -> tuple[str, str]:
    if " の" in title:
        return title.split(" の", 1)[0].strip(), "記事タイトルから仮の商品名を推定。要手動確認。"
    if "|" in title:
        return title.split("|", 1)[0].strip(), "記事タイトルから仮の商品名を推定。要手動確認。"
    return slug.replace("-", " "), "slugから仮の商品名を推定。要手動確認。"


def detect_platform(text: str, url: str) -> str:
    lowered = f"{text} {url}".lower()
    if "amazon" in lowered or "amzn.to" in lowered:
        return "Amazon"
    if "rakuten" in lowered or "楽天" in text:
        return "楽天市場"
    if "yahoo" in lowered or "ヤフー" in text:
        return "Yahoo"
    return "unknown"


def extract_markdown_links(body: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    line_starts = line_start_offsets(body)
    for match in MARKDOWN_LINK_RE.finditer(body):
        line_no = offset_to_line(line_starts, match.start())
        links.append(
            {
                "link_text": match.group(1).strip(),
                "url": match.group(2).strip(),
                "line": str(line_no),
                "markdown": match.group(0),
            }
        )
    return links


def line_start_offsets(text: str) -> list[int]:
    starts = [0]
    for match in re.finditer(r"\n", text):
        starts.append(match.end())
    return starts


def offset_to_line(starts: list[int], offset: int) -> int:
    line = 1
    for index, start in enumerate(starts, start=1):
        if start > offset:
            break
        line = index
    return line


def product_card_props() -> list[str]:
    if not COMPONENT_PATH.exists():
        return []
    text = COMPONENT_PATH.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"interface Props\s*\{(?P<body>.*?)\}", text, re.DOTALL)
    if not match:
        return []
    return [
        line.split(":", 1)[0].strip().rstrip("?")
        for line in match.group("body").splitlines()
        if ":" in line
    ]


def group_links(links: list[dict[str, str]], product_name: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for index, link in enumerate(links, start=1):
        platform = detect_platform(link["link_text"], link["url"])
        group_key = "product-001"
        product = grouped.setdefault(
            group_key,
            {
                "id": group_key,
                "title": product_name,
                "name": product_name,
                "platforms": [],
                "notes": [],
            },
        )
        product["platforms"].append(platform)
        if platform == "Amazon":
            product["amazon_url"] = link["url"]
        elif platform == "楽天市場":
            product["rakuten_url"] = link["url"]
        elif platform == "Yahoo":
            product["yahoo_url"] = link["url"]
        else:
            product[f"url_{index}"] = link["url"]
        if link["link_text"] in VAGUE_LINK_TEXTS:
            product["notes"].append(f"{link['link_text']}: リンクテキストが商品名ではないため要手動確認")
    return list(grouped.values())


def yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_products_yaml(products: list[dict[str, Any]]) -> str:
    lines = ["products:"]
    for product in products:
        lines.append(f"  - title: {yaml_quote(product['title'])}")
        if product.get("amazon_url"):
            lines.append(f"    amazon_url: {yaml_quote(product['amazon_url'])}")
        if product.get("rakuten_url"):
            lines.append(f"    rakuten_url: {yaml_quote(product['rakuten_url'])}")
        if product.get("yahoo_url"):
            lines.append(f"    yahoo_url: {yaml_quote(product['yahoo_url'])}")
        if product.get("notes"):
            lines.append("    notes:")
            for note in product["notes"]:
                lines.append(f"      - {yaml_quote(note)}")
        lines.append("    product_group: \"product-001\"")
    return "\n".join(lines)


def build_report() -> tuple[str, int, int, str, str]:
    rows = read_csv_rows(MIGRATION_REPORT)
    target_file, target_rows = choose_target(rows)
    path = Path(target_file)
    if not path.is_absolute():
        path = ROOT / target_file

    text = path.read_text(encoding="utf-8")
    frontmatter, frontmatter_text, body = split_frontmatter(text)
    slug = str(frontmatter.get("slug") or path.stem)
    title = str(frontmatter.get("title") or slug)
    product_name, infer_note = infer_product_name(title, slug)
    links = extract_markdown_links(body)
    target_urls = {row["url"] for row in target_rows}
    affiliate_links = [link for link in links if link["url"] in target_urls]
    products = group_links(affiliate_links, product_name)
    props = product_card_props()
    has_products = re.search(r"(?m)^products\s*:", frontmatter_text) is not None

    auto_status = "manual_review"
    if len(affiliate_links) == 1 and product_name and props:
        auto_status = "manual_review"

    lines = [
        "# ProductCard Preview Report",
        "",
        f"- target_file: `{path.as_posix()}`",
        f"- target_slug: `{slug}`",
        f"- title: {title}",
        f"- extracted_affiliate_links: {len(affiliate_links)}",
        f"- conversion_candidates: {len(products)}",
        f"- has_products_frontmatter: {str(has_products).lower()}",
        f"- existing_ProductCard_props: {', '.join(props) if props else 'not found'}",
        f"- auto_convert: {auto_status}",
        f"- notes: {infer_note}",
        "",
        "## Extracted Links",
        "",
        "| line | link_text | platform | url |",
        "| --- | --- | --- | --- |",
    ]
    for link in affiliate_links:
        lines.append(
            f"| {link['line']} | {escape_table(link['link_text'])} | {detect_platform(link['link_text'], link['url'])} | {escape_table(link['url'])} |"
        )

    lines.extend(
        [
            "",
            "## Products Frontmatter Candidate",
            "",
            "```yaml",
            build_products_yaml(products),
            "```",
            "",
            "## ProductCard Display Candidate",
            "",
            "既存実装では `products` frontmatter を `ProductCard` に渡せます。",
            "",
            "```astro",
            '<ProductCard',
            '  title={product.title || product.name || product.product_name}',
            '  image={product.image?.url || product.product_image?.url}',
            '  amazonUrl={product.amazon_url || product.amazon_link}',
            '  rakutenUrl={product.rakuten_url || product.rakuten_link}',
            '  yahooUrl={product.yahoo_url || product.yahoo_link}',
            '  price={product.price}',
            '/>',
            "```",
            "",
            "## Body Replacement Candidates",
            "",
        ]
    )

    for link in affiliate_links:
        lines.append(f"- line {link['line']}: remove or replace `{link['markdown']}`")

    lines.extend(
        [
            "",
            "## Manual Checks",
            "",
            "- リンクテキストが商品名ではないため、商品名推定は要手動確認。",
            "- 楽天/Amazonのペアがそろっていない場合は、同一商品としてまとめる前に確認。",
            "- 今回は実ファイルを変更していません。",
        ]
    )

    OUTPUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path.name, len(affiliate_links), len(products), auto_status, product_name


def escape_table(value: str) -> str:
    return value.replace("|", "\\|")


def main() -> int:
    target, link_count, candidate_count, auto_status, product_name = build_report()
    print(f"target={target}")
    print(f"product_name={product_name}")
    print(f"extracted_links={link_count}")
    print(f"conversion_candidates={candidate_count}")
    print(f"auto_convert={auto_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
