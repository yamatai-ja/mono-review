from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = ROOT / "src" / "content" / "posts"
OUTPUT_DIR = ROOT / "output"
CSV_REPORT = OUTPUT_DIR / "markdown_post_audit_report.csv"
MD_REPORT = OUTPUT_DIR / "markdown_post_audit_report.md"

CSV_COLUMNS = [
    "file",
    "slug",
    "title",
    "draft",
    "decision",
    "failed_checks",
    "warnings",
    "checked_at",
]

BANNED_TERMS = [
    "使ってみた",
    "本音レビュー",
    "実機レビュー",
    "絶対",
    "必ず",
    "最安",
    "どこでも安定",
]

URL_RE = re.compile(r"https?://")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\((https?://[^)\s]+)\)")
AFFILIATE_URL_HINTS = [
    "tag=",
    "amazon.co.jp",
    "amzn.to",
    "rakuten.co.jp",
    "hb.afl.rakuten",
    "a8.net",
    "moshimo.com",
    "valuecommerce",
    "felmat",
    "accesstrade",
]
INTERNAL_URL_HINTS = [
    "127.0.0.1",
    "localhost",
    "monoslog.com",
]


def split_frontmatter(text: str) -> tuple[dict[str, Any] | None, str, list[str]]:
    warnings: list[str] = []
    if not text.startswith("---"):
        return None, text, warnings

    lines = text.splitlines()
    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break

    if end_index is None:
        return None, text, ["frontmatter_not_closed"]

    frontmatter_text = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :])
    return parse_simple_yaml(frontmatter_text), body, warnings


def parse_simple_yaml(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        if raw_line.startswith((" ", "\t")):
            if current_key and raw_line.strip().startswith("- "):
                data.setdefault(current_key, [])
                if isinstance(data[current_key], list):
                    data[current_key].append(clean_scalar(raw_line.strip()[2:]))
            continue

        if ":" not in raw_line:
            continue

        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_key = key

        if value == "":
            data[key] = []
        elif value.startswith("[") and value.endswith("]"):
            data[key] = parse_inline_list(value)
        else:
            data[key] = clean_scalar(value)

    return data


def parse_inline_list(value: str) -> list[str]:
    inner = value[1:-1].strip()
    if not inner:
        return []
    return [clean_scalar(item.strip()) for item in inner.split(",")]


def clean_scalar(value: str) -> str | bool:
    cleaned = value.strip()
    if (
        (cleaned.startswith('"') and cleaned.endswith('"'))
        or (cleaned.startswith("'") and cleaned.endswith("'"))
    ):
        cleaned = cleaned[1:-1]
    if cleaned.lower() == "true":
        return True
    if cleaned.lower() == "false":
        return False
    return cleaned


def as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return default


def has_value(data: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            if any(str(item).strip() for item in value):
                return True
        elif value not in (None, "", []):
            return True
    return False


def count_body_headings(body: str) -> tuple[int, int]:
    h1_count = 0
    h2_count = 0
    in_code = False

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if re.match(r"^#\s+", stripped):
            h1_count += 1
        elif re.match(r"^##\s+", stripped):
            h2_count += 1

    return h1_count, h2_count


def classify_urls(text: str) -> dict[str, list[str]]:
    normalized = text.replace('rel="sponsored nofollow"', "")
    markdown_urls = MARKDOWN_LINK_RE.findall(normalized)
    text_without_markdown_links = MARKDOWN_LINK_RE.sub("", normalized)
    naked_urls = URL_RE.findall(text_without_markdown_links)

    affiliate_links: list[str] = []
    external_links: list[str] = []
    internal_links: list[str] = []

    for url in markdown_urls:
        lowered = url.lower()
        if any(hint in lowered for hint in AFFILIATE_URL_HINTS):
            affiliate_links.append(url)
        elif any(hint in lowered for hint in INTERNAL_URL_HINTS) or lowered.startswith("/"):
            internal_links.append(url)
        else:
            external_links.append(url)

    return {
        "naked_urls": naked_urls,
        "affiliate_markdown_links": affiliate_links,
        "external_markdown_links": external_links,
        "internal_links": internal_links,
    }


def has_pr_disclosure(text: str) -> bool:
    patterns = ["PR", "広告", "アフィリエイト", "affiliate", "Affiliate"]
    return any(pattern in text for pattern in patterns)


def slugify_filename(path: Path) -> str:
    return path.stem


def audit_post(path: Path, checked_at: str) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    frontmatter, body, parser_warnings = split_frontmatter(text)

    failed: list[str] = []
    warnings: list[str] = list(parser_warnings)

    if frontmatter is None:
        return {
            "file": path.as_posix(),
            "slug": slugify_filename(path),
            "title": "",
            "draft": "",
            "decision": "blocked",
            "failed_checks": "frontmatter_invalid",
            "warnings": join_items(warnings),
            "checked_at": checked_at,
        }

    filename_slug = slugify_filename(path)
    slug = str(frontmatter.get("slug") or filename_slug)
    title = str(frontmatter.get("title") or "")
    draft = as_bool(frontmatter.get("draft"), default=False)

    if not has_value(frontmatter, "title"):
        failed.append("missing_title")
    if not has_value(frontmatter, "description"):
        failed.append("missing_description")
    if not has_value(frontmatter, "pubDate", "date"):
        failed.append("missing_pubDate_or_date")
    if "draft" not in frontmatter:
        warnings.append("missing_draft_assumed_false")
    if not has_value(frontmatter, "category", "categories"):
        failed.append("missing_category_or_categories")
    if not has_value(frontmatter, "tags"):
        failed.append("missing_tags")
    if "slug" not in frontmatter:
        warnings.append("missing_slug_using_filename")
    elif slug != filename_slug:
        warnings.append(f"slug_filename_mismatch:{slug}!={filename_slug}")

    body_h1_count, h2_count = count_body_headings(body)
    if body_h1_count >= 2:
        failed.append(f"body_h1_count_invalid:{body_h1_count}")
    elif body_h1_count == 1:
        warnings.append("body_h1_present:prefer_frontmatter_title_plus_h2_body")
    if h2_count == 0:
        failed.append("missing_h2")

    description = str(frontmatter.get("description") or "")
    text_for_terms = f"{description}\n{body}"
    banned_hits = [term for term in BANNED_TERMS if term in text_for_terms]
    if banned_hits:
        failed.append("banned_terms:" + "|".join(banned_hits))

    url_info = classify_urls(text_for_terms)
    pr_found = has_pr_disclosure(text_for_terms)

    if draft:
        if not pr_found:
            warnings.append("draft_missing_pr_disclosure")
        append_url_findings(warnings, url_info, draft=True)
    else:
        if not pr_found:
            failed.append("missing_pr_disclosure")
        if url_info["naked_urls"]:
            failed.append(f"naked_url:{len(url_info['naked_urls'])}")
        append_url_findings(warnings, url_info, draft=False)

    decision = decide(draft=draft, failed=failed, warnings=warnings)

    return {
        "file": path.as_posix(),
        "slug": slug,
        "title": title,
        "draft": str(draft).lower(),
        "decision": decision,
        "failed_checks": join_items(failed),
        "warnings": join_items(warnings),
        "checked_at": checked_at,
    }


def append_url_findings(
    warnings: list[str],
    url_info: dict[str, list[str]],
    *,
    draft: bool,
) -> None:
    if draft and url_info["naked_urls"]:
        warnings.append(f"draft_naked_url:{len(url_info['naked_urls'])}")
    if url_info["affiliate_markdown_links"]:
        warnings.append(
            f"affiliate_markdown_link_needs_product_card:{len(url_info['affiliate_markdown_links'])}"
        )
    if url_info["external_markdown_links"]:
        warnings.append(f"external_markdown_link:{len(url_info['external_markdown_links'])}")
    if url_info["internal_links"]:
        warnings.append(f"internal_link:{len(url_info['internal_links'])}")


def decide(*, draft: bool, failed: list[str], warnings: list[str]) -> str:
    if failed:
        if draft and failed == ["missing_pr_disclosure"]:
            return "needs_fix"
        return "blocked"
    if warnings:
        return "needs_fix"
    return "draft_ok" if draft else "public_ok"


def join_items(items: list[str]) -> str:
    return "; ".join(items) if items else "none"


def write_csv(rows: list[dict[str, str]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_REPORT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, str]]) -> None:
    public_count = sum(1 for row in rows if row["draft"] == "false")
    draft_count = sum(1 for row in rows if row["draft"] == "true")
    counts = {
        "public_ok": sum(1 for row in rows if row["decision"] == "public_ok"),
        "draft_ok": sum(1 for row in rows if row["decision"] == "draft_ok"),
        "needs_fix": sum(1 for row in rows if row["decision"] == "needs_fix"),
        "blocked": sum(1 for row in rows if row["decision"] == "blocked"),
    }

    lines = [
        "# Markdown Post Audit Report",
        "",
        f"- total: {len(rows)}",
        f"- public posts: {public_count}",
        f"- draft posts: {draft_count}",
        f"- public_ok: {counts['public_ok']}",
        f"- draft_ok: {counts['draft_ok']}",
        f"- needs_fix: {counts['needs_fix']}",
        f"- blocked: {counts['blocked']}",
        "",
        "## Results",
        "",
        "| file | draft | decision | failed_checks | warnings |",
        "| --- | --- | --- | --- | --- |",
    ]

    for row in rows:
        lines.append(
            "| {file} | {draft} | {decision} | {failed} | {warnings} |".format(
                file=Path(row["file"]).name,
                draft=row["draft"],
                decision=row["decision"],
                failed=escape_table(row["failed_checks"]),
                warnings=escape_table(row["warnings"]),
            )
        )

    MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def escape_table(value: str) -> str:
    return value.replace("|", "\\|")


def main() -> int:
    checked_at = datetime.now().isoformat(timespec="seconds")
    rows = [audit_post(path, checked_at) for path in sorted(POSTS_DIR.glob("*.md"))]
    write_csv(rows)
    write_markdown(rows)

    public_count = sum(1 for row in rows if row["draft"] == "false")
    draft_count = sum(1 for row in rows if row["draft"] == "true")
    print(f"checked={len(rows)}")
    print(f"public_posts={public_count}")
    print(f"draft_posts={draft_count}")
    print(f"public_ok={sum(1 for row in rows if row['decision'] == 'public_ok')}")
    print(f"draft_ok={sum(1 for row in rows if row['decision'] == 'draft_ok')}")
    print(f"needs_fix={sum(1 for row in rows if row['decision'] == 'needs_fix')}")
    print(f"blocked={sum(1 for row in rows if row['decision'] == 'blocked')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
