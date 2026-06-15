import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"

QUEUE_PATH = DATA_DIR / "article_queue.csv"
REVIEW_REPORT_PATH = OUTPUT_DIR / "outline_review_report.csv"
OUTPUT_CSV_PATH = OUTPUT_DIR / "body_prompt_queue.csv"
OUTPUT_REPORT_PATH = OUTPUT_DIR / "body_prompt_queue_report.md"

OUTPUT_COLUMNS = [
    "queue_id",
    "keyword",
    "article_title",
    "article_type",
    "queue_status",
    "prompt_file",
    "next_action",
    "notes",
]
REQUIRED_QUEUE_COLUMNS = {"queue_id", "keyword", "article_title", "article_type", "status"}
REQUIRED_REVIEW_COLUMNS = {"queue_id", "decision"}


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return reader.fieldnames or [], rows


def require_columns(label, columns, required):
    missing = sorted(required - set(columns))
    if missing:
        raise SystemExit(f"Missing columns in {label}: {', '.join(missing)}")


def prompt_path_for(queue_id):
    return Path("output") / "body_prompts" / f"{queue_id}_body_prompt.md"


def build_queue_rows():
    review_columns, review_rows = read_csv(REVIEW_REPORT_PATH)
    queue_columns, queue_rows = read_csv(QUEUE_PATH)

    require_columns("output/outline_review_report.csv", review_columns, REQUIRED_REVIEW_COLUMNS)
    require_columns("data/article_queue.csv", queue_columns, REQUIRED_QUEUE_COLUMNS)

    queue_by_id = {row.get("queue_id", "").strip(): row for row in queue_rows}
    ready_ids = [
        (row.get("queue_id") or "").strip()
        for row in review_rows
        if (row.get("decision") or "").strip() == "ready_for_body"
    ]

    output_rows = []
    missing_prompts = []
    missing_queue_rows = []

    for queue_id in ready_ids:
        if not queue_id:
            continue

        queue_row = queue_by_id.get(queue_id)
        relative_prompt_path = prompt_path_for(queue_id).as_posix()
        absolute_prompt_path = ROOT / relative_prompt_path
        prompt_exists = absolute_prompt_path.exists()

        if queue_row is None:
            missing_queue_rows.append(queue_id)
            output_rows.append(
                {
                    "queue_id": queue_id,
                    "keyword": "",
                    "article_title": "",
                    "article_type": "",
                    "queue_status": "",
                    "prompt_file": relative_prompt_path,
                    "next_action": "needs_review",
                    "notes": "missing article_queue row",
                }
            )
            continue

        if not prompt_exists:
            missing_prompts.append(queue_id)

        output_rows.append(
            {
                "queue_id": queue_id,
                "keyword": queue_row.get("keyword", ""),
                "article_title": queue_row.get("article_title", ""),
                "article_type": queue_row.get("article_type", ""),
                "queue_status": queue_row.get("status", ""),
                "prompt_file": relative_prompt_path,
                "next_action": "send_to_gpt" if prompt_exists else "missing_prompt",
                "notes": "ready_for_body prompt available" if prompt_exists else "ready_for_body but prompt file is missing",
            }
        )

    return output_rows, ready_ids, missing_prompts, missing_queue_rows


def write_queue_csv(rows):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_report(rows, ready_ids, missing_prompts, missing_queue_rows):
    lines = [
        "# Body Prompt Queue Report",
        "",
        f"Generated rows: {len(rows)}",
        f"Ready queue IDs: {', '.join(ready_ids) if ready_ids else 'none'}",
        "",
        "## Missing Prompt Files",
    ]
    if missing_prompts:
        lines.extend([f"- {queue_id}: {prompt_path_for(queue_id).as_posix()}" for queue_id in missing_prompts])
    else:
        lines.append("- none")

    lines.extend(["", "## Missing Queue Rows"])
    if missing_queue_rows:
        lines.extend([f"- {queue_id}" for queue_id in missing_queue_rows])
    else:
        lines.append("- none")

    lines.extend(["", "## Queue Rows"])
    if rows:
        lines.extend([f"- {row['queue_id']}: {row['next_action']} ({row['prompt_file']})" for row in rows])
    else:
        lines.append("- none")

    OUTPUT_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    rows, ready_ids, missing_prompts, missing_queue_rows = build_queue_rows()
    write_queue_csv(rows)
    write_report(rows, ready_ids, missing_prompts, missing_queue_rows)

    print(f"generated={len(rows)} csv={OUTPUT_CSV_PATH} report={OUTPUT_REPORT_PATH}")
    for row in rows:
        print(f"{row['queue_id']} {row['next_action']} {row['prompt_file']}")


if __name__ == "__main__":
    main()

