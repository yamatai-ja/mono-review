from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"

DRY_RUN_PATH = OUTPUT_DIR / "rss_to_article_queue_dry_run.csv"
ARTICLE_QUEUE_PATH = DATA_DIR / "article_queue.csv"
REPORT_CSV_PATH = OUTPUT_DIR / "rss_to_article_queue_apply_report.csv"
REPORT_MD_PATH = OUTPUT_DIR / "rss_to_article_queue_apply_report.md"

REPORT_FIELDS = [
    "stage",
    "action",
    "result",
    "queue_id",
    "keyword",
    "article_title",
    "before_rows",
    "after_rows",
    "before_sha256",
    "after_sha256",
    "backup_file",
    "reason",
]


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        rows = [{k: (v or "") for k, v in row.items()} for row in reader]
    return fields, rows


def write_csv_rows(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def file_sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row_count(path: Path) -> int:
    return len(read_csv_rows(path)[1])


def add_test_one_row() -> tuple[str, dict[str, str] | None]:
    _, rows = read_csv_rows(DRY_RUN_PATH)
    add_rows = [row for row in rows if row.get("recommendation") == "add_test_one"]
    if len(add_rows) != 1:
        return f"add_test_one count must be 1, got {len(add_rows)}", None
    return "", add_rows[0]


def duplicate_reason(candidate: dict[str, str], existing_rows: list[dict[str, str]]) -> str:
    queue_id = candidate.get("candidate_rank", "")
    keyword = candidate.get("target_keyword", "")
    article_title = candidate.get("article_title", "")
    source_url = candidate.get("source_url", "")
    for row in existing_rows:
        if queue_id and row.get("queue_id") == queue_id:
            return f"duplicate queue_id: {queue_id}"
        if keyword and row.get("keyword") == keyword:
            return f"duplicate keyword: {keyword}"
        if article_title and row.get("article_title") == article_title:
            return f"duplicate article_title: {article_title}"
        if source_url and source_url in " ".join(str(value) for value in row.values()):
            return f"duplicate source_url: {source_url}"
    return ""


def build_queue_row(candidate: dict[str, str], fields: list[str]) -> dict[str, str]:
    notes = (
        f"source=rss | source_item_id={candidate.get('source_item_id', '')} | "
        f"url={candidate.get('source_url', '')} | dry_run_priority={candidate.get('priority', '')}"
    )
    values = {
        "queue_id": candidate.get("candidate_rank", ""),
        "keyword": candidate.get("target_keyword", ""),
        "article_title": candidate.get("article_title", ""),
        "article_type": candidate.get("article_type", ""),
        "priority": candidate.get("priority", ""),
        "status": candidate.get("status", "candidate_from_rss"),
        "assigned_product_ids": "",
        "notes": notes,
        "created_at": now_iso(),
    }
    return {field: values.get(field, "") for field in fields}


def write_reports(records: list[dict[str, str]]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    with REPORT_CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field, "") for field in REPORT_FIELDS})

    lines = ["# RSS to Article Queue Apply Report", "", f"Generated: {now_iso()}", ""]
    for record in records:
        lines.extend(
            [
                f"## {record.get('stage', '')}",
                "",
                f"- action: {record.get('action', '')}",
                f"- result: {record.get('result', '')}",
                f"- queue_id: {record.get('queue_id', '')}",
                f"- keyword: {record.get('keyword', '')}",
                f"- article_title: {record.get('article_title', '')}",
                f"- before_rows: {record.get('before_rows', '')}",
                f"- after_rows: {record.get('after_rows', '')}",
                f"- backup_file: {record.get('backup_file', '')}",
                f"- reason: {record.get('reason', '')}",
                "",
            ]
        )
    REPORT_MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def make_record(
    stage: str,
    action: str,
    result: str,
    candidate: dict[str, str] | None,
    before_rows: int,
    after_rows: int,
    before_sha: str,
    after_sha: str,
    backup_file: str,
    reason: str,
) -> dict[str, str]:
    candidate = candidate or {}
    return {
        "stage": stage,
        "action": action,
        "result": result,
        "queue_id": candidate.get("candidate_rank", ""),
        "keyword": candidate.get("target_keyword", ""),
        "article_title": candidate.get("article_title", ""),
        "before_rows": str(before_rows),
        "after_rows": str(after_rows),
        "before_sha256": before_sha,
        "after_sha256": after_sha,
        "backup_file": backup_file,
        "reason": reason,
    }


def run(apply: bool) -> int:
    records: list[dict[str, str]] = []
    before_sha = file_sha256(ARTICLE_QUEUE_PATH)
    before_count = row_count(ARTICLE_QUEUE_PATH)
    error, candidate = add_test_one_row()
    fields, existing_rows = read_csv_rows(ARTICLE_QUEUE_PATH)

    if error:
        after_sha = file_sha256(ARTICLE_QUEUE_PATH)
        after_count = row_count(ARTICLE_QUEUE_PATH)
        records.append(make_record("dry-run" if not apply else "apply", "validate", "manual_review", candidate, before_count, after_count, before_sha, after_sha, "", error))
        write_reports(records)
        print(f"result=manual_review reason={error}")
        return 1

    required = ["queue_id", "keyword", "article_title", "article_type", "priority", "status", "assigned_product_ids", "notes", "created_at"]
    missing_required = [field for field in required if field not in fields]
    if missing_required:
        reason = "article_queue header missing required fields: " + ", ".join(missing_required)
        after_sha = file_sha256(ARTICLE_QUEUE_PATH)
        after_count = row_count(ARTICLE_QUEUE_PATH)
        records.append(make_record("dry-run" if not apply else "apply", "validate", "manual_review", candidate, before_count, after_count, before_sha, after_sha, "", reason))
        write_reports(records)
        print(f"result=manual_review reason={reason}")
        return 1

    dup = duplicate_reason(candidate or {}, existing_rows)
    if dup:
        after_sha = file_sha256(ARTICLE_QUEUE_PATH)
        after_count = row_count(ARTICLE_QUEUE_PATH)
        stage = "apply" if apply else "dry-run"
        records.append(make_record(stage, "skip", "skipped_duplicate", candidate, before_count, after_count, before_sha, after_sha, "", dup))
        write_reports(records)
        print(f"result=skipped_duplicate reason={dup}")
        return 0

    if not apply:
        after_sha = file_sha256(ARTICLE_QUEUE_PATH)
        after_count = row_count(ARTICLE_QUEUE_PATH)
        result = "dry_run_ok" if before_sha == after_sha and before_count == after_count else "dry_run_changed"
        reason = "would append exactly one row" if result == "dry_run_ok" else "unexpected file change during dry-run"
        records.append(make_record("dry-run", "validate", result, candidate, before_count, after_count, before_sha, after_sha, "", reason))
        write_reports(records)
        print(f"result={result}")
        print(f"rows_before={before_count} rows_after={after_count}")
        print(f"sha_unchanged={str(before_sha == after_sha).lower()}")
        return 0 if result == "dry_run_ok" else 1

    timestamp = dt.datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = ARTICLE_QUEUE_PATH.with_name(f"{ARTICLE_QUEUE_PATH.name}.bak.{timestamp}")
    shutil.copy2(ARTICLE_QUEUE_PATH, backup_path)

    new_row = build_queue_row(candidate or {}, fields)
    write_csv_rows(ARTICLE_QUEUE_PATH, fields, existing_rows + [new_row])

    after_sha = file_sha256(ARTICLE_QUEUE_PATH)
    after_count = row_count(ARTICLE_QUEUE_PATH)
    added_rows = after_count - before_count
    result = "applied" if added_rows == 1 else "error"
    reason = "appended exactly one row" if added_rows == 1 else f"expected +1 row, got {added_rows}"
    records.append(make_record("apply", "append", result, candidate, before_count, after_count, before_sha, after_sha, str(backup_path), reason))
    write_reports(records)
    print(f"result={result}")
    print(f"rows_before={before_count} rows_after={after_count}")
    print(f"backup={backup_path}")
    return 0 if result == "applied" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely append one RSS add_test_one candidate to article_queue.csv.")
    parser.add_argument("--apply", action="store_true", help="Append one row after validation. Omit for dry-run.")
    args = parser.parse_args()
    return run(apply=args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
