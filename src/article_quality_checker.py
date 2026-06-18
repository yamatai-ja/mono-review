from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = Path(__file__).resolve().parent / "article_profiles"
OUTPUT_DIR = ROOT / "output"
REPORT_CSV = OUTPUT_DIR / "article_quality_report.csv"
REPORT_MD = OUTPUT_DIR / "article_quality_report.md"

REPORT_FIELDS = [
    "slug",
    "article_type",
    "draft_file",
    "quality_score",
    "decision",
    "failed_checks",
    "warnings",
    "checked_at",
]


def load_simple_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"profile not found: {path}")

    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    last_key_at_indent: dict[int, tuple[Any, str]] = {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if line.startswith("- "):
            value = parse_scalar(line[2:].strip())
            if not isinstance(parent, list):
                container, key = last_key_at_indent[indent]
                new_list: list[Any] = []
                container[key] = new_list
                stack.append((indent - 1, new_list))
                parent = new_list
            parent.append(value)
            continue

        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if raw_value:
            parent[key] = parse_scalar(raw_value)
            last_key_at_indent[indent + 2] = (parent, key)
            continue

        child: dict[str, Any] = {}
        parent[key] = child
        last_key_at_indent[indent + 2] = (parent, key)
        stack.append((indent, child))

    return root


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def count_heading(markdown: str, level: int) -> int:
    marker = "#" * level + " "
    return sum(1 for line in markdown.splitlines() if line.startswith(marker))


def find_terms(markdown: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term and term in markdown]


def bare_urls(markdown: str) -> list[str]:
    return re.findall(r"https?://[^\s)>'\"]+", markdown)


def split_frontmatter(markdown: str) -> tuple[str | None, str]:
    lines = markdown.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None, markdown

    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "".join(lines[1:index]), "".join(lines[index + 1 :])

    # Do not hide content from checks when the opening delimiter is malformed.
    return None, markdown


def frontmatter_has_value(frontmatter: str | None, key: str) -> bool:
    if frontmatter is None:
        return False

    match = re.search(rf"(?m)^{re.escape(key)}\s*:\s*(.*)$", frontmatter)
    if not match:
        return False

    value = match.group(1).strip()
    return bool(value and value not in {'""', "''"})


def check_article(markdown: str, profile: dict[str, Any]) -> tuple[int, str, list[str], list[str], list[str]]:
    failed: list[str] = []
    warnings: list[str] = []
    details: list[str] = []

    requirements = profile.get("requirements", {})
    hard_fail_terms = profile.get("hard_fail_terms", {})
    frontmatter, body = split_frontmatter(markdown)
    details.append("frontmatter separated" if frontmatter is not None else "frontmatter not present")

    h1_count = count_heading(body, 1)
    expected_h1 = int(requirements.get("h1_count", 0))
    if h1_count != expected_h1:
        failed.append(f"h1_count={h1_count}")
    details.append(f"h1_count={h1_count}")

    h2_count = count_heading(body, 2)
    min_h2 = int(requirements.get("min_h2_count", 0))
    if h2_count < min_h2:
        warnings.append(f"h2_count={h2_count}")
    details.append(f"h2_count={h2_count}")

    if requirements.get("require_faq") and "## FAQ" not in body:
        failed.append("missing_faq")
    else:
        details.append("faq ok")

    internal_terms = find_terms(body, list(hard_fail_terms.get("internal", [])))
    if internal_terms:
        failed.append("internal_terms:" + "/".join(internal_terms))
    else:
        details.append("internal terms ok")

    strong_cta_terms = find_terms(body, list(hard_fail_terms.get("strong_cta", [])))
    if strong_cta_terms:
        failed.append("strong_cta_terms:" + "/".join(strong_cta_terms))
    else:
        details.append("strong CTA terms ok")

    experience_terms = find_terms(body, list(hard_fail_terms.get("experience", [])))
    if experience_terms:
        failed.append("experience_terms:" + "/".join(experience_terms))
    else:
        details.append("experience terms ok")

    has_meta_description = frontmatter_has_value(frontmatter, "description") or "メタディスクリプション案" in body
    if requirements.get("require_meta_description") and not has_meta_description:
        warnings.append("missing_meta_description")
    else:
        source = "frontmatter" if frontmatter_has_value(frontmatter, "description") else "body"
        details.append(f"meta description ok ({source})")

    if requirements.get("require_summary") and "## まとめ" not in body:
        warnings.append("missing_summary")
    else:
        details.append("summary ok")

    if requirements.get("require_internal_link") and not re.search(r"\[[^\]]+\]\(/blog/[^)]+\)", body):
        warnings.append("missing_internal_link")
    else:
        details.append("internal link ok")

    urls = bare_urls(body)
    if urls:
        warnings.append("bare_urls:" + "/".join(urls[:5]))
    else:
        details.append("bare URL check ok")

    score_config = profile.get("score", {})
    score = int(score_config.get("initial", 100))
    score -= len(failed) * int(score_config.get("hard_fail_penalty", 25))
    score -= len(warnings) * int(score_config.get("warning_penalty", 5))
    score = max(0, min(100, score))

    threshold = int(score_config.get("pass_threshold", 95))
    if failed:
        decision = str(profile.get("needs_edit_decision", "needs_edit"))
    elif score >= threshold:
        decision = str(profile.get("ready_decision", "ready_for_astro_candidate"))
    else:
        decision = str(profile.get("needs_edit_decision", "needs_edit"))

    return score, decision, failed, warnings, details


def write_reports(row: dict[str, str], details: list[str]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with REPORT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerow(row)

    lines = [
        "# Article Quality Report",
        "",
        f"- slug: {row['slug']}",
        f"- article_type: {row['article_type']}",
        f"- draft_file: {row['draft_file']}",
        f"- quality_score: {row['quality_score']}",
        f"- decision: {row['decision']}",
        f"- failed_checks: {row['failed_checks'] or 'none'}",
        f"- warnings: {row['warnings'] or 'none'}",
        f"- checked_at: {row['checked_at']}",
        "",
        "## Details",
    ]
    lines.extend(f"- {detail}" for detail in details)
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check article body quality using article_type profiles.")
    parser.add_argument("--article-type", required=True, help="Article type profile name, e.g. problem_solution.")
    parser.add_argument("--draft-file", required=True, help="Draft Markdown file to check.")
    parser.add_argument("--slug", required=True, help="Candidate article slug.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    article_type = args.article_type.strip()
    draft_path = ROOT / args.draft_file
    if not draft_path.exists():
        raise SystemExit(f"draft file not found: {args.draft_file}")

    profile = load_simple_yaml(PROFILE_DIR / f"{article_type}.yaml")
    markdown = draft_path.read_text(encoding="utf-8")
    score, decision, failed, warnings, details = check_article(markdown, profile)
    checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    row = {
        "slug": args.slug.strip(),
        "article_type": article_type,
        "draft_file": args.draft_file,
        "quality_score": str(score),
        "decision": decision,
        "failed_checks": ";".join(failed),
        "warnings": ";".join(warnings),
        "checked_at": checked_at,
    }
    write_reports(row, details)

    print(f"quality_score={score}")
    print(f"decision={decision}")
    print(f"failed_checks={row['failed_checks'] or 'none'}")
    print(f"warnings={row['warnings'] or 'none'}")
    print(f"report={REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
