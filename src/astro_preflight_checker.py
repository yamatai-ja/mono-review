import argparse
import csv
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTICLES_CSV = ROOT / "data" / "articles.csv"
DRAFT_QUALITY_CSV = ROOT / "output" / "draft_quality_report.csv"
REPORT_CSV = ROOT / "output" / "astro_preflight_report.csv"
REPORT_MD = ROOT / "output" / "astro_preflight_report.md"

REPORT_FIELDS = [
    "queue_id",
    "article_title",
    "slug_candidate",
    "decision",
    "missing_items",
    "warnings",
    "checked_at",
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


def write_markdown(path, rows):
    lines = ["# Astro Preflight Report", ""]
    lines.append(f"total: {len(rows)}")
    lines.append("")
    for row in rows:
        lines.append(f"## {row['queue_id']}")
        lines.append(f"- decision: {row['decision']}")
        lines.append(f"- slug_candidate: {row['slug_candidate']}")
        lines.append(f"- missing_items: {row['missing_items']}")
        lines.append(f"- warnings: {row['warnings']}")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def safe_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def count_h1(markdown):
    return len(re.findall(r"^# (?!#).+", markdown, flags=re.MULTILINE))


def has_meta_description(markdown):
    return "メタディスクリプション" in markdown or "meta description" in markdown.lower()


def slug_for(row):
    if row.get("queue_id") == "q000003":
        return "fs040w-povo-setting"
    slug_value = (row.get("slug") or "").strip()
    if slug_value and slug_value != (row.get("queue_id") or "").strip():
        source = slug_value
    else:
        source = row.get("keyword") or row.get("article_title") or row.get("title") or row.get("queue_id", "")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", source.lower()).strip("-")
    return slug or row.get("queue_id", "")


def quality_by_queue(rows):
    return {row.get("queue_id", ""): row for row in rows}


def check_article(row, quality_rows, checked_at):
    missing = []
    warnings = []
    blockers = []

    queue_id = row.get("queue_id", "").strip()
    article_title = (row.get("article_title") or row.get("title") or "").strip()
    keyword = row.get("keyword", "").strip()
    article_type = row.get("article_type", "").strip()
    draft_file = row.get("draft_file", "").strip() or row.get("draft_path", "").strip()
    status = row.get("status", "").strip()
    notes = row.get("notes", "").strip()
    quality_score = safe_int(row.get("quality_score", ""))
    slug_candidate = slug_for(row)

    required_values = {
        "queue_id": queue_id,
        "article_title": article_title,
        "keyword": keyword,
        "article_type": article_type,
        "draft_file": draft_file,
        "status=draft_ready": status == "draft_ready",
        "quality_score": row.get("quality_score", "").strip(),
        "slug_candidate": slug_candidate,
    }
    for name, value in required_values.items():
        if not value:
            missing.append(name)

    if quality_score is None:
        missing.append("quality_score_numeric")
    elif quality_score < 80:
        blockers.append("quality_score_below_80")

    if status != "draft_ready":
        blockers.append("status_not_draft_ready")

    quality = quality_rows.get(queue_id)
    if not quality:
        blockers.append("draft_quality_report_missing")
    elif quality.get("decision", "").strip() != "pass":
        blockers.append("draft_quality_not_pass")

    draft_path = ROOT / draft_file if draft_file else None
    draft_text = ""
    if not draft_path:
        blockers.append("draft_file_missing")
    elif not draft_path.exists():
        blockers.append("draft_file_not_found")
    else:
        draft_text = draft_path.read_text(encoding="utf-8")
        h1_count = count_h1(draft_text)
        if h1_count != 1:
            blockers.append(f"h1_count={h1_count}")
        if not has_meta_description(draft_text):
            missing.append("meta_description")

    frontmatter_candidates = {
        "title": article_title,
        "description": has_meta_description(draft_text) if draft_text else False,
        "pubDate": True,
        "updatedDate": True,
        "draft": True,
        "tags": keyword,
        "category": article_type,
        "slug": slug_candidate,
        "sourceQueueId": queue_id,
    }
    for name, value in frontmatter_candidates.items():
        if not value:
            missing.append(f"frontmatter:{name}")

    if blockers:
        decision = "blocked"
    elif missing:
        decision = "needs_fix"
    else:
        decision = "ready_for_astro"

    if quality and quality.get("warnings", "").strip():
        warnings.append(f"quality_warnings={quality.get('warnings', '').strip()}")
    if "product/offer URL needs check" in notes or "strong CTA not allowed" in notes:
        warnings.append("url_unconfirmed_strong_cta_not_allowed")

    return {
        "queue_id": queue_id,
        "article_title": article_title,
        "slug_candidate": slug_candidate,
        "decision": decision,
        "missing_items": "; ".join(dict.fromkeys(missing + blockers)) or "none",
        "warnings": "; ".join(warnings) or "none",
        "checked_at": checked_at,
    }


def main():
    parser = argparse.ArgumentParser(description="Check draft_ready articles before Astro Markdown generation.")
    parser.add_argument("--queue-id", help="Check only one queue_id. Omit to check all draft_ready articles.")
    args = parser.parse_args()

    articles = read_csv(ARTICLES_CSV)
    quality_rows = quality_by_queue(read_csv(DRAFT_QUALITY_CSV))
    checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    rows = [
        check_article(row, quality_rows, checked_at)
        for row in articles
        if row.get("status", "").strip() == "draft_ready"
        and (not args.queue_id or row.get("queue_id", "").strip() == args.queue_id)
    ]

    write_csv(REPORT_CSV, rows)
    write_markdown(REPORT_MD, rows)

    for row in rows:
        print(
            f"{row['queue_id']}: {row['decision']} "
            f"slug={row['slug_candidate']} missing={row['missing_items']}"
        )


if __name__ == "__main__":
    main()
