import argparse
import csv
import re
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTICLES_CSV = ROOT / "data" / "articles.csv"
PREFLIGHT_CSV = ROOT / "output" / "astro_preflight_report.csv"
OUTPUT_DIR = ROOT / "output" / "astro_articles"
REPORT_CSV = ROOT / "output" / "astro_article_report.csv"
REPORT_MD = ROOT / "output" / "astro_article_report.md"
LEGACY_REPORT_MD = ROOT / "output" / "astro_article_build_report.md"

DEFAULT_QUEUE_ID = "q000003"

REPORT_FIELDS = [
    "queue_id",
    "slug",
    "output_file",
    "status",
    "h1_count",
    "warnings",
]


def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def yaml_quote(value):
    text = str(value or "").replace("\\", "\\\\").replace('"', '\\"')
    text = re.sub(r"\s+", " ", text).strip()
    return f'"{text}"'


def articles_by_queue(rows):
    return {row.get("queue_id", "").strip(): row for row in rows}


def extract_description(markdown, article_title):
    lines = markdown.splitlines()
    start = None
    for i, line in enumerate(lines[:12]):
        normalized = line.strip()
        if (
            normalized.startswith("メタディスクリプション案")
            or normalized.lower().startswith("meta description")
            or normalized.startswith("繝｡繧ｿ繝・ぅ繧ｹ繧ｯ繝ｪ繝励す繝ｧ繝ｳ")
        ):
            start = i
            break

    if start is None:
        return f"{article_title}について、購入前に確認したいポイントを整理します。", markdown

    first_line = lines[start].strip()
    description = re.sub(r"^.*?[：:]\s*", "", first_line).strip()
    end = start + 1
    if not description:
        collected = []
        for j in range(start + 1, len(lines)):
            line = lines[j]
            if line.startswith("# "):
                end = j
                break
            if line.strip():
                collected.append(line.strip())
            end = j + 1
        description = " ".join(collected).strip()

    description = re.sub(r"\s+", " ", description).strip()
    if not description:
        description = f"{article_title}について、購入前に確認したいポイントを整理します。"

    body = "\n".join(lines[end:]).lstrip()
    return description, body


def frontmatter_for_q000005(article, preflight, description):
    today = date.today().isoformat()
    return [
        "---",
        f"title: {yaml_quote(article.get('article_title') or article.get('title'))}",
        f"description: {yaml_quote(description)}",
        f'pubDate: "{today}"',
        f'updatedDate: "{today}"',
        "draft: true",
        'category: "スマホ"',
        "tags:",
        '  - "motorola"',
        '  - "edge 60"',
        '  - "スマホ"',
        '  - "Android"',
        f"slug: {yaml_quote(preflight.get('slug_candidate'))}",
        'queue_id: "q000005"',
        'source_type: "rss"',
        'source_url: "https://k-tai.watch.impress.co.jp/docs/news/2116804.html"',
        'product_id: "motorola-edge-60-product-001"',
        'offer_id: "motorola-edge-60-offer-001"',
        'url_status: "needs_url_check"',
        'cta_policy: "strong_cta_not_allowed_until_url_confirmed"',
        f"qualityScore: {article.get('quality_score', '').strip() or '100'}",
        "---",
        "",
        "<!-- URL未確認・ProductCard未完成のため、公開前に価格・在庫・販売ページを確認する。強い購入CTAは禁止。 -->",
        "",
    ]


def frontmatter_for_default(article, preflight, description):
    today = date.today().isoformat()
    quality_score = article.get("quality_score", "").strip() or "100"
    slug = preflight.get("slug_candidate", "").strip()
    return [
        "---",
        f"title: {yaml_quote(article.get('article_title') or article.get('title'))}",
        f"description: {yaml_quote(description)}",
        f'pubDate: "{today}"',
        f'updatedDate: "{today}"',
        "draft: true",
        'category: "モバイルWiFi"',
        "tags:",
        '  - "FS040W"',
        '  - "povo"',
        '  - "モバイルWiFi"',
        '  - "ルーター設定"',
        f"slug: {yaml_quote(slug)}",
        f"sourceQueueId: {yaml_quote(article.get('queue_id'))}",
        f"qualityScore: {quality_score}",
        "---",
        "",
    ]


def build_frontmatter(article, preflight, description):
    if article.get("queue_id", "").strip() == "q000005":
        return "\n".join(frontmatter_for_q000005(article, preflight, description))
    return "\n".join(frontmatter_for_default(article, preflight, description))


def h1_count(markdown):
    return len(re.findall(r"^# (?!#).+", markdown, flags=re.MULTILINE))


def write_markdown_report(rows):
    lines = ["# Astro Article Build Report", ""]
    for row in rows:
        lines.append(f"- {row['queue_id']}: {row['status']} {row['output_file'] or 'none'}")
        lines.append(f"  - slug: {row['slug']}")
        lines.append(f"  - h1_count: {row['h1_count']}")
        lines.append(f"  - warnings: {row['warnings'] or 'none'}")
    built = sum(1 for row in rows if row["status"] == "built")
    skipped = sum(1 for row in rows if row["status"].startswith("skipped"))
    lines.extend(["", f"built: {built}", f"skipped: {skipped}"])
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LEGACY_REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Build Astro-ready draft Markdown from a passed draft.")
    parser.add_argument("--queue-id", default=DEFAULT_QUEUE_ID, help=f"Queue ID to build. Default: {DEFAULT_QUEUE_ID}")
    args = parser.parse_args()
    target_queue_id = args.queue_id.strip()

    preflight_rows = [
        row
        for row in read_csv(PREFLIGHT_CSV)
        if row.get("decision", "").strip() == "ready_for_astro"
        and row.get("queue_id", "").strip() == target_queue_id
    ]
    article_rows = articles_by_queue(read_csv(ARTICLES_CSV))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    report_rows = []
    for preflight in preflight_rows:
        queue_id = preflight.get("queue_id", "").strip()
        article = article_rows.get(queue_id)
        slug = preflight.get("slug_candidate", "").strip()
        output_path = OUTPUT_DIR / f"{slug}.md"
        warnings = preflight.get("warnings", "").strip()

        if not article:
            report_rows.append(
                {"queue_id": queue_id, "slug": slug, "output_file": "", "status": "skipped_article_not_found", "h1_count": "", "warnings": warnings}
            )
            continue
        if output_path.exists():
            report_rows.append(
                {
                    "queue_id": queue_id,
                    "slug": slug,
                    "output_file": output_path.relative_to(ROOT).as_posix(),
                    "status": "skipped_output_exists",
                    "h1_count": "",
                    "warnings": warnings,
                }
            )
            continue

        draft_file = article.get("draft_file", "").strip() or article.get("draft_path", "").strip()
        draft_path = ROOT / draft_file
        if not draft_path.exists():
            report_rows.append(
                {"queue_id": queue_id, "slug": slug, "output_file": "", "status": "skipped_draft_not_found", "h1_count": "", "warnings": warnings}
            )
            continue

        draft = draft_path.read_text(encoding="utf-8")
        description, body = extract_description(draft, article.get("article_title") or article.get("title"))
        frontmatter = build_frontmatter(article, preflight, description)
        output = frontmatter + body.rstrip() + "\n"
        output_path.write_text(output, encoding="utf-8")

        report_rows.append(
            {
                "queue_id": queue_id,
                "slug": slug,
                "output_file": output_path.relative_to(ROOT).as_posix(),
                "status": "built",
                "h1_count": str(h1_count(body)),
                "warnings": warnings,
            }
        )

    if not report_rows:
        report_rows.append(
            {
                "queue_id": target_queue_id,
                "slug": "",
                "output_file": "",
                "status": "skipped_not_ready_for_astro",
                "h1_count": "",
                "warnings": "ready_for_astro row not found",
            }
        )

    write_csv(REPORT_CSV, report_rows)
    write_markdown_report(report_rows)
    built = sum(1 for row in report_rows if row["status"] == "built")
    skipped = len(report_rows) - built
    print(f"built={built} skipped={skipped}")


if __name__ == "__main__":
    main()
