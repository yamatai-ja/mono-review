import argparse
import csv
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATION_CSV = ROOT / "output" / "astro_article_validation_report.csv"
DEFAULT_TARGET_DIR = ROOT / "src" / "content" / "posts"
REPORT_CSV = ROOT / "output" / "astro_draft_copy_report.csv"
REPORT_MD = ROOT / "output" / "astro_draft_copy_report.md"

REPORT_FIELDS = ["queue_id", "status", "reason", "source", "target"]


def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def checked_at():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_report(rows):
    REPORT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    lines = ["# Astro Draft Copy Report", "", f"checked_at: {checked_at()}", ""]
    for row in rows:
        lines.append(f"## {row['source']}")
        lines.append(f"- queue_id: {row.get('queue_id') or 'unknown'}")
        lines.append(f"- status: {row['status']}")
        lines.append(f"- reason: {row['reason']}")
        lines.append(f"- source: {row['source']}")
        lines.append(f"- target: {row['target']}")
        lines.append("")
    copied = sum(1 for row in rows if row["status"] == "copied")
    skipped = sum(1 for row in rows if row["status"] == "skipped")
    errors = sum(1 for row in rows if row["status"] == "error")
    lines.extend([f"copied: {copied}", f"skipped: {skipped}", f"error: {errors}"])
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def ensure_draft_true(path):
    text = path.read_text(encoding="utf-8")
    return "draft: true" in text


def copy_ready_articles(target_dir, queue_id=None):
    rows = []
    validation_rows = read_csv(VALIDATION_CSV)
    ready_rows = [row for row in validation_rows if row.get("decision", "").strip() == "ready_to_copy"]
    if queue_id:
        ready_rows = [row for row in ready_rows if (row.get("sourceQueueId") or "").strip() == queue_id]

    if not ready_rows:
        rows.append(
            {
                "status": "error",
                "reason": "no ready_to_copy articles found",
                "source": str(VALIDATION_CSV.relative_to(ROOT)),
                "target": str(target_dir),
                "queue_id": queue_id or "",
            }
        )
        return rows

    for row in ready_rows:
        source_rel = row.get("file", "").strip()
        source_path = ROOT / source_rel
        target_path = target_dir / source_path.name
        row_queue_id = (row.get("sourceQueueId") or "").strip()

        if not source_rel or not source_path.exists():
            rows.append(
                {
                    "status": "error",
                    "reason": "source file not found",
                    "source": source_rel or "unknown",
                    "target": str(target_path),
                    "queue_id": row_queue_id,
                }
            )
            continue

        if target_path.exists():
            rows.append(
                {
                    "status": "skipped",
                    "reason": "target file already exists",
                    "source": str(source_path.relative_to(ROOT)),
                    "target": str(target_path),
                    "queue_id": row_queue_id,
                }
            )
            continue

        shutil.copyfile(source_path, target_path)
        if target_path.stat().st_size == 0:
            rows.append(
                {
                    "status": "error",
                    "reason": "copied file size is zero",
                    "source": str(source_path.relative_to(ROOT)),
                    "target": str(target_path),
                    "queue_id": row_queue_id,
                }
            )
            continue
        if not ensure_draft_true(target_path):
            rows.append(
                {
                    "status": "error",
                    "reason": "draft true not found after copy",
                    "source": str(source_path.relative_to(ROOT)),
                    "target": str(target_path),
                    "queue_id": row_queue_id,
                }
            )
            continue

        rows.append(
            {
                "status": "copied",
                "reason": "copied draft markdown without modification",
                "source": str(source_path.relative_to(ROOT)),
                "target": str(target_path),
                "queue_id": row_queue_id,
            }
        )

    return rows


def parse_args():
    parser = argparse.ArgumentParser(
        description="Copy validated Astro draft markdown files to an existing target directory."
    )
    parser.add_argument("--queue-id", help="Copy only one validated queue_id.")
    parser.add_argument("--target-dir", help="Existing Astro article directory to copy drafts into. Default: src/content/posts")
    return parser.parse_args()


def main():
    args = parse_args()
    target_dir = Path(args.target_dir) if args.target_dir else DEFAULT_TARGET_DIR
    if not target_dir.exists():
        rows = [
            {
                "status": "error",
                "reason": "target directory does not exist",
                "source": str(VALIDATION_CSV.relative_to(ROOT)),
                "target": str(target_dir),
                "queue_id": args.queue_id or "",
            }
        ]
        write_report(rows)
        print("error: target directory does not exist")
        return 1
    if not target_dir.is_dir():
        rows = [
            {
                "status": "error",
                "reason": "target path is not a directory",
                "source": str(VALIDATION_CSV.relative_to(ROOT)),
                "target": str(target_dir),
                "queue_id": args.queue_id or "",
            }
        ]
        write_report(rows)
        print("error: target path is not a directory")
        return 1

    rows = copy_ready_articles(target_dir, args.queue_id)
    write_report(rows)
    copied = sum(1 for row in rows if row["status"] == "copied")
    skipped = sum(1 for row in rows if row["status"] == "skipped")
    errors = sum(1 for row in rows if row["status"] == "error")
    print(f"copied={copied} skipped={skipped} error={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
