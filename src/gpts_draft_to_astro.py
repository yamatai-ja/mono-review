from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTICLE_QUEUE_CSV = ROOT / "data" / "article_queue.csv"
OUTPUT_DIR = ROOT / "output"
ASTRO_ARTICLES_DIR = OUTPUT_DIR / "astro_articles"
REPORT_PATH = OUTPUT_DIR / "gpts_draft_to_astro_report.md"

MOJIBAKE_MARKERS = ["�", "ã", "縺", "譁", "繧"]
DEFAULT_CATEGORY = "others"
DEFAULT_TAG = "others"
DEFAULT_AUTHOR = "Admin"


class ConversionError(Exception):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [{key: (value or "") for key, value in row.items()} for row in reader]


def find_queue_row(queue_id: str) -> dict[str, str] | None:
    for row in read_csv_rows(ARTICLE_QUEUE_CSV):
        if (row.get("queue_id") or "").strip() == queue_id:
            return row
    return None


def read_utf8(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ConversionError(f"input file is not valid UTF-8: {exc}") from exc


def strip_frontmatter(markdown: str) -> tuple[str, bool]:
    text = markdown.lstrip("\ufeff")
    if not text.startswith("---"):
        return markdown, False
    match = re.match(r"\A---\s*\r?\n.*?\r?\n---\s*(?:\r?\n|\Z)", text, flags=re.DOTALL)
    if not match:
        return markdown, False
    return text[match.end() :].lstrip(), True


def first_h1(markdown: str) -> str:
    match = re.search(r"(?m)^#\s+(.+?)\s*$", markdown)
    return match.group(1).strip() if match else ""


def remove_first_h1(markdown: str) -> tuple[str, bool]:
    lines = markdown.splitlines()
    output: list[str] = []
    removed = False
    for line in lines:
        if not removed and re.match(r"^#\s+\S", line.strip()):
            removed = True
            continue
        output.append(line)
    return "\n".join(output).lstrip() + ("\n" if output else ""), removed


def normalize_escaped_headings(markdown: str) -> tuple[str, int]:
    lines: list[str] = []
    in_code = False
    normalized_count = 0

    for line in markdown.splitlines():
        stripped = line.lstrip()
        leading = line[: len(line) - len(stripped)]

        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code = not in_code
            lines.append(line)
            continue

        if not in_code:
            match = re.match(r"^\\(#{1,6})(\s+.+)$", stripped)
            if match:
                line = f"{leading}{match.group(1)}{match.group(2)}"
                normalized_count += 1

        lines.append(line)

    trailing_newline = "\n" if markdown.endswith("\n") else ""
    return "\n".join(lines) + trailing_newline, normalized_count


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_markdown_marks(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[`*_>#|-]", " ", text)
    return normalize_space(text)


def extract_meta_description(markdown: str) -> tuple[str, str]:
    lines = markdown.splitlines()
    output: list[str] = []
    description = ""
    skip_next = False

    for index, line in enumerate(lines):
        stripped = line.strip()
        lower = stripped.lower()
        if skip_next:
            skip_next = False
            continue

        inline_match = re.match(
            r"^(?:meta\s*description|description|メタディスクリプション|概要|説明)\s*[:：]\s*(.+)$",
            stripped,
            flags=re.IGNORECASE,
        )
        if inline_match and not description:
            description = strip_markdown_marks(inline_match.group(1))
            continue

        if lower in {"meta description", "description"} or stripped in {"メタディスクリプション", "概要", "説明"}:
            next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
            if next_line and not description:
                description = strip_markdown_marks(next_line)
                skip_next = True
                continue

        output.append(line)

    return description, "\n".join(output).lstrip()


def natural_paragraphs(markdown: str) -> list[str]:
    paragraphs: list[str] = []
    current: list[str] = []
    in_code = False

    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if not stripped:
            if current:
                paragraphs.append(strip_markdown_marks(" ".join(current)))
                current = []
            continue
        if stripped.startswith("#") or stripped.startswith("|") or stripped.startswith(">"):
            continue
        if re.match(r"^[-*+]\s+", stripped) or re.match(r"^\d+[.)]\s+", stripped):
            continue
        current.append(stripped)

    if current:
        paragraphs.append(strip_markdown_marks(" ".join(current)))
    return [p for p in paragraphs if p]


def trim_description(text: str, minimum: int = 80, maximum: int = 160) -> str:
    text = normalize_space(text)
    if len(text) <= maximum:
        return text
    candidate = text[:maximum]
    breakpoints = [candidate.rfind("。"), candidate.rfind("、"), candidate.rfind(" ")]
    cut = max(point for point in breakpoints if point >= minimum) if any(point >= minimum for point in breakpoints) else maximum
    return candidate[:cut].rstrip("、。 ") + "。"


def build_description(markdown: str, title: str, keyword: str) -> tuple[str, str]:
    meta_description, body_without_meta = extract_meta_description(markdown)
    if meta_description:
        return trim_description(meta_description), body_without_meta

    for paragraph in natural_paragraphs(markdown):
        if len(paragraph) >= 30:
            return trim_description(paragraph), body_without_meta

    base = title or keyword
    if keyword and keyword not in base:
        return trim_description(f"{base}について、購入や利用前に確認したいポイントを整理します。"), body_without_meta
    return trim_description(f"{base}について、事前に確認したいポイントを整理します。"), body_without_meta


def sanitize_slug(value: str) -> str:
    slug = (value or "").strip().lower()
    slug = re.sub(r"[^a-z0-9_-]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def yaml_quote(value: Any) -> str:
    text = str(value or "").replace("\\", "\\\\").replace('"', '\\"')
    text = text.replace("\r", " ").replace("\n", " ")
    return f'"{normalize_space(text)}"'


def split_terms(value: str) -> list[str]:
    normalized = (value or "").replace(";", ",").replace("|", ",")
    return [part.strip() for part in normalized.split(",") if part.strip()]


def category_from_queue(row: dict[str, str]) -> str:
    article_type = (row.get("article_type") or "").strip()
    return article_type or DEFAULT_CATEGORY


def tags_from_queue(row: dict[str, str], keyword: str) -> list[str]:
    tags: list[str] = []
    for item in split_terms(keyword):
        tags.append(item)
    for product_id in split_terms(row.get("assigned_product_ids", "")):
        tags.append(product_id)
    if not tags:
        tags.append(DEFAULT_TAG)

    seen: set[str] = set()
    unique: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            unique.append(tag)
    return unique[:8]


def build_frontmatter(title: str, description: str, category: str, tags: list[str]) -> str:
    lines = [
        "---",
        f"title: {yaml_quote(title)}",
        f"description: {yaml_quote(description)}",
        f"date: {yaml_quote(date.today().isoformat())}",
        "categories:",
        f"  - {yaml_quote(category)}",
        "tags:",
    ]
    lines.extend(f"  - {yaml_quote(tag)}" for tag in tags)
    lines.extend([
        "draft: true",
        "authors:",
        f"  - {yaml_quote(DEFAULT_AUTHOR)}",
        "---",
        "",
    ])
    return "\n".join(lines)


def has_h1(markdown: str) -> bool:
    return bool(re.search(r"(?m)^#\s+\S", markdown))


def has_h2(markdown: str) -> bool:
    return bool(re.search(r"(?m)^##\s+\S", markdown))


def bare_urls(markdown: str) -> list[str]:
    urls = re.findall(r"https?://[^\s)>'\"]+", markdown)
    linked = set(re.findall(r"\[[^\]]*\]\((https?://[^\s)>'\"]+)\)", markdown))
    return [url for url in urls if url not in linked]


def mojibake_hits(text: str) -> list[str]:
    return [marker for marker in MOJIBAKE_MARKERS if marker in text]


def write_report(data: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    warnings = data.get("warnings") or []
    errors = data.get("errors") or []
    lines = [
        "# GPTs Draft To Astro Report",
        "",
        f"executed_at: {data.get('executed_at', now_iso())}",
        f"status: {data.get('status', 'unknown')}",
        f"queue_id: {data.get('queue_id', '')}",
        f"input_file: {data.get('input_file', '')}",
        f"output_file: {data.get('output_file', '')}",
        f"title: {data.get('title', '')}",
        f"description: {data.get('description', '')}",
        f"normalized_escaped_headings: {'yes' if data.get('normalized_escaped_headings') else 'no'}",
        f"normalized_escaped_headings_count: {data.get('normalized_escaped_headings_count', 0)}",
        "categories:",
    ]
    for category in data.get("categories") or []:
        lines.append(f"- {category}")
    lines.append("tags:")
    for tag in data.get("tags") or []:
        lines.append(f"- {tag}")
    lines.extend([
        f"draft: {str(data.get('draft', '')).lower()}",
        "",
        "## Warnings",
    ])
    lines.extend([f"- {warning}" for warning in warnings] if warnings else ["- none"])
    lines.extend(["", "## Errors"])
    lines.extend([f"- {error}" for error in errors] if errors else ["- none"])
    lines.extend([
        "",
        "## Next Human Checks",
        "- 出力Markdownのタイトル、説明文、カテゴリ、タグが意図通りか確認する",
        "- 本文に事実不明な価格、在庫、キャンペーン、ランキング、レビュー表現がないか確認する",
        "- 文字化け疑いが出た場合は入力Markdownの文字コードと本文を確認する",
        "- 問題なければ別手順でsrc/content/postsへコピーし、npm run check / npm run buildを実行する",
        "",
    ])
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def convert(queue_id: str, input_file: Path, slug_arg: str | None, normalize_headings: bool = True) -> int:
    report: dict[str, Any] = {
        "executed_at": now_iso(),
        "status": "error",
        "queue_id": queue_id,
        "input_file": str(input_file),
        "output_file": "",
        "title": "",
        "description": "",
        "categories": [],
        "tags": [],
        "draft": True,
        "warnings": [],
        "errors": [],
        "normalized_escaped_headings": False,
        "normalized_escaped_headings_count": 0,
    }

    try:
        queue_row = find_queue_row(queue_id)
        if queue_row is None:
            raise ConversionError("queue_id not found in data/article_queue.csv")

        source_path = input_file if input_file.is_absolute() else ROOT / input_file
        if not source_path.exists():
            raise ConversionError("input file does not exist")
        if not source_path.is_file():
            raise ConversionError("input file is not a file")

        raw_markdown = read_utf8(source_path)
        body, had_frontmatter = strip_frontmatter(raw_markdown)
        if had_frontmatter:
            report["warnings"].append("input frontmatter was removed before conversion")

        if normalize_headings:
            body, normalized_count = normalize_escaped_headings(body)
            report["normalized_escaped_headings"] = normalized_count > 0
            report["normalized_escaped_headings_count"] = normalized_count
            if normalized_count > 0:
                report["warnings"].append(f"escaped headings normalized: {normalized_count}")

        h1_title = first_h1(body)
        title = normalize_space(queue_row.get("article_title") or h1_title or queue_row.get("keyword") or queue_id)
        if not title:
            raise ConversionError("frontmatter title is empty")

        body, removed_h1 = remove_first_h1(body)
        if removed_h1:
            report["warnings"].append("first H1 was removed from body to avoid title duplication")

        keyword = normalize_space(queue_row.get("keyword") or "")
        description, body = build_description(body, title, keyword)
        if not description:
            description = f"{title}について、事前に確認したいポイントを整理します。"

        category = category_from_queue(queue_row)
        tags = tags_from_queue(queue_row, keyword)
        slug = sanitize_slug(slug_arg or queue_id)
        if not slug:
            raise ConversionError("slug is empty after sanitization")

        ASTRO_ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
        output_path = ASTRO_ARTICLES_DIR / f"{slug}.md"
        report["output_file"] = str(output_path.relative_to(ROOT))
        if output_path.exists():
            raise ConversionError("output file already exists; refusing to overwrite")

        if has_h1(body):
            report["warnings"].append("H1 remains in body")
        if not has_h2(body):
            report["warnings"].append("body has no H2 headings")
        found_bare_urls = bare_urls(body)
        if found_bare_urls:
            report["warnings"].append("bare URLs found: " + ", ".join(found_bare_urls[:5]))
        markers = mojibake_hits(title + "\n" + description + "\n" + body)
        if markers:
            report["warnings"].append("mojibake markers found: " + ", ".join(markers))
        if not description:
            report["warnings"].append("description is empty")
        if not category:
            report["warnings"].append("categories is empty")
        if not tags:
            report["warnings"].append("tags is empty")

        frontmatter = build_frontmatter(title, description, category, tags)
        output = frontmatter + body.rstrip() + "\n"
        output_path.write_text(output, encoding="utf-8")

        report.update(
            {
                "status": "converted",
                "title": title,
                "description": description,
                "categories": [category],
                "tags": tags,
                "draft": True,
            }
        )
        write_report(report)
        print(f"converted: {output_path.relative_to(ROOT).as_posix()}")
        return 0
    except ConversionError as exc:
        report["errors"].append(str(exc))
        write_report(report)
        print(f"error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a GPTs-generated Markdown draft into an Astro article candidate."
    )
    parser.add_argument("--queue-id", required=True, help="queue_id in data/article_queue.csv")
    parser.add_argument("--input-file", required=True, help="UTF-8 Markdown draft file, e.g. input/q000003_draft.md")
    parser.add_argument("--slug", help="Optional output slug. Defaults to queue_id.")
    parser.add_argument(
        "--no-normalize-escaped-headings",
        action="store_true",
        help="Do not convert line-start escaped Markdown headings like \\## into ##.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return convert(args.queue_id.strip(), Path(args.input_file), args.slug, not args.no_normalize_escaped_headings)


if __name__ == "__main__":
    raise SystemExit(main())
