from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = ROOT / "src" / "content" / "posts"
COMPONENTS_DIR = ROOT / "src" / "components"
LAYOUTS_DIR = ROOT / "src" / "layouts"
OUTPUT_DIR = ROOT / "output"
CSV_REPORT = OUTPUT_DIR / "product_card_migration_report.csv"
MD_REPORT = OUTPUT_DIR / "product_card_migration_report.md"

CSV_COLUMNS = [
    "file",
    "slug",
    "draft",
    "link_text",
    "url",
    "link_type",
    "has_products_frontmatter",
    "has_existing_product_card",
    "candidate_status",
    "notes",
]

AFFILIATE_HINTS = [
    "af.moshimo.com",
    "hb.afl.rakuten.co.jp",
    "a8.net",
    "amazon",
    "amzn.to",
    "rakuten",
    "yahoo",
    "valuecommerce",
    "felmat",
    "link-a",
    "accesstrade",
    "tag=",
]

VAGUE_LINK_TEXTS = {
    "",
    "こちら",
    "ここ",
    "詳細",
    "詳しくはこちら",
    "購入はこちら",
    "公式サイト",
    "リンク",
    "amazon",
    "楽天",
    "楽天市場",
    "yahoo",
    "ヤフー",
}

MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\((https?://[^)\s]+)\)")
NAKED_URL_RE = re.compile(r"(?<!\]\()https?://[^\s<>()\"']+")
HTML_LINK_RE = re.compile(
    r"<a\b[^>]*\bhref=[\"'](https?://[^\"']+)[\"'][^>]*>(.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)


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
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.startswith((" ", "\t")):
            continue
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
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


def as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return default


def has_products_frontmatter(frontmatter_text: str) -> bool:
    return re.search(r"(?m)^products\s*:", frontmatter_text) is not None


def has_existing_product_card() -> bool:
    search_dirs = [COMPONENTS_DIR, LAYOUTS_DIR]
    for base_dir in search_dirs:
        if not base_dir.exists():
            continue
        for path in base_dir.rglob("*.*"):
            if path.suffix.lower() not in {".astro", ".ts", ".tsx", ".js", ".jsx"}:
                continue
            try:
                if "ProductCard" in path.read_text(encoding="utf-8", errors="ignore"):
                    return True
            except OSError:
                continue
    return False


def is_affiliate_url(url: str) -> bool:
    lowered = url.lower()
    return any(hint in lowered for hint in AFFILIATE_HINTS)


def is_internal_url(url: str) -> bool:
    lowered = url.lower()
    return lowered.startswith("/") or "localhost" in lowered or "127.0.0.1" in lowered or "monoslog.com" in lowered


def normalize_link_text(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def has_product_like_text(text: str) -> bool:
    normalized = normalize_link_text(text)
    lowered = normalized.lower()
    if lowered in VAGUE_LINK_TEXTS:
        return False
    if len(normalized) < 3:
        return False
    if any(char.isdigit() for char in normalized):
        return True
    if any(keyword in normalized for keyword in ["探す", "購入", "Amazon", "楽天", "Yahoo"]):
        return True
    return len(normalized) >= 6


def classify_markdown_link(link_text: str, url: str) -> tuple[str, str, str]:
    if is_affiliate_url(url):
        if has_product_like_text(link_text):
            return "affiliate_markdown_link", "candidate", "affiliate link with usable link text"
        return "affiliate_markdown_link", "needs_manual_review", "affiliate link text is vague"
    if is_internal_url(url):
        return "internal_markdown_link", "skip", "internal link"
    return "external_markdown_link", "skip", "normal external link"


def row_for_link(
    *,
    path: Path,
    slug: str,
    draft: bool,
    link_text: str,
    url: str,
    link_type: str,
    has_products: bool,
    product_card_exists: bool,
    candidate_status: str,
    notes: str,
) -> dict[str, str]:
    return {
        "file": path.as_posix(),
        "slug": slug,
        "draft": str(draft).lower(),
        "link_text": normalize_link_text(link_text),
        "url": url,
        "link_type": link_type,
        "has_products_frontmatter": str(has_products).lower(),
        "has_existing_product_card": str(product_card_exists).lower(),
        "candidate_status": candidate_status,
        "notes": notes,
    }


def scan_post(path: Path, product_card_exists: bool) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    frontmatter, frontmatter_text, body = split_frontmatter(text)
    slug = str(frontmatter.get("slug") or path.stem)
    draft = as_bool(frontmatter.get("draft"), default=False)
    has_products = has_products_frontmatter(frontmatter_text)
    rows: list[dict[str, str]] = []

    markdown_spans: list[tuple[int, int]] = []
    for match in MARKDOWN_LINK_RE.finditer(body):
        markdown_spans.append(match.span())
        link_text = match.group(1)
        url = match.group(2)
        link_type, status, notes = classify_markdown_link(link_text, url)
        rows.append(
            row_for_link(
                path=path,
                slug=slug,
                draft=draft,
                link_text=link_text,
                url=url,
                link_type=link_type,
                has_products=has_products,
                product_card_exists=product_card_exists,
                candidate_status=status,
                notes=notes,
            )
        )

    body_without_markdown = remove_spans(body, markdown_spans)

    for match in HTML_LINK_RE.finditer(body_without_markdown):
        url = match.group(1)
        link_text = match.group(2)
        link_type = "affiliate_html_link" if is_affiliate_url(url) else "html_link"
        rows.append(
            row_for_link(
                path=path,
                slug=slug,
                draft=draft,
                link_text=link_text,
                url=url,
                link_type=link_type,
                has_products=has_products,
                product_card_exists=product_card_exists,
                candidate_status="needs_manual_review",
                notes="html link requires manual review",
            )
        )

    body_without_links = HTML_LINK_RE.sub("", body_without_markdown)
    for match in NAKED_URL_RE.finditer(body_without_links):
        rows.append(
            row_for_link(
                path=path,
                slug=slug,
                draft=draft,
                link_text="(naked_url)",
                url=match.group(0),
                link_type="naked_url",
                has_products=has_products,
                product_card_exists=product_card_exists,
                candidate_status="needs_manual_review",
                notes="naked URL requires manual review",
            )
        )

    return rows


def remove_spans(text: str, spans: list[tuple[int, int]]) -> str:
    if not spans:
        return text
    chunks: list[str] = []
    last = 0
    for start, end in spans:
        chunks.append(text[last:start])
        last = end
    chunks.append(text[last:])
    return "".join(chunks)


def write_csv(rows: list[dict[str, str]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_REPORT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, str]], product_card_exists: bool) -> None:
    affiliate_count = sum(1 for row in rows if row["link_type"].startswith("affiliate"))
    candidate_count = sum(1 for row in rows if row["candidate_status"] == "candidate")
    manual_count = sum(1 for row in rows if row["candidate_status"] == "needs_manual_review")
    skip_count = sum(1 for row in rows if row["candidate_status"] == "skip")

    lines = [
        "# ProductCard Migration Report",
        "",
        f"- scanned links: {len(rows)}",
        f"- affiliate-like links: {affiliate_count}",
        f"- candidate: {candidate_count}",
        f"- needs_manual_review: {manual_count}",
        f"- skip: {skip_count}",
        f"- existing ProductCard found: {str(product_card_exists).lower()}",
        "",
        "## Results",
        "",
        "| file | link_text | link_type | status | has_products | notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for row in rows:
        lines.append(
            "| {file} | {text} | {link_type} | {status} | {has_products} | {notes} |".format(
                file=Path(row["file"]).name,
                text=escape_table(row["link_text"]),
                link_type=row["link_type"],
                status=row["candidate_status"],
                has_products=row["has_products_frontmatter"],
                notes=escape_table(row["notes"]),
            )
        )

    MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def escape_table(value: str) -> str:
    return value.replace("|", "\\|")


def main() -> int:
    product_card_exists = has_existing_product_card()
    rows: list[dict[str, str]] = []
    for path in sorted(POSTS_DIR.glob("*.md")):
        rows.extend(scan_post(path, product_card_exists))

    write_csv(rows)
    write_markdown(rows, product_card_exists)

    affiliate_count = sum(1 for row in rows if row["link_type"].startswith("affiliate"))
    candidate_count = sum(1 for row in rows if row["candidate_status"] == "candidate")
    manual_count = sum(1 for row in rows if row["candidate_status"] == "needs_manual_review")
    skip_count = sum(1 for row in rows if row["candidate_status"] == "skip")

    print(f"checked_at={datetime.now().isoformat(timespec='seconds')}")
    print(f"links={len(rows)}")
    print(f"affiliate_links={affiliate_count}")
    print(f"candidate={candidate_count}")
    print(f"needs_manual_review={manual_count}")
    print(f"skip={skip_count}")
    print(f"existing_product_card={str(product_card_exists).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
