from __future__ import annotations

import argparse
import hashlib
import re
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_REPORT = ROOT / "output" / "product_card_single_migration_report.md"
PRODUCT_CARD = ROOT / "src" / "components" / "ProductCard.astro"

MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\((https?://[^)\s]+)\)")
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
VAGUE_LINK_TEXT_HINTS = [
    "amazon",
    "rakuten",
    "yahoo",
    "purchase",
    "buy",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dry-run friendly single-post ProductCard migrator.",
    )
    parser.add_argument("--file", required=True, help="Target Markdown post file.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the migration. Without this flag, runs as dry-run.",
    )
    parser.add_argument(
        "--product-name",
        help="Explicit product name to use in the products frontmatter candidate.",
    )
    return parser.parse_args()


def resolve_target(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def split_frontmatter(text: str) -> tuple[dict[str, Any], str, str]:
    if not text.startswith("---"):
        return {}, "", text
    lines = text.splitlines(keepends=True)
    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
    if end_index is None:
        return {}, "", text
    frontmatter_text = "".join(lines[1:end_index])
    body = "".join(lines[end_index + 1 :])
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


def has_products_frontmatter(frontmatter_text: str) -> bool:
    return re.search(r"(?m)^products\s*:", frontmatter_text) is not None


def is_affiliate_url(url: str) -> bool:
    lowered = url.lower()
    return any(hint in lowered for hint in AFFILIATE_HINTS)


def looks_like_vague_link_text(link_text: str) -> bool:
    lowered = link_text.lower()
    if any(hint in lowered for hint in VAGUE_LINK_TEXT_HINTS):
        return True
    return len(link_text.strip()) <= 16


def detect_platform(link_text: str, url: str) -> str:
    lowered = f"{link_text} {url}".lower()
    if "amazon" in lowered or "amzn.to" in lowered:
        return "Amazon"
    if "rakuten" in lowered:
        return "Rakuten"
    if "yahoo" in lowered:
        return "Yahoo"
    return "unknown"


def extract_links(body: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    starts = line_start_offsets(body)
    for match in MARKDOWN_LINK_RE.finditer(body):
        url = match.group(2).strip()
        if not is_affiliate_url(url):
            continue
        links.append(
            {
                "link_text": match.group(1).strip(),
                "url": url,
                "markdown": match.group(0),
                "line": str(offset_to_line(starts, match.start())),
                "platform": detect_platform(match.group(1).strip(), url),
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


def infer_product_name(title: str, slug: str) -> tuple[str, str]:
    if " | " in title:
        return title.split(" | ", 1)[0].strip(), "Product name inferred from title. Manual confirmation required."
    if " - " in title:
        return title.split(" - ", 1)[0].strip(), "Product name inferred from title. Manual confirmation required."
    if title and title != slug:
        return title[:80].strip(), "Product name inferred from title. Manual confirmation required."
    return slug.replace("-", " "), "Product name inferred from slug. Manual confirmation required."


def stable_product_id(slug: str, platform: str) -> str:
    platform_id = {
        "Amazon": "amazon",
        "Rakuten": "rakuten",
        "Yahoo": "yahoo",
    }.get(platform, "affiliate")
    return f"{slug}-{platform_id}-001"


def yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_products_yaml(
    slug: str,
    title: str,
    link: dict[str, str] | None,
    *,
    product_name: str | None = None,
) -> str:
    if not link:
        return "(none)"
    if product_name:
        resolved_product_name = product_name
        note = "Product name explicitly provided by user."
    else:
        resolved_product_name, note = infer_product_name(title, slug)
    platform = link["platform"]
    lines = [
        "products:",
        f"  - id: {yaml_quote(stable_product_id(slug, platform))}",
        f"    title: {yaml_quote(resolved_product_name)}",
        f"    platform: {yaml_quote(platform)}",
        f"    productGroup: {yaml_quote(slug + '-product-001')}",
    ]
    if platform == "Amazon":
        lines.append(f"    amazon_url: {yaml_quote(link['url'])}")
    elif platform == "Rakuten":
        lines.append(f"    rakuten_url: {yaml_quote(link['url'])}")
    elif platform == "Yahoo":
        lines.append(f"    yahoo_url: {yaml_quote(link['url'])}")
    else:
        lines.append(f"    url: {yaml_quote(link['url'])}")
    lines.extend(
        [
            "    notes:",
            f"      - {yaml_quote(note)}",
            f"      - {yaml_quote(link['link_text'] + ': link text is not a product name. Manual confirmation required.')}",
        ]
    )
    return "\n".join(lines)


def product_card_props() -> list[str]:
    if not PRODUCT_CARD.exists():
        return []
    text = PRODUCT_CARD.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"interface Props\s*\{(?P<body>.*?)\}", text, re.DOTALL)
    if not match:
        return []
    return [
        line.split(":", 1)[0].strip().rstrip("?")
        for line in match.group("body").splitlines()
        if ":" in line
    ]


def build_new_text(original: str, products_yaml: str, link: dict[str, str]) -> str:
    lines = original.splitlines(keepends=True)
    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
    if end_index is None:
        raise RuntimeError("frontmatter closing marker not found")
    new_lines = lines[:end_index] + [products_yaml + "\n"] + lines[end_index:]
    return "".join(new_lines).replace(link["markdown"], "", 1)


def evaluate(path: Path, *, product_name: str | None = None) -> dict[str, Any]:
    if not path.exists():
        return {"status": "error", "reasons": [f"file not found: {path}"], "path": path}
    if product_name is not None and not product_name.strip():
        return {"status": "manual_review", "reasons": ["--product-name is empty"], "path": path}
    text = path.read_text(encoding="utf-8")
    frontmatter, frontmatter_text, body = split_frontmatter(text)
    slug = str(frontmatter.get("slug") or path.stem)
    title = str(frontmatter.get("title") or slug)
    links = extract_links(body)
    props = product_card_props()
    has_products = has_products_frontmatter(frontmatter_text)

    reasons: list[str] = []
    status = "yes"
    if not props:
        status = "manual_review"
        reasons.append("ProductCard props could not be detected")
    if len(links) == 0:
        status = "skipped"
        reasons.append("Markdown affiliate link not found")
    elif len(links) >= 2:
        status = "manual_review"
        reasons.append("Multiple Markdown affiliate links found")
    if has_products:
        status = "manual_review"
        reasons.append("products frontmatter already exists")
    explicit_product_name = product_name.strip() if product_name else None
    if len(links) == 1 and looks_like_vague_link_text(links[0]["link_text"]) and not explicit_product_name:
        status = "manual_review"
        reasons.append("Link text is not a product name; product name was inferred and needs manual confirmation")

    link = links[0] if links else None
    products_yaml = build_products_yaml(slug, title, link, product_name=explicit_product_name)
    backup_path = path.with_suffix(path.suffix + ".bak")

    return {
        "status": status,
        "reasons": reasons,
        "path": path,
        "slug": slug,
        "title": title,
        "links": links,
        "props": props,
        "has_products": has_products,
        "products_yaml": products_yaml,
        "product_name": explicit_product_name or "",
        "backup_path": backup_path,
        "text": text,
        "link": link,
    }


def write_report(result: dict[str, Any], *, apply: bool, changed: bool) -> None:
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# ProductCard Single Migration Report",
        "",
        f"- mode: {'apply' if apply else 'dry-run'}",
        f"- target_file: `{result.get('path')}`",
        f"- status: {result.get('status')}",
        f"- changed: {str(changed).lower()}",
        f"- backup_file_on_apply: `{result.get('backup_path')}`",
        f"- reasons: {', '.join(result.get('reasons') or ['none'])}",
        f"- explicit_product_name: {result.get('product_name') or 'none'}",
        f"- existing_ProductCard_props: {', '.join(result.get('props') or []) or 'not found'}",
        "",
        "## Detected Markdown Affiliate Links",
        "",
        "| line | link_text | platform | url |",
        "| --- | --- | --- | --- |",
    ]
    for link in result.get("links", []):
        lines.append(f"| {link['line']} | {escape_table(link['link_text'])} | {link['platform']} | {escape_table(link['url'])} |")

    lines.extend(
        [
            "",
            "## Products Frontmatter Candidate",
            "",
            "```yaml",
            result.get("products_yaml") or "(none)",
            "```",
            "",
            "## Body Link Removal Candidates",
            "",
        ]
    )
    for link in result.get("links", []):
        lines.append(f"- line {link['line']}: remove `{link['markdown']}`")

    lines.extend(
        [
            "",
            "## ProductCard Display Candidate",
            "",
            "```astro",
            "<ProductCard",
            "  title={product.title}",
            "  image={product.image}",
            "  amazonUrl={product.amazonUrl}",
            "  rakutenUrl={product.rakutenUrl}",
            "  yahooUrl={product.yahooUrl}",
            "  price={product.price}",
            "/>",
            "```",
        ]
    )
    OUTPUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def apply_migration(result: dict[str, Any]) -> bool:
    if result["status"] != "yes" or not result.get("link"):
        return False
    path: Path = result["path"]
    backup_path: Path = result["backup_path"]
    shutil.copy2(path, backup_path)
    new_text = build_new_text(result["text"], result["products_yaml"], result["link"])
    path.write_text(new_text, encoding="utf-8")
    return True


def escape_table(value: str) -> str:
    return value.replace("|", "\\|")


def main() -> int:
    args = parse_args()
    target = resolve_target(args.file)
    before_sha = sha256(target) if target.exists() else ""
    result = evaluate(target, product_name=args.product_name)
    changed = False
    if args.apply:
        changed = apply_migration(result)
    after_sha = sha256(target) if target.exists() else ""
    write_report(result, apply=args.apply, changed=changed)

    print(f"mode={'apply' if args.apply else 'dry-run'}")
    print(f"target={target}")
    print(f"status={result.get('status')}")
    print(f"links={len(result.get('links', []))}")
    print(f"backup_on_apply={result.get('backup_path')}")
    print(f"changed={str(changed).lower()}")
    print(f"sha256_before={before_sha}")
    print(f"sha256_after={after_sha}")
    print(f"sha256_unchanged={str(before_sha == after_sha).lower()}")
    if result.get("reasons"):
        print("reasons=" + "; ".join(result["reasons"]))
    return 0 if result.get("status") != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
