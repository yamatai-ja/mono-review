import argparse
import csv
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = ROOT / "src" / "content" / "posts"
PRODUCTS_CSV = ROOT / "data" / "products.csv"
OFFERS_CSV = ROOT / "data" / "offers.csv"
REPORT_CSV = ROOT / "output" / "publish_preflight_report.csv"
REPORT_MD = ROOT / "output" / "publish_preflight_report.md"

DEFAULT_QUEUE_ID = "q000003"
POST_FILES = {
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

INTERNAL_MEMO_TERMS = [
    "CTA挿入候補",
    "ProductCard",
    "frontmatter",
    "queue_id",
    "draft",
    "rel=",
    "HTMLで挿入",
    "URL確認後",
]


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(row):
    REPORT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerow(row)


def write_markdown(row):
    lines = [
        "# Publish Preflight Report",
        "",
        f"- file: {row['file']}",
        f"- slug: {row['slug']}",
        f"- sourceQueueId: {row['sourceQueueId']}",
        f"- decision: {row['decision']}",
        f"- failed_checks: {row['failed_checks']}",
        f"- warnings: {row['warnings']}",
        f"- checked_at: {row['checked_at']}",
        "",
        "Note: this tool checks publish readiness only. It does not change draft status or article content.",
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


def clean_yaml_value(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def parse_frontmatter(frontmatter):
    data = {}
    lines = frontmatter.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.startswith(" "):
            i += 1
            continue
        if ":" not in line:
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
            data[key] = tags
            i = j
            continue
        data[key] = clean_yaml_value(value)
        i += 1
    return data


def to_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def h1_count(body):
    return len(re.findall(r"^# (?!#).+", body, flags=re.MULTILINE))


def has_h2(body):
    return bool(re.search(r"^## (?!#).+", body, flags=re.MULTILINE))


def has_raw_url(text, allowed_urls=None):
    allowed_urls = set(allowed_urls or [])
    urls = re.findall(r"https?://[^\s)>'\"]+", text)
    return [url for url in urls if url not in allowed_urls]


def find_by_value(rows, key, value):
    for row in rows:
        if (row.get(key) or "").strip() == value:
            return row
    return None


def article_file_for(queue_id):
    return POSTS_DIR / POST_FILES.get(queue_id, f"{queue_id}.md")


def report_decision(failures, warnings):
    blocking = [
        item
        for item in failures
        if item in {
            "draft_not_true",
            "draft_already_false",
            "raw_url_found",
            "article_file_not_found",
            "article_file_not_utf8",
            "url_status_needs_url_check",
            "product_status_needs_url_check",
            "offer_status_needs_url_check",
        }
        or item.startswith("banned_term:")
        or item.startswith("strong_cta_term:")
        or item.startswith("internal_memo_term:")
        or item.startswith("frontmatter_")
        or item.startswith("missing_frontmatter:")
        or item.startswith("h1_present")
    ]
    if blocking:
        return "blocked_for_publish"
    non_blocking_warnings = {"draft_preview_noindex_confirmed_separately"}
    actionable_warnings = [warning for warning in warnings if warning not in non_blocking_warnings]
    if failures or actionable_warnings:
        return "needs_fix"
    return "ready_to_publish"


def validate(queue_id):
    article_file = article_file_for(queue_id)
    failures = []
    warnings = []
    slug = "unknown"
    source_queue_id = "unknown"

    if not article_file.exists():
        failures.append("article_file_not_found")
        return build_row(article_file, failures, warnings, slug, source_queue_id)

    try:
        text = article_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        failures.append("article_file_not_utf8")
        return build_row(article_file, failures, warnings, slug, source_queue_id)

    frontmatter, body, fm_error = split_frontmatter(text)
    if fm_error:
        failures.append(fm_error)
        return build_row(article_file, failures, warnings, slug, source_queue_id)

    data = parse_frontmatter(frontmatter)
    slug = str(data.get("slug") or "unknown")
    source_queue_id = str(data.get("sourceQueueId") or data.get("queue_id") or "unknown")

    required = ["title", "description", "category", "tags", "slug", "qualityScore"]
    required.append("sourceQueueId" if queue_id == "q000003" else "queue_id")
    for key in required:
        value = data.get(key)
        if value in (None, "", []):
            failures.append(f"missing_frontmatter:{key}")

    draft_value = str(data.get("draft", "")).lower()
    if draft_value == "false":
        failures.append("draft_already_false")
    elif draft_value != "true":
        failures.append("draft_not_true")

    if source_queue_id != queue_id:
        failures.append("sourceQueueId_mismatch")

    score = to_int(data.get("qualityScore"))
    if score is None:
        failures.append("qualityScore_not_numeric")
    elif score < 80:
        failures.append("qualityScore_below_80")

    count = h1_count(body)
    if count > 0:
        warnings.append(f"h1_present={count}")
    if not has_h2(body):
        failures.append("h2_missing")
    if not any(term in body for term in ["PR", "広告", "アフィリエイト"]):
        failures.append("pr_notice_missing")
    if "FAQ" not in body:
        failures.append("faq_missing")
    if "まとめ" not in body:
        failures.append("summary_missing")

    allowed_urls = [data.get("source_url", "")] if queue_id == "q000005" else []
    if has_raw_url(body, allowed_urls):
        failures.append("raw_url_found")

    for term in BANNED_TERMS:
        if term in body:
            failures.append(f"banned_term:{term}")
    for term in STRONG_CTA_TERMS:
        if term in body:
            failures.append(f"strong_cta_term:{term}")
    for term in INTERNAL_MEMO_TERMS:
        if term in body:
            failures.append(f"internal_memo_term:{term}")

    if queue_id == "q000005":
        product_id = data.get("product_id", "")
        offer_id = data.get("offer_id", "")
        if not product_id:
            failures.append("product_id_missing")
        if not offer_id:
            failures.append("offer_id_missing")
        if data.get("url_status") == "needs_url_check":
            failures.append("url_status_needs_url_check")
        if data.get("cta_policy") not in {
            "strong_cta_not_allowed_until_url_confirmed",
            "weak_cta_allowed_after_url_confirmed",
        }:
            failures.append("cta_policy_missing_or_invalid")

        product = find_by_value(read_csv(PRODUCTS_CSV), "product_id", product_id)
        offer = find_by_value(read_csv(OFFERS_CSV), "offer_id", offer_id)
        if not product:
            failures.append("product_not_found")
        elif (product.get("status") or "").strip() == "needs_url_check":
            failures.append("product_status_needs_url_check")
        if not offer:
            failures.append("offer_not_found")
        elif (offer.get("status") or "").strip() == "needs_url_check":
            failures.append("offer_status_needs_url_check")
        warnings.append("draft_preview_noindex_confirmed_separately")

    return build_row(article_file, failures, warnings, slug, source_queue_id)


def build_row(article_file, failures, warnings, slug, source_queue_id):
    return {
        "file": str(article_file.relative_to(ROOT)),
        "slug": slug,
        "sourceQueueId": source_queue_id,
        "decision": report_decision(failures, warnings),
        "failed_checks": "; ".join(failures) if failures else "none",
        "warnings": "; ".join(warnings) if warnings else "none",
        "checked_at": now_iso(),
    }


def main():
    parser = argparse.ArgumentParser(description="Check whether a draft Astro article is safe to publish.")
    parser.add_argument("--queue-id", default=DEFAULT_QUEUE_ID, help=f"Queue ID to check. Default: {DEFAULT_QUEUE_ID}")
    args = parser.parse_args()

    row = validate(args.queue_id.strip())
    write_csv(row)
    write_markdown(row)
    print(f"{row['file']}: {row['decision']} failed={row['failed_checks']} warnings={row['warnings']}")


if __name__ == "__main__":
    main()
