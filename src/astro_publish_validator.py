from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "output" / "astro_publish_validation_report.md"
MOJIBAKE_MARKERS = ["\ufffd", "\u00e3", "\u7e3a", "\u8b41", "\u7e67"]
EDITING_NOTE_MARKERS = [
    "CTA挿入候補",
    "リンク候補",
    "確認後に挿入",
    "実URLは公開前に確認",
    "メタディスクリプション案",
    "sourceQueueId:",
    "p_test_",
]
ASSERTIVE_TERMS = ["最安", "絶対", "必ず", "実機レビュー", "本音レビュー"]
COMMERCE_TERMS = ["価格", "在庫", "キャンペーン", "ランキング", "レビュー"]
PR_TERMS = ["PR", "広告", "アフィリエイト", "広告リンク"]
MIN_BODY_CHARS = 800
COMMERCE_TERM_WARNING_THRESHOLD = 12


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


def has_pr_notice(body: str) -> bool:
    return any(term in body for term in PR_TERMS)


def text_hits(text: str, markers: list[str]) -> list[str]:
    return [marker for marker in markers if marker in text]


def term_counts(text: str, terms: list[str]) -> dict[str, int]:
    return {term: text.count(term) for term in terms if text.count(term) > 0}


def p_test_hits(data: dict[str, Any], text: str) -> list[str]:
    hits: list[str] = []
    tags = data.get("tags")
    if isinstance(tags, list):
        hits.extend(str(tag) for tag in tags if "p_test_" in str(tag))
    if "p_test_" in text:
        hits.append("p_test_ in body or frontmatter")
    return sorted(set(hits))


def validate_file(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    frontmatter_summary: dict[str, Any] = {}
    heading_summary: dict[str, Any] = {}
    publish_readiness = "not_ready"

    try:
        text = read_utf8(path)
    except ValidationReadError as exc:
        return build_result(path, "fail", [str(exc)], warnings, frontmatter_summary, heading_summary, publish_readiness)

    frontmatter, body, frontmatter_error = split_frontmatter(text)
    if frontmatter_error:
        errors.append(frontmatter_error)
        return build_result(path, "fail", errors, warnings, frontmatter_summary, heading_summary, publish_readiness)

    assert frontmatter is not None
    data = parse_frontmatter(frontmatter)
    combined_text = frontmatter + "\n" + body
    headings = markdown_headings(body)
    h1 = [text for level, text in headings if level == 1]
    h2 = [text for level, text in headings if level == 2]
    h3 = [text for level, text in headings if level == 3]
    empty_headings = [level for level, text in headings if not text]
    urls = bare_urls(body)
    body_chars = visible_body_length(body)
    mojibake = text_hits(combined_text, MOJIBAKE_MARKERS)
    editing_notes = text_hits(combined_text, EDITING_NOTE_MARKERS)
    assertive_hits = text_hits(body, ASSERTIVE_TERMS)
    commerce_counts = term_counts(body, COMMERCE_TERMS)
    p_tests = p_test_hits(data, combined_text)

    frontmatter_summary = {
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "date": data.get("date", ""),
        "categories": data.get("categories", []),
        "tags": data.get("tags", []),
        "draft": data.get("draft", "not_specified"),
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

    tags = data.get("tags")
    if not isinstance(tags, list) or not [item for item in tags if str(item).strip()]:
        errors.append("frontmatter tags must be a non-empty array")

    authors = data.get("authors")
    if not isinstance(authors, list):
        errors.append("frontmatter authors must be an array")

    draft = str(data.get("draft", "")).strip().lower()
    if draft == "true":
        errors.append("frontmatter draft:true is not publish-ready")
    elif draft not in {"", "false"}:
        warnings.append(f"frontmatter draft has unexpected value: {data.get('draft')}")

    if "pubDate" in data:
        errors.append("frontmatter pubDate must not be used")
    if "category" in data:
        errors.append("frontmatter category must not be used; use categories")

    if "sourceQueueId" in combined_text:
        errors.append("sourceQueueId remains in article")
    if editing_notes:
        errors.append("editing memo markers found: " + ", ".join(editing_notes))
    if p_tests:
        errors.append("test product tag or marker found: " + ", ".join(p_tests))

    if h1:
        errors.append(f"body must not contain H1 headings: {len(h1)} found")
    if not h2:
        errors.append("body must contain at least one H2 heading")
    if empty_headings:
        errors.append(f"body has empty headings: {len(empty_headings)} found")
    if urls:
        errors.append("body has bare URLs: " + ", ".join(urls[:5]))
    if mojibake:
        errors.append("mojibake markers found: " + ", ".join(mojibake))

    if body_chars < MIN_BODY_CHARS:
        warnings.append(f"body may be too short: {body_chars} visible chars")
    if not has_pr_notice(body):
        warnings.append("PR notice not found in body; template AffiliateDisclosure may cover this")
    if assertive_hits:
        warnings.append("assertive or review-like terms found: " + ", ".join(assertive_hits))

    commerce_total = sum(commerce_counts.values())
    if commerce_total >= COMMERCE_TERM_WARNING_THRESHOLD:
        details = ", ".join(f"{term}:{count}" for term, count in commerce_counts.items())
        warnings.append(f"commerce terms appear often ({commerce_total}): {details}")

    result = "fail" if errors else ("warning" if warnings else "pass")
    publish_readiness = "ready" if result in {"pass", "warning"} else "not_ready"
    return build_result(path, result, errors, warnings, frontmatter_summary, heading_summary, publish_readiness)


def build_result(
    path: Path,
    result: str,
    errors: list[str],
    warnings: list[str],
    frontmatter_summary: dict[str, Any],
    heading_summary: dict[str, Any],
    publish_readiness: str,
) -> dict[str, Any]:
    return {
        "executed_at": now_iso(),
        "file": str(path),
        "result": result,
        "errors": errors,
        "warnings": warnings,
        "frontmatter_summary": frontmatter_summary,
        "heading_summary": heading_summary,
        "publish_readiness": publish_readiness,
    }


def write_report(result: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Astro Publish Validation Report",
        "",
        f"executed_at: {result['executed_at']}",
        f"file: {result['file']}",
        f"result: {result['result']}",
        f"publish_readiness: {result['publish_readiness']}",
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
            "## Publish Readiness",
            "",
            f"- {result['publish_readiness']}",
            "",
            "## Final Human Checks",
            "",
            "- 公開URLでタイトル、目次、表、FAQ、スマホ表示が崩れていないか確認する",
            "- PR表記がテンプレート側と本文側で過不足ないか確認する",
            "- 価格、在庫、キャンペーン、ランキング、レビュー表現が公開時点の事実に基づいているか確認する",
            "- affiliateリンクや商品リンクがある場合は、リンク先、nofollow/sponsored、表記を確認する",
            "- resultがpassまたは許容できるwarningなら、npm run check / npm run buildを実行してから公開判断する",
            "Note: this validator does not modify articles, draft state, or git state.",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate an Astro post as a publish-ready article.")
    parser.add_argument("--file", required=True, help="Published article markdown file, e.g. src/content/posts/example.md")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    target = Path(args.file)
    path = target if target.is_absolute() else ROOT / target
    if not path.exists():
        result = build_result(path, "fail", ["target file does not exist"], [], {}, {}, "not_ready")
        write_report(result)
        print("fail: target file does not exist", file=sys.stderr)
        return 1
    if not path.is_file():
        result = build_result(path, "fail", ["target path is not a file"], [], {}, {}, "not_ready")
        write_report(result)
        print("fail: target path is not a file", file=sys.stderr)
        return 1

    result = validate_file(path)
    write_report(result)
    display_path = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
    print(f"{result['result']}: {display_path}")
    return 1 if result["result"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
