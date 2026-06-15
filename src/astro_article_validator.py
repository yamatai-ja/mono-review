import argparse
import csv
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTICLE_DIR = ROOT / "output" / "astro_articles"
REPORT_CSV = ROOT / "output" / "astro_article_validation_report.csv"
REPORT_MD = ROOT / "output" / "astro_article_validation_report.md"

DEFAULT_QUEUE_ID = "q000003"
DEFAULT_FILES = {
    "q000003": "fs040w-povo-setting.md",
    "q000005": "motorola-edge-60.md",
}

REPORT_FIELDS = [
    "file",
    "slug",
    "sourceQueueId",
    "decision",
    "failed_checks",
    "warnings",
    "checked_at",
]

REQUIRED_FRONTMATTER = [
    "title",
    "description",
    "pubDate",
    "updatedDate",
    "draft",
    "category",
    "tags",
    "slug",
    "qualityScore",
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

STRONG_CTA_TERMS = [
    "今すぐ購入",
    "最安値はこちら",
    "いますぐ購入",
    "迷わず購入",
]


def checked_at():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_csv(row):
    REPORT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerow(row)


def write_markdown(row):
    lines = [
        "# Astro Article Validation Report",
        "",
        f"- file: {row['file']}",
        f"- slug: {row['slug']}",
        f"- sourceQueueId: {row['sourceQueueId']}",
        f"- decision: {row['decision']}",
        f"- failed_checks: {row['failed_checks']}",
        f"- warnings: {row['warnings']}",
        f"- checked_at: {row['checked_at']}",
        "",
        "Note: this tool validates the generated Astro markdown only. It does not modify or copy the article.",
    ]
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def split_frontmatter(text):
    if not text.startswith("---\n"):
        return None, text, "frontmatter_start_missing"
    end = text.find("\n---", 4)
    if end == -1:
        return None, text, "frontmatter_end_missing"
    frontmatter = text[4:end].strip("\n")
    body = text[end + len("\n---") :].lstrip("\n")
    return frontmatter, body, None


def parse_frontmatter(frontmatter):
    values = {}
    lines = frontmatter.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if ":" not in line or line.startswith(" "):
            i += 1
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if key == "tags" and not value:
            tags = []
            j = i + 1
            while j < len(lines) and lines[j].startswith(" "):
                item = lines[j].strip()
                if item.startswith("-"):
                    tags.append(clean_yaml_value(item[1:].strip()))
                j += 1
            values[key] = tags
            i = j
            continue
        values[key] = clean_yaml_value(value)
        i += 1
    return values


def clean_yaml_value(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def h1_count(body):
    return len(re.findall(r"^# (?!#).+", body, flags=re.MULTILINE))


def has_h2(body):
    return bool(re.search(r"^## (?!#).+", body, flags=re.MULTILINE))


def has_pr_notice(body):
    return any(term in body for term in ["PR", "広告", "アフィリエイト"])


def raw_urls(text):
    return re.findall(r"https?://[^\s)>'\"]+", text)


def quality_score(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def article_file_for(queue_id):
    return ARTICLE_DIR / DEFAULT_FILES.get(queue_id, f"{queue_id}.md")


def validate(queue_id):
    article_file = article_file_for(queue_id)
    failures = []
    warnings = []
    slug = ""
    source_queue_id = ""

    if not article_file.exists():
        failures.append("article_file_not_found")
        return result_row(article_file, "blocked", failures, warnings, slug, source_queue_id)

    try:
        text = article_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        failures.append("article_file_not_utf8")
        return result_row(article_file, "blocked", failures, warnings, slug, source_queue_id)

    frontmatter, body, frontmatter_error = split_frontmatter(text)
    if frontmatter_error:
        failures.append(frontmatter_error)
        return result_row(article_file, "blocked", failures, warnings, slug, source_queue_id)

    data = parse_frontmatter(frontmatter)
    slug = str(data.get("slug", ""))
    source_queue_id = str(data.get("sourceQueueId") or data.get("queue_id") or "")

    required = list(REQUIRED_FRONTMATTER)
    if queue_id == "q000003":
        required.append("sourceQueueId")
    else:
        required.append("queue_id")

    for key in required:
        value = data.get(key)
        if value in (None, "", []):
            failures.append(f"missing_frontmatter:{key}")

    if str(data.get("draft", "")).lower() != "true":
        failures.append("draft_not_true")
    expected_slug = "fs040w-povo-setting" if queue_id == "q000003" else "motorola-edge-60"
    if slug != expected_slug:
        failures.append("slug_mismatch")
    if source_queue_id != queue_id:
        failures.append("sourceQueueId_mismatch")

    score = quality_score(data.get("qualityScore"))
    if score is None:
        failures.append("qualityScore_not_numeric")
    elif score < 80:
        failures.append("qualityScore_below_80")

    tags = data.get("tags")
    if isinstance(tags, list) and not tags:
        failures.append("tags_empty")
    elif isinstance(tags, str) and not tags.strip():
        failures.append("tags_empty")

    count = h1_count(body)
    if count != 1:
        failures.append(f"h1_count={count}")
    if not has_h2(body):
        failures.append("h2_missing")
    if not has_pr_notice(body):
        failures.append("pr_notice_missing")

    urls = raw_urls(text)
    if queue_id == "q000005":
        source_url = data.get("source_url", "")
        unexpected_urls = [url for url in urls if url != source_url]
        if unexpected_urls:
            failures.append("raw_url_found")
    elif urls:
        failures.append("raw_url_found")

    banned = [term for term in BANNED_TERMS if term in text]
    if banned:
        failures.append("banned_terms:" + "/".join(banned))
    strong_cta = [term for term in STRONG_CTA_TERMS if term in text]
    if strong_cta:
        failures.append("strong_cta_terms:" + "/".join(strong_cta))

    if 'rel="sponsored nofollow"' not in text:
        warnings.append("rel_sponsored_nofollow_notice_missing")
    if data.get("url_status") == "needs_url_check":
        warnings.append("url_status_needs_url_check")
    if data.get("cta_policy") == "strong_cta_not_allowed_until_url_confirmed":
        warnings.append("strong_cta_not_allowed_until_url_confirmed")

    blocking = [
        item
        for item in failures
        if item.startswith("frontmatter_")
        or item.startswith("h1_count")
        or item == "draft_not_true"
        or item == "raw_url_found"
        or item == "article_file_not_found"
        or item == "article_file_not_utf8"
        or item.startswith("banned_terms")
        or item.startswith("strong_cta_terms")
    ]
    decision = "blocked" if blocking else ("needs_fix" if failures else "ready_to_copy")
    return result_row(article_file, decision, failures, warnings, slug, source_queue_id)


def result_row(article_file, decision, failures, warnings, slug, source_queue_id):
    return {
        "file": str(article_file.relative_to(ROOT)),
        "slug": slug or "unknown",
        "sourceQueueId": source_queue_id or "unknown",
        "decision": decision,
        "failed_checks": "; ".join(failures) if failures else "none",
        "warnings": "; ".join(warnings) if warnings else "none",
        "checked_at": checked_at(),
    }


def main():
    parser = argparse.ArgumentParser(description="Validate generated Astro Markdown before copying it to src/content/posts.")
    parser.add_argument("--queue-id", default=DEFAULT_QUEUE_ID, help=f"Queue ID to validate. Default: {DEFAULT_QUEUE_ID}")
    args = parser.parse_args()

    row = validate(args.queue_id.strip())
    write_csv(row)
    write_markdown(row)
    print(
        f"{row['file']}: {row['decision']} "
        f"failed={row['failed_checks']} warnings={row['warnings']}"
    )


if __name__ == "__main__":
    main()
