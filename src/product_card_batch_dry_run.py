from __future__ import annotations

import csv
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_REPORT = ROOT / "output" / "product_card_migration_report.csv"
CSV_REPORT = ROOT / "output" / "product_card_batch_dry_run_report.csv"
MD_REPORT = ROOT / "output" / "product_card_batch_dry_run_report.md"
EXCLUDE_FILES = {"amazon-fire-tv-cube.md"}

CSV_COLUMNS = [
    "file",
    "slug",
    "link_count",
    "has_products_frontmatter",
    "status",
    "reason",
    "suggested_product_name",
    "checked_at",
]

MOJIBAKE_RE = re.compile(r"縺|繝|隨|蜃|窶|荳|鬲|譁|邵|郢")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(rows: list[dict[str, str]]) -> None:
    CSV_REPORT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_REPORT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, str]]) -> None:
    counts = count_statuses(rows)
    lines = [
        "# ProductCard Batch Dry-run Report",
        "",
        f"- total: {len(rows)}",
        f"- yes: {counts['yes']}",
        f"- manual_review: {counts['manual_review']}",
        f"- skipped: {counts['skipped']}",
        "",
        "## Results",
        "",
        "| file | slug | links | products | status | reason | suggested_product_name |",
        "| --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {file} | {slug} | {links} | {products} | {status} | {reason} | {name} |".format(
                file=Path(row["file"]).name,
                slug=row["slug"],
                links=row["link_count"],
                products=row["has_products_frontmatter"],
                status=row["status"],
                reason=escape_table(row["reason"]),
                name=escape_table(row["suggested_product_name"]),
            )
        )
    MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def count_statuses(rows: list[dict[str, str]]) -> dict[str, int]:
    return {
        "yes": sum(1 for row in rows if row["status"] == "yes"),
        "manual_review": sum(1 for row in rows if row["status"] == "manual_review"),
        "skipped": sum(1 for row in rows if row["status"] == "skipped"),
    }


def escape_table(value: str) -> str:
    return value.replace("|", "\\|")


def split_frontmatter(text: str) -> tuple[dict[str, Any], str, str]:
    if not text.startswith("---"):
        return {}, "", text
    lines = text.splitlines()
    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
    if end_index is None:
        return {}, "", text
    frontmatter_text = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :])
    return parse_frontmatter(frontmatter_text), frontmatter_text, body


def parse_frontmatter(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith((" ", "\t")) or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = clean_scalar(value.strip())
    return data


def clean_scalar(value: str) -> str:
    cleaned = value.strip()
    if (
        (cleaned.startswith('"') and cleaned.endswith('"'))
        or (cleaned.startswith("'") and cleaned.endswith("'"))
    ):
        cleaned = cleaned[1:-1]
    return cleaned


def has_products_frontmatter(frontmatter_text: str) -> bool:
    return re.search(r"(?m)^products\s*:", frontmatter_text) is not None


def resolve_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def infer_product_name(frontmatter: dict[str, Any], slug: str) -> tuple[str, str]:
    title = str(frontmatter.get("title") or "").strip()
    if not title:
        return slug.replace("-", " "), "title_missing_inferred_from_slug"
    for separator in (" の正直レビュー", "の正直レビュー", " レビュー", "レビュー", " | ", " - "):
        if separator in title:
            candidate = title.split(separator, 1)[0].strip()
            if candidate:
                return candidate, "inferred_from_title"
    return title[:80], "title_needs_manual_confirmation"


def is_mojibake(text: str) -> bool:
    return MOJIBAKE_RE.search(text) is not None


def evaluate_file(file_path: Path, report_rows: list[dict[str, str]], checked_at: str) -> dict[str, str]:
    text = file_path.read_text(encoding="utf-8")
    frontmatter, frontmatter_text, _body = split_frontmatter(text)
    slug = str(frontmatter.get("slug") or report_rows[0].get("slug") or file_path.stem)
    has_products = has_products_frontmatter(frontmatter_text)
    link_count = len(report_rows)
    suggested_name, name_reason = infer_product_name(frontmatter, slug)

    reasons: list[str] = []
    status = "yes"

    if link_count == 0:
        status = "skipped"
        reasons.append("links=0")
    if has_products:
        status = "skipped"
        reasons.append("products frontmatter already exists")
    if link_count >= 2:
        status = "manual_review"
        reasons.append("links>=2")
    if link_count == 1 and name_reason != "inferred_from_title":
        status = "manual_review"
        reasons.append(name_reason)
    if is_mojibake(text):
        status = "manual_review"
        reasons.append("mojibake_suspected")

    if not reasons:
        reasons.append(name_reason if status == "yes" else "none")

    return {
        "file": file_path.as_posix(),
        "slug": slug,
        "link_count": str(link_count),
        "has_products_frontmatter": str(has_products).lower(),
        "status": status,
        "reason": "; ".join(reasons),
        "suggested_product_name": suggested_name,
        "checked_at": checked_at,
    }


def build_report() -> list[dict[str, str]]:
    rows = [row for row in read_csv(MIGRATION_REPORT) if row.get("candidate_status") == "candidate"]
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        path = resolve_path(row["file"])
        if path.name in EXCLUDE_FILES:
            continue
        grouped[path.as_posix()].append(row)

    checked_at = datetime.now().isoformat(timespec="seconds")
    results: list[dict[str, str]] = []
    for file_name, file_rows in sorted(grouped.items()):
        path = Path(file_name)
        if not path.exists():
            results.append(
                {
                    "file": path.as_posix(),
                    "slug": file_rows[0].get("slug", path.stem),
                    "link_count": str(len(file_rows)),
                    "has_products_frontmatter": "unknown",
                    "status": "manual_review",
                    "reason": "file_not_found",
                    "suggested_product_name": "",
                    "checked_at": checked_at,
                }
            )
            continue
        results.append(evaluate_file(path, file_rows, checked_at))
    return results


def main() -> int:
    rows = build_report()
    write_csv(rows)
    write_markdown(rows)
    counts = count_statuses(rows)
    print(f"checked={len(rows)}")
    print(f"yes={counts['yes']}")
    print(f"manual_review={counts['manual_review']}")
    print(f"skipped={counts['skipped']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
