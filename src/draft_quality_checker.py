from __future__ import annotations

import csv
import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
DRAFTS_DIR = OUTPUT_DIR / "drafts"

DEFAULT_QUEUE_ID = "q000003"

ARTICLE_QUEUE_CSV = DATA_DIR / "article_queue.csv"
BODY_PROMPT_QUEUE_CSV = OUTPUT_DIR / "body_prompt_queue.csv"
REPORT_CSV = OUTPUT_DIR / "draft_quality_report.csv"
REPORT_MD = OUTPUT_DIR / "draft_quality_report.md"

OUTPUT_COLUMNS = [
    "draft_id",
    "queue_id",
    "quality_score",
    "decision",
    "failed_checks",
    "warnings",
    "checked_at",
]

BANNED_TERMS = [
    "\u4f7f\u3063\u3066\u307f\u305f",
    "\u672c\u97f3\u30ec\u30d3\u30e5\u30fc",
    "\u5b9f\u6a5f\u30ec\u30d3\u30e5\u30fc",
    "\u7d76\u5bfe",
    "\u5fc5\u305a",
    "\u6700\u5b89",
    "\u3069\u3053\u3067\u3082\u5b89\u5b9a",
]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames or [], list(reader)


def write_reports(row: dict[str, str], details: list[str]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with REPORT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerow(row)

    lines = [
        "# Draft Quality Report",
        "",
        f"draft_id: {row['draft_id']}",
        f"queue_id: {row['queue_id']}",
        f"quality_score: {row['quality_score']}",
        f"decision: {row['decision']}",
        f"failed_checks: {row['failed_checks'] or 'none'}",
        f"warnings: {row['warnings'] or 'none'}",
        f"checked_at: {row['checked_at']}",
        "",
        "## Details",
    ]
    if details:
        lines.extend([f"- {item}" for item in details])
    else:
        lines.append("- none")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def error_report(message: str, queue_id: str) -> int:
    checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = {
        "draft_id": f"{queue_id}_draft",
        "queue_id": queue_id,
        "quality_score": "0",
        "decision": "fail",
        "failed_checks": "error",
        "warnings": message,
        "checked_at": checked_at,
    }
    write_reports(row, [message])
    print(f"error: {message}")
    return 1


def get_row(rows: list[dict[str, str]], queue_id: str) -> dict[str, str] | None:
    for row in rows:
        if (row.get("queue_id") or "").strip() == queue_id:
            return row
    return None


def has_heading(text: str, level: int) -> bool:
    prefix = "#" * level + " "
    return any(line.strip().startswith(prefix) for line in text.splitlines())


def count_h1(text: str) -> int:
    return sum(1 for line in text.splitlines() if re.match(r"^#(?!#)\s+", line.strip()))


def contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def find_banned_terms(text: str) -> list[str]:
    return [term for term in BANNED_TERMS if term in text]


def url_bare_pastes(text: str) -> list[str]:
    return re.findall(r"https?://[^\s)>'\"]+", text)


def check_quality(text: str, target_keyword: str) -> tuple[int, str, list[str], list[str], list[str]]:
    failed: list[str] = []
    warnings: list[str] = []
    details: list[str] = []

    h1_count = count_h1(text)
    if h1_count != 1:
        failed.append("h1_count")
        details.append(f"H1 count is {h1_count}; expected exactly 1")
    else:
        details.append("H1 count ok")

    if not has_heading(text, 2):
        warnings.append("missing_h2")
        details.append("H2 heading missing")
    else:
        details.append("H2 exists")

    soft_checks = [
        ("meta_description", ["\u30e1\u30bf\u30c7\u30a3\u30b9\u30af\u30ea\u30d7\u30b7\u30e7\u30f3", "meta description", "description"]),
        ("faq", ["FAQ", "\u3088\u304f\u3042\u308b\u8cea\u554f"]),
        ("summary", ["\u307e\u3068\u3081"]),
        ("buy_for", ["\u8cb7\u3046\u3079\u304d\u4eba", "\u8cb7\u3046\u3079\u304d"]),
        ("not_buy_for", ["\u8cb7\u308f\u306a\u3044\u65b9\u304c\u3044\u3044\u4eba", "\u8cb7\u308f\u306a\u3044"]),
        ("demerits_or_notes", ["\u30c7\u30e1\u30ea\u30c3\u30c8", "\u6ce8\u610f\u70b9", "\u6ce8\u610f"]),
        ("cta_candidates", ["CTA", "\u633f\u5165\u5019\u88dc", "\u30ea\u30f3\u30af\u5019\u88dc"]),
        ("rel_sponsored_notice", ['rel="sponsored nofollow"', "rel='sponsored nofollow'"]),
        ("target_keyword", [target_keyword]),
    ]

    for name, terms in soft_checks:
        if contains_any(text, terms):
            details.append(f"{name} ok")
        else:
            warnings.append(name)
            details.append(f"{name} missing")

    if contains_any(text, ["PR", "\u5e83\u544a", "\u30a2\u30d5\u30a3\u30ea\u30a8\u30a4\u30c8"]):
        details.append("pr_ad_disclosure ok")
    else:
        failed.append("missing_pr_ad_disclosure")
        details.append("PR/ad disclosure missing")

    banned = find_banned_terms(text)
    if banned:
        failed.append("banned_terms:" + "/".join(banned))
        details.append("banned terms found: " + "/".join(banned))
    else:
        details.append("banned terms ok")

    urls = url_bare_pastes(text)
    if urls:
        failed.append("bare_urls:" + "/".join(urls[:5]))
        details.append("bare URLs found: " + "/".join(urls[:5]))
    else:
        details.append("bare URL check ok")

    score = 100
    score -= len(failed) * 25
    score -= len(warnings) * 5
    score = max(0, min(100, score))

    hard_fail = any(
        item.startswith("h1_count")
        or item.startswith("missing_pr_ad_disclosure")
        or item.startswith("banned_terms")
        or item.startswith("bare_urls")
        for item in failed
    )
    if hard_fail:
        decision = "fail"
    elif warnings:
        decision = "needs_fix"
    else:
        decision = "pass"

    return score, decision, failed, warnings, details


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a saved draft Markdown file before article registration.")
    parser.add_argument("--queue-id", default=DEFAULT_QUEUE_ID, help=f"Queue ID to check. Default: {DEFAULT_QUEUE_ID}")
    args = parser.parse_args()
    queue_id = args.queue_id.strip()
    draft_path = DRAFTS_DIR / f"{queue_id}_draft.md"

    queue_columns, queue_rows = read_csv(BODY_PROMPT_QUEUE_CSV)
    if not queue_rows:
        return error_report("output/body_prompt_queue.csv is missing or empty", queue_id)
    if not {"queue_id", "next_action"}.issubset(set(queue_columns)):
        return error_report("output/body_prompt_queue.csv is missing required columns", queue_id)

    queue_row = get_row(queue_rows, queue_id)
    if queue_row is None:
        return error_report(f"{queue_id} not found in output/body_prompt_queue.csv", queue_id)
    if (queue_row.get("next_action") or "").strip() != "send_to_gpt":
        return error_report(f"{queue_id} next_action is not send_to_gpt", queue_id)

    article_columns, article_rows = read_csv(ARTICLE_QUEUE_CSV)
    article_row = get_row(article_rows, queue_id) if article_rows else None
    if article_row is None:
        return error_report(f"{queue_id} not found in data/article_queue.csv", queue_id)
    target_keyword = (article_row.get("keyword") or "").strip()
    if not target_keyword:
        return error_report(f"{queue_id} keyword is empty in data/article_queue.csv", queue_id)

    if not draft_path.exists():
        return error_report(f"draft not found: {draft_path.relative_to(ROOT).as_posix()}", queue_id)

    text = draft_path.read_text(encoding="utf-8")
    score, decision, failed, warnings, details = check_quality(text, target_keyword)
    checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = {
        "draft_id": f"{queue_id}_draft",
        "queue_id": queue_id,
        "quality_score": str(score),
        "decision": decision,
        "failed_checks": ";".join(failed),
        "warnings": ";".join(warnings),
        "checked_at": checked_at,
    }
    write_reports(row, details)
    print(f"{queue_id}\tquality_score={score}\tdecision={decision}")
    print(f"failed_checks={row['failed_checks'] or 'none'}")
    print(f"warnings={row['warnings'] or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
