from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
BODY_PROMPT_QUEUE_CSV = OUTPUT_DIR / "body_prompt_queue.csv"
DRAFTS_DIR = OUTPUT_DIR / "drafts"
REPORT_PATH = OUTPUT_DIR / "draft_receive_report.md"

REQUIRED_QUEUE_COLUMNS = {"queue_id", "prompt_file", "next_action"}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames or [], list(reader)


def write_report(status: str, queue_id: str, source: Path | None, destination: Path | None, message: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Draft Receive Report",
        "",
        f"status: {status}",
        f"queue_id: {queue_id or 'none'}",
        f"source: {source.as_posix() if source else 'none'}",
        f"destination: {destination.relative_to(ROOT).as_posix() if destination and destination.is_absolute() else (destination.as_posix() if destination else 'none')}",
        f"message: {message}",
        "",
        "Note: this tool only saves an already generated draft. It does not generate article body text.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def fail(message: str, queue_id: str = "", source: Path | None = None, destination: Path | None = None) -> int:
    write_report("error", queue_id, source, destination, message)
    print(f"error: {message}", file=sys.stderr)
    return 1


def find_queue_row(queue_id: str) -> dict[str, str] | None:
    columns, rows = read_csv(BODY_PROMPT_QUEUE_CSV)
    missing = sorted(REQUIRED_QUEUE_COLUMNS - set(columns))
    if missing:
        raise ValueError("Missing columns in output/body_prompt_queue.csv: " + ", ".join(missing))
    for row in rows:
        if (row.get("queue_id") or "").strip() == queue_id:
            return row
    return None


def receive_draft(queue_id: str, draft_file: Path) -> int:
    if not BODY_PROMPT_QUEUE_CSV.exists():
        return fail("output/body_prompt_queue.csv does not exist", queue_id, draft_file, None)

    try:
        queue_row = find_queue_row(queue_id)
    except ValueError as exc:
        return fail(str(exc), queue_id, draft_file, None)

    if queue_row is None:
        return fail("queue_id not found in output/body_prompt_queue.csv", queue_id, draft_file, None)

    next_action = (queue_row.get("next_action") or "").strip()
    if next_action != "send_to_gpt":
        return fail(f"queue_id is not receivable: next_action={next_action or 'blank'}", queue_id, draft_file, None)

    if not draft_file.exists():
        destination = DRAFTS_DIR / f"{queue_id}_draft.md"
        return fail("draft_file does not exist", queue_id, draft_file, destination)
    if not draft_file.is_file():
        destination = DRAFTS_DIR / f"{queue_id}_draft.md"
        return fail("draft_file is not a file", queue_id, draft_file, destination)

    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    destination = DRAFTS_DIR / f"{queue_id}_draft.md"
    if destination.exists():
        return fail("destination draft already exists; refusing to overwrite", queue_id, draft_file, destination)

    # Preserve the draft body exactly as supplied, while validating it can be read as UTF-8.
    draft_file.read_text(encoding="utf-8")
    shutil.copyfile(draft_file, destination)
    write_report("saved", queue_id, draft_file, destination, "draft saved without modification")
    print(f"saved {destination.relative_to(ROOT).as_posix()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Receive an already generated article draft and save it by queue_id. This tool does not generate article body text."
    )
    parser.add_argument("--queue-id", required=True, help="Queue ID from output/body_prompt_queue.csv, e.g. q000003")
    parser.add_argument("--draft-file", required=True, help="Path to an existing UTF-8 Markdown draft generated outside Codex")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return receive_draft(args.queue_id.strip(), Path(args.draft_file))


if __name__ == "__main__":
    raise SystemExit(main())
