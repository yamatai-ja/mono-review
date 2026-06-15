from __future__ import annotations

import argparse
import csv
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"

DEFAULT_QUEUE_ID = "q000003"
ARTICLES_CSV = DATA_DIR / "articles.csv"
ARTICLE_QUEUE_CSV = DATA_DIR / "article_queue.csv"
DRAFT_QUALITY_CSV = OUTPUT_DIR / "draft_quality_report.csv"
BODY_PROMPT_QUEUE_CSV = OUTPUT_DIR / "body_prompt_queue.csv"
REPORT_CSV = OUTPUT_DIR / "article_register_report.csv"
REPORT_MD = OUTPUT_DIR / "article_register_report.md"

ALLOWED_APPEND_COLUMNS = [
    "queue_id",
    "article_title",
    "article_type",
    "draft_file",
    "quality_score",
    "created_at",
]
REQUIRED_ARTICLE_FIELDS = [
    "queue_id",
    "article_title",
    "keyword",
    "article_type",
    "draft_file",
    "quality_score",
    "status",
    "created_at",
    "notes",
]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames or [], list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


REPORT_COLUMNS = [
    "queue_id",
    "added",
    "skipped",
    "skipped_reason",
    "articles_csv_updated",
    "backup_file",
]


def write_report(
    added: int,
    skipped: int,
    registered_queue_id: str,
    skipped_reason: str,
    updated: bool,
    backup_file: str = "",
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with REPORT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "queue_id": registered_queue_id,
                "added": str(added),
                "skipped": str(skipped),
                "skipped_reason": skipped_reason,
                "articles_csv_updated": str(updated).lower(),
                "backup_file": backup_file,
            }
        )

    lines = [
        "# Article Register Report",
        "",
        f"added: {added}",
        f"skipped: {skipped}",
        f"registered_queue_id: {registered_queue_id or 'none'}",
        f"skipped_reason: {skipped_reason or 'none'}",
        f"articles_csv_updated: {str(updated).lower()}",
        f"backup_file: {backup_file or 'none'}",
        "",
        "Note: this tool registers a passed draft into data/articles.csv. It does not generate or modify article body text.",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def find_row(rows: list[dict[str, str]], key: str, value: str) -> dict[str, str] | None:
    for row in rows:
        if (row.get(key) or "").strip() == value:
            return row
    return None


def normalize_article_columns(columns: list[str]) -> tuple[list[str], list[str]]:
    if not columns:
        columns = ["article_id", "title", "slug", "keyword", "status", "draft_path", "published_url", "updated_at", "notes"]
    missing_required = [name for name in REQUIRED_ARTICLE_FIELDS if name not in columns]
    not_allowed = [name for name in missing_required if name not in ALLOWED_APPEND_COLUMNS]
    if not_allowed:
        # These are expected to exist in the current MVP schema. Do not invent unapproved columns.
        raise SystemExit("Missing non-appendable articles.csv columns: " + ", ".join(not_allowed))
    append_columns = [name for name in ALLOWED_APPEND_COLUMNS if name in missing_required]
    return [*columns, *append_columns], append_columns


def build_article_row(
    columns: list[str],
    body_prompt_row: dict[str, str],
    quality_row: dict[str, str],
    article_queue_row: dict[str, str] | None,
    created_at: str,
) -> dict[str, str]:
    queue_id = body_prompt_row.get("queue_id", "")
    article_title = body_prompt_row.get("article_title", "")
    keyword = body_prompt_row.get("keyword", "")
    draft_file = (OUTPUT_DIR / "drafts" / f"{queue_id}_draft.md").relative_to(ROOT).as_posix()
    row = {name: "" for name in columns}
    source_notes = article_queue_row.get("notes", "") if article_queue_row else ""
    notes = f"registered_from={queue_id} | quality_pass"
    if "source=rss" in source_notes:
        notes = (
            f"{notes} | source=rss | source URL: https://k-tai.watch.impress.co.jp/docs/news/2116804.html "
            "| product_id=motorola-edge-60-product-001 | offer_id=motorola-edge-60-offer-001 "
            "| product/offer URL needs check | strong CTA not allowed until URL confirmed"
        )

    values = {
        "article_id": queue_id,
        "title": article_title,
        "slug": queue_id,
        "keyword": keyword,
        "status": "draft_ready",
        "draft_path": draft_file,
        "published_url": "",
        "updated_at": created_at,
        "notes": notes,
        "queue_id": queue_id,
        "article_title": article_title,
        "article_type": body_prompt_row.get("article_type", ""),
        "draft_file": draft_file,
        "quality_score": quality_row.get("quality_score", ""),
        "created_at": created_at,
    }
    for key, value in values.items():
        if key in row:
            row[key] = value
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="Register a passed draft into data/articles.csv.")
    parser.add_argument("--queue-id", default=DEFAULT_QUEUE_ID, help=f"Queue ID to register. Default: {DEFAULT_QUEUE_ID}")
    args = parser.parse_args()
    queue_id = args.queue_id.strip()
    draft_file = OUTPUT_DIR / "drafts" / f"{queue_id}_draft.md"

    article_columns, article_rows = read_csv(ARTICLES_CSV)
    queue_columns, queue_rows = read_csv(ARTICLE_QUEUE_CSV)
    body_columns, body_rows = read_csv(BODY_PROMPT_QUEUE_CSV)
    quality_columns, quality_rows = read_csv(DRAFT_QUALITY_CSV)

    article_columns, append_columns = normalize_article_columns(article_columns)

    body_row = find_row(body_rows, "queue_id", queue_id)
    if body_row is None:
        write_report(0, 1, "", "queue_id not found in body_prompt_queue.csv", False)
        return 1

    quality_row = find_row(quality_rows, "queue_id", queue_id)
    if quality_row is None:
        write_report(0, 1, "", "queue_id not found in draft_quality_report.csv", False)
        return 1
    if (quality_row.get("decision") or "").strip() != "pass":
        write_report(0, 1, "", "quality decision is not pass", False)
        return 1
    if not draft_file.exists():
        write_report(0, 1, "", "draft file does not exist", False)
        return 1

    duplicate = (
        find_row(article_rows, "queue_id", queue_id)
        or find_row(article_rows, "article_id", queue_id)
    )
    if duplicate is not None:
        write_report(0, 1, "", "queue_id already registered", False)
        print("added=0 skipped=1 reason=queue_id already registered")
        return 0

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    normalized_rows = [{name: row.get(name, "") for name in article_columns} for row in article_rows]
    article_queue_row = find_row(queue_rows, "queue_id", queue_id)
    normalized_rows.append(build_article_row(article_columns, body_row, quality_row, article_queue_row, created_at))
    backup_file = ARTICLES_CSV.with_name(f"articles.csv.bak.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    shutil.copy2(ARTICLES_CSV, backup_file)
    write_csv(ARTICLES_CSV, article_columns, normalized_rows)
    write_report(1, 0, queue_id, "", True, backup_file.relative_to(ROOT).as_posix())
    print(f"added=1 skipped=0 registered={queue_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
