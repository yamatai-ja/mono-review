import argparse
import csv
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_CSV = ROOT / "output" / "publish_preflight_report.csv"
REPORT_MD = ROOT / "output" / "publish_switch_report.md"


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_report(status, slug, source_file, reason, apply):
    lines = [
        "# Publish Switch Report",
        "",
        f"- checked_at: {now_iso()}",
        f"- slug: {slug}",
        f"- source_file: {source_file}",
        f"- mode: {'apply' if apply else 'dry-run'}",
        f"- status: {status}",
        f"- reason: {reason}",
        "",
        "Note: dry-run mode does not modify the article and does not create a backup.",
    ]
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def find_preflight(slug):
    for row in read_csv(PREFLIGHT_CSV):
        if row.get("slug", "").strip() == slug:
            return row
    return None


def split_frontmatter(text):
    if not text.startswith("---\n"):
        return None, text, "frontmatter_start_missing"
    end = text.find("\n---", 4)
    if end == -1:
        return None, text, "frontmatter_end_missing"
    return text[: end + len("\n---")], text[end + len("\n---") :], None


def switch_draft_line(frontmatter):
    pattern = re.compile(r"(?m)^draft:\s*(true|false)\s*$")
    match = pattern.search(frontmatter)
    if not match:
        return frontmatter, "missing"
    if match.group(1) == "false":
        return frontmatter, "already_false"
    return pattern.sub("draft: false", frontmatter, count=1), "switched"


def target_path_from_row(row):
    file_value = row.get("file", "").strip()
    if not file_value:
        return None
    return ROOT / file_value


def run(slug, apply):
    row = find_preflight(slug)
    if not row:
        write_report("blocked", slug, "unknown", "slug not found in publish preflight report", apply)
        return 1
    if row.get("decision", "").strip() != "ready_to_publish":
        write_report("blocked", slug, row.get("file", "unknown"), "decision is not ready_to_publish", apply)
        return 1

    path = target_path_from_row(row)
    if not path or not path.exists():
        write_report("error", slug, str(path or "unknown"), "target file does not exist", apply)
        return 1

    text = path.read_text(encoding="utf-8")
    frontmatter, body, error = split_frontmatter(text)
    if error:
        write_report("error", slug, str(path.relative_to(ROOT)), error, apply)
        return 1

    new_frontmatter, state = switch_draft_line(frontmatter)
    rel_path = str(path.relative_to(ROOT))
    if state == "missing":
        write_report("blocked", slug, rel_path, "draft line not found in frontmatter", apply)
        return 1
    if state == "already_false":
        write_report("skipped", slug, rel_path, "draft is already false", apply)
        return 0

    if not apply:
        write_report("dry-run", slug, rel_path, "would switch frontmatter draft: true to draft: false", apply)
        print("dry-run: would switch draft true to false")
        return 0

    backup_path = path.with_suffix(path.suffix + ".bak")
    backup_path.write_text(text, encoding="utf-8")
    path.write_text(new_frontmatter + body, encoding="utf-8")
    updated = path.read_text(encoding="utf-8")
    updated_frontmatter, _, updated_error = split_frontmatter(updated)
    if updated_error or not re.search(r"(?m)^draft:\s*false\s*$", updated_frontmatter or ""):
        write_report("error", slug, rel_path, "draft false not confirmed after apply", apply)
        return 1

    write_report("changed", slug, rel_path, f"switched to draft:false; backup={backup_path.name}", apply)
    print("changed: switched draft true to false")
    return 0


def parse_args():
    parser = argparse.ArgumentParser(
        description="Switch a ready_to_publish Astro draft from draft:true to draft:false."
    )
    parser.add_argument("--slug", required=True, help="Article slug to switch.")
    parser.add_argument("--apply", action="store_true", help="Actually modify the article. Omit for dry-run.")
    return parser.parse_args()


def main():
    args = parse_args()
    return run(args.slug, args.apply)


if __name__ == "__main__":
    sys.exit(main())
