from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "output" / "astro_candidate_validation_report.md"
MOJIBAKE_MARKERS = ["\ufffd", "\u00e3", "\u7e3a", "\u8b41", "\u7e67"]
ASSERTIVE_TERMS = ["\u6700\u5b89", "\u5fc5\u305a", "\u7d76\u5bfe", "\u5728\u5eab\u3042\u308a", "\u30ad\u30e3\u30f3\u30da\u30fc\u30f3\u4e2d", "\u30e9\u30f3\u30ad\u30f3\u30b01\u4f4d", "\u304a\u3059\u3059\u30811\u4f4d", "\u672c\u97f3\u30ec\u30d3\u30e5\u30fc", "\u5b9f\u6a5f\u30ec\u30d3\u30e5\u30fc"]
AFFILIATE_URL_MARKERS = ["tag=", "affiliate", "afl", "rakuten", "amazon", "a8.net", "valuecommerce", "\u3082\u3057\u3082"]
MIN_BODY_CHARS = 800
EDITING_NOTE_MARKERS = [
    "\u0043\u0054\u0041\u633f\u5165\u5019\u88dc",
    "\u78ba\u8a8d\u5f8c\u306b\u633f\u5165",
    "\u5b9f\u0055\u0052\u004c\u306f\u516c\u958b\u524d\u306b\u78ba\u8a8d",
    "\u30e1\u30bf\u30c7\u30a3\u30b9\u30af\u30ea\u30d7\u30b7\u30e7\u30f3\u6848",
    "sourceQueueId:",
    "p_test_",
    "draft: true",
    "draft: false",
    "\u3053\u3053\u306bFS040W",
    "\u3053\u3053\u306b\u30ea\u30f3\u30af",
    "\u3053\u3053\u306b\u8cfc\u5165",
    "\u3053\u3053\u306bCTA",
    "\u3053\u3053\u306b\u633f\u5165",
]
BODY_PR_DISCLOSURE_MARKERS = [
    "\u203b\u3053\u306e\u8a18\u4e8b\u306b\u306f\u5e83\u544a\u30fbPR\u3092\u542b\u307f\u307e\u3059",
    "\u203b\u3053\u306e\u8a18\u4e8b\u306b\u306f\u5e83\u544a\u30ea\u30f3\u30af\u3092\u542b\u307f\u307e\u3059",
    "\u3053\u306e\u8a18\u4e8b\u306b\u306f\u5e83\u544a\u30fbPR\u3092\u542b\u3080\u53ef\u80fd\u6027\u304c\u3042\u308a\u307e\u3059",
]


class ValidationReadError(Exception):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_utf8(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationReadError(f"file is not valid UTF-8: {exc}") from exc


def split_frontmatter(text: str) -> tuple[str | None, str, str | None]:
    normalized = text.lstrip("\ufeff")
    if not normalized.startswith("---\n"):
        return None, normalized, "frontmatter_start_missing"
    end = normalized.find("\n---", 4)
    if end == -1:
        return None, normalized, "frontmatter_end_missing"
    frontmatter = normalized[4:end].strip("\n")
    body = normalized[end + len("\n---") :].lstrip("\n")
    return frontmatter, body, None


def clean_yaml_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def parse_frontmatter(frontmatter: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    lines = frontmatter.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if ":" not in line or line.startswith((" ", "\t")):
            i += 1
            continue

        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if not value:
            items: list[str] = []
            j = i + 1
            while j < len(lines) and lines[j].startswith((" ", "\t")):
                item = lines[j].strip()
                if item.startswith("-"):
                    items.append(clean_yaml_value(item[1:].strip()))
                j += 1
            data[key] = items
            i = j
            continue

        data[key] = clean_yaml_value(value)
        i += 1
    return data


def markdown_headings(body: str) -> list[tuple[int, str]]:
    headings: list[tuple[int, str]] = []
    in_code = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code = not in_code
            continue
        if in_code:
            continue
        match = re.match(r"^(#{1,6})\s*(.*?)\s*$", line)
        if match:
            headings.append((len(match.group(1)), match.group(2).strip()))
    return headings


def bare_urls(text: str) -> list[str]:
    urls = re.findall(r"https?://[^\s)>'\"]+", text)
    linked = set(re.findall(r"\[[^\]]*\]\((https?://[^\s)>'\"]+)\)", text))
    return [url for url in urls if url not in linked]


def visible_body_length(body: str) -> int:
    text = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    text = re.sub(r"~~~.*?~~~", "", text, flags=re.DOTALL)
    text = re.sub(r"[#>*_`|\-\[\]()]", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\s+", "", text)
    return len(text)


def strip_markdown_marks(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[`*_>#|-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def comparable_text(text: str) -> str:
    return strip_markdown_marks(text).casefold()


def has_leading_duplicate_title(body: str, title: str, max_lines: int = 8) -> bool:
    if not title.strip():
        return False
    target = comparable_text(title)
    checked = 0
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        checked += 1
        if checked > max_lines:
            return False
        if stripped.startswith(("#", "```", "~~~")):
            continue
        return comparable_text(stripped) == target
    return False


def has_leading_body_pr_disclosure(body: str, max_lines: int = 10) -> bool:
    checked = 0
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        checked += 1
        if checked > max_lines or stripped.startswith("#"):
            return False
        plain = strip_markdown_marks(stripped)
        if any(marker in plain for marker in BODY_PR_DISCLOSURE_MARKERS):
            return True
    return False


def text_hits(text: str, markers: list[str]) -> list[str]:
    return sorted({marker for marker in markers if marker in text})


def has_pr_notice(body: str) -> bool:
    return any(term in body for term in ["PR", "\u5e83\u544a", "\u30a2\u30d5\u30a3\u30ea\u30a8\u30a4\u30c8", "\u5e83\u544a\u30ea\u30f3\u30af"])


def mojibake_hits(text: str) -> list[str]:
    return [marker for marker in MOJIBAKE_MARKERS if marker in text]


def assertive_term_hits(text: str) -> list[str]:
    return [term for term in ASSERTIVE_TERMS if term in text]


def affiliate_bare_urls(urls: list[str]) -> list[str]:
    results: list[str] = []
    for url in urls:
        lower = url.lower()
        if any(marker in lower for marker in AFFILIATE_URL_MARKERS):
            results.append(url)
    return results


def validate_file(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    frontmatter_summary: dict[str, Any] = {}
    heading_summary: dict[str, Any] = {}

    try:
        text = read_utf8(path)
    except ValidationReadError as exc:
        return build_result(path, "fail", [str(exc)], warnings, frontmatter_summary, heading_summary)

    frontmatter, body, frontmatter_error = split_frontmatter(text)
    if frontmatter_error:
        errors.append(frontmatter_error)
        return build_result(path, "fail", errors, warnings, frontmatter_summary, heading_summary)

    assert frontmatter is not None
    data = parse_frontmatter(frontmatter)
    headings = markdown_headings(body)
    h1 = [text for level, text in headings if level == 1]
    h2 = [text for level, text in headings if level == 2]
    h3 = [text for level, text in headings if level == 3]
    empty_headings = [level for level, text in headings if not text]
    urls = bare_urls(body)
    body_chars = visible_body_length(body)
    markers = mojibake_hits(text)
    assertive_hits = assertive_term_hits(body)
    affiliate_urls = affiliate_bare_urls(urls)
    editing_notes = text_hits(body, EDITING_NOTE_MARKERS)

    frontmatter_summary = {
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "date": data.get("date", ""),
        "categories": data.get("categories", []),
        "tags": data.get("tags", []),
        "draft": data.get("draft", ""),
        "authors": data.get("authors", []),
    }
    heading_summary = {
        "h1_count": len(h1),
        "h2_count": len(h2),
        "h3_count": len(h3),
        "empty_heading_count": len(empty_headings),
        "body_chars": body_chars,
    }

    if not str(data.get("title", "")).strip():
        errors.append("frontmatter title is empty")
    if not str(data.get("description", "")).strip():
        errors.append("frontmatter description is empty")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(data.get("date", "")).strip().strip('"')):
        errors.append("frontmatter date is not YYYY-MM-DD")

    categories = data.get("categories")
    if not isinstance(categories, list) or not [item for item in categories if str(item).strip()]:
        errors.append("frontmatter categories must be a non-empty array")
    elif any(str(item).strip().casefold() == "others" for item in categories):
        warnings.append("frontmatter categories contains others; choose a more specific category before publishing")

    tags = data.get("tags")
    if not isinstance(tags, list) or not [item for item in tags if str(item).strip()]:
        errors.append("frontmatter tags must be a non-empty array")

    if str(data.get("draft", "")).strip().lower() != "true":
        errors.append("frontmatter draft must be true")

    authors = data.get("authors")
    if not isinstance(authors, list):
        errors.append("frontmatter authors must be an array")

    if "pubDate" in data:
        errors.append("frontmatter pubDate must not be used")
    if "category" in data:
        errors.append("frontmatter category must not be used; use categories")

    if h1:
        errors.append(f"body must not contain H1 headings: {len(h1)} found")
    if has_leading_duplicate_title(body, str(data.get("title", ""))):
        errors.append("body starts with a duplicate plain title")
    if has_leading_body_pr_disclosure(body):
        errors.append("body starts with a duplicate PR disclosure; template disclosure should cover it")
    if editing_notes:
        errors.append("editing memo markers found: " + ", ".join(editing_notes))
    if not h2:
        errors.append("body must contain at least one H2 heading")
    if not headings:
        errors.append("body has no Markdown headings")
    if empty_headings:
        errors.append(f"body has empty headings: {len(empty_headings)} found")
    if urls:
        errors.append("body has bare URLs: " + ", ".join(urls[:5]))
    if markers:
        errors.append("mojibake markers found: " + ", ".join(markers))

    if body_chars < MIN_BODY_CHARS:
        warnings.append(f"body may be too short: {body_chars} visible chars")
    if not has_pr_notice(body):
        warnings.append("PR notice not found in body; template AffiliateDisclosure may cover this")
    if assertive_hits:
        warnings.append("assertive monetization terms found: " + ", ".join(assertive_hits))
    if affiliate_urls:
        warnings.append("bare affiliate-like URLs found: " + ", ".join(affiliate_urls[:5]))

    result = "fail" if errors else ("warning" if warnings else "pass")
    return build_result(path, result, errors, warnings, frontmatter_summary, heading_summary)


def build_result(
    path: Path,
    result: str,
    errors: list[str],
    warnings: list[str],
    frontmatter_summary: dict[str, Any],
    heading_summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "executed_at": now_iso(),
        "file": str(path),
        "result": result,
        "errors": errors,
        "warnings": warnings,
        "frontmatter_summary": frontmatter_summary,
        "heading_summary": heading_summary,
    }


def write_report(result: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Astro Candidate Validation Report",
        "",
        f"executed_at: {result['executed_at']}",
        f"file: {result['file']}",
        f"result: {result['result']}",
        "",
        "## Errors",
    ]
    lines.extend([f"- {error}" for error in result["errors"]] if result["errors"] else ["- none"])
    lines.extend(["", "## Warnings"])
    lines.extend([f"- {warning}" for warning in result["warnings"]] if result["warnings"] else ["- none"])

    lines.extend(["", "## Frontmatter Summary"])
    summary = result.get("frontmatter_summary") or {}
    if summary:
        for key, value in summary.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- none")

    lines.extend(["", "## Heading Summary"])
    heading = result.get("heading_summary") or {}
    if heading:
        for key, value in heading.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Next Human Checks",
            "",
            "- frontmatter\u306etitle\u3001description\u3001categories\u3001tags\u304c\u8a18\u4e8b\u610f\u56f3\u3068\u5408\u3063\u3066\u3044\u308b\u304b\u78ba\u8a8d\u3059\u308b",
            "- \u4fa1\u683c\u3001\u5728\u5eab\u3001\u30ad\u30e3\u30f3\u30da\u30fc\u30f3\u3001\u30e9\u30f3\u30ad\u30f3\u30b0\u3001\u30ec\u30d3\u30e5\u30fc\u8868\u73fe\u304c\u4e8b\u5b9f\u306b\u57fa\u3065\u3044\u3066\u3044\u308b\u304b\u78ba\u8a8d\u3059\u308b",
            "- PR\u8868\u8a18\u304c\u30c6\u30f3\u30d7\u30ec\u30fc\u30c8\u5074\u3068\u672c\u6587\u5074\u3067\u904e\u4e0d\u8db3\u306a\u3044\u304b\u78ba\u8a8d\u3059\u308b",
            "- result\u304cpass\u307e\u305f\u306f\u8a31\u5bb9\u3067\u304d\u308bwarning\u306a\u3089\u3001\u5225\u624b\u9806\u3067src/content/posts\u3078\u30b3\u30d4\u30fc\u3057\u3066npm run check / npm run build\u3092\u5b9f\u884c\u3059\u308b",
            "Note: this validator does not modify the candidate and does not copy it to src/content/posts.",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate an Astro article candidate before copying it to src/content/posts.")
    parser.add_argument("--file", required=True, help="Candidate markdown file, e.g. output/astro_articles/q000003.md")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    target = Path(args.file)
    path = target if target.is_absolute() else ROOT / target
    if not path.exists():
        result = build_result(path, "fail", ["target file does not exist"], [], {}, {})
        write_report(result)
        print("fail: target file does not exist", file=sys.stderr)
        return 1
    if not path.is_file():
        result = build_result(path, "fail", ["target path is not a file"], [], {}, {})
        write_report(result)
        print("fail: target path is not a file", file=sys.stderr)
        return 1

    result = validate_file(path)
    write_report(result)
    print(f"{result['result']}: {path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path}")
    return 1 if result["result"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
