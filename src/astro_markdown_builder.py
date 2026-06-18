from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUALITY_REPORT_CSV = ROOT / "output" / "article_quality_report.csv"
POSTS_DIR = ROOT / "src" / "content" / "posts"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [{key: (value or "") for key, value in row.items()} for row in csv.DictReader(f)]


def yaml_quote(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def yaml_array(values: list[str]) -> str:
    return "[" + ", ".join(yaml_quote(value) for value in values if value.strip()) + "]"


def parse_tags(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def find_quality_row(slug: str, article_type: str, draft_file: str) -> dict[str, str]:
    rows = read_csv(QUALITY_REPORT_CSV)
    for row in rows:
        if (
            row.get("slug", "").strip() == slug
            and row.get("article_type", "").strip() == article_type
            and normalize_path(row.get("draft_file", "")) == normalize_path(draft_file)
        ):
            return row
    return {}


def normalize_path(value: str) -> str:
    return (value or "").replace("\\", "/").strip()


def build_frontmatter(
    *,
    title: str,
    slug: str,
    article_type: str,
    category: str,
    tags: list[str],
) -> str:
    return "\n".join(
        [
            "---",
            f"title: {yaml_quote(title)}",
            f"slug: {yaml_quote(slug)}",
            f"draft: true",
            f"article_type: {yaml_quote(article_type)}",
            f"categories: {yaml_array([category])}",
            f"tags: {yaml_array(tags)}",
            "---",
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Astro draft Markdown from a checked article body.")
    parser.add_argument("--article-type", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--draft-file", required=True)
    parser.add_argument("--category", required=True)
    parser.add_argument("--tags", required=True, help="Comma-separated tag list.")
    parser.add_argument("--apply", action="store_true", help="Write src/content/posts/{slug}.md.")
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting an existing output file.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    slug = args.slug.strip()
    article_type = args.article_type.strip()
    draft_file = args.draft_file.strip()
    draft_path = ROOT / draft_file
    output_path = POSTS_DIR / f"{slug}.md"

    if not draft_path.exists():
        raise SystemExit(f"draft_file not found: {draft_file}")

    quality_row = find_quality_row(slug, article_type, draft_file)
    if not quality_row:
        raise SystemExit("matching article_quality_report row not found. Run article_quality_checker.py first.")

    decision = quality_row.get("decision", "").strip()
    if decision != "ready_for_astro_candidate":
        raise SystemExit(f"quality decision is not ready_for_astro_candidate: {decision or 'empty'}")

    if output_path.exists() and not args.overwrite:
        raise SystemExit(f"output file already exists. Use --overwrite to replace it: {output_path}")

    body = draft_path.read_text(encoding="utf-8").rstrip()
    frontmatter = build_frontmatter(
        title=args.title,
        slug=slug,
        article_type=article_type,
        category=args.category,
        tags=parse_tags(args.tags),
    )
    output = frontmatter + body + "\n"

    print(f"quality_score={quality_row.get('quality_score', '')}")
    print(f"decision={decision}")
    print(f"output_file={output_path}")
    print(f"would_write={'yes' if args.apply else 'no'}")
    print(f"overwrite={'yes' if args.overwrite else 'no'}")

    if args.apply:
        POSTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
        print("written=yes")
    else:
        print("written=no")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
