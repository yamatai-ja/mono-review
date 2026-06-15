import argparse
import csv
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTICLE_QUEUE = ROOT / "data" / "article_queue.csv"
PRODUCTS = ROOT / "data" / "products.csv"
OFFERS = ROOT / "data" / "offers.csv"
REPORT_CSV = ROOT / "output" / "rss_product_check_report.csv"
REPORT_MD = ROOT / "output" / "rss_product_check_report.md"


QUEUE_ID_FIELD = "queue_id"
PRODUCT_CARD_NOTE = "RSS source candidate. Product links need manual confirmation before body generation."
CTA_POLICY = [
    "Amazon/楽天/Yahooで販売確認後にProductCard化する",
    "公式またはキャリア販売ページを確認する",
    "価格・在庫・対応バンド・保証・SIMフリー/キャリア版の違いを確認する",
    "商品リンク未確認のまま購入CTAを強くしない",
]
PRE_BODY_CHECKS = [
    "Amazon/Rakuten/Yahooの商品URLを手動確認する",
    "公式販売ページまたはキャリア販売ページを確認する",
    "対応バンド、保証、SIMフリー版/キャリア版の違いを確認する",
    "RSS元URLの内容を確認し、公開情報ベースの記事として扱う",
]


def read_csv(path):
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        return rows, reader.fieldnames or []


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def normalize(text):
    return (text or "").strip().lower()


def tokens_from_keyword(keyword):
    return [token for token in re.split(r"[\s\-_/]+", normalize(keyword)) if len(token) >= 2]


def extract_source_url(notes):
    match = re.search(r"\burl=(https?://\S+)", notes or "")
    return match.group(1).strip() if match else ""


def find_queue_row(queue_id):
    rows, _ = read_csv(ARTICLE_QUEUE)
    for row in rows:
        if row.get(QUEUE_ID_FIELD) == queue_id:
            return row
    raise SystemExit(f"queue_id not found: {queue_id}")


def row_text(row):
    return " ".join(str(value or "") for value in row.values())


def find_product_candidates(keyword, title):
    rows, _ = read_csv(PRODUCTS)
    hay_tokens = tokens_from_keyword(f"{keyword} {title}")
    candidates = []
    for row in rows:
        text = normalize(row_text(row))
        score = sum(1 for token in hay_tokens if token in text)
        if score >= 2 or normalize(keyword) in text:
            candidates.append(row)
    return candidates


def find_offer_candidates(keyword, title):
    rows, _ = read_csv(OFFERS)
    relevant_terms = [
        "amazon",
        "rakuten",
        "楽天",
        "yahoo",
        "スマホ",
        "mobile",
        "モバイル",
        "carrier",
        "キャリア",
        "motorola",
        "edge",
    ]
    target = normalize(f"{keyword} {title}")
    candidates = []
    for row in rows:
        text = normalize(row_text(row))
        if any(term.lower() in text for term in relevant_terms) or any(term.lower() in target and term.lower() in text for term in relevant_terms):
            candidates.append(row)
    return candidates


def product_card_yaml(keyword):
    slug = re.sub(r"[^a-z0-9]+", "-", normalize(keyword)).strip("-") or "rss-product"
    product_id = f"{slug}-product-001"
    lines = [
        "products:",
        f'  - id: "{product_id}"',
        f'    title: "{keyword}"',
        f'    productGroup: "{product_id}"',
        '    amazon_url: ""',
        '    rakuten_url: ""',
        '    yahoo_url: ""',
        '    official_url: ""',
        "    notes:",
        f'      - "{PRODUCT_CARD_NOTE}"',
    ]
    return "\n".join(lines)


def summarize_rows(rows, keys):
    if not rows:
        return "none"
    parts = []
    for row in rows:
        values = [row.get(key, "") for key in keys if row.get(key, "")]
        parts.append(" / ".join(values) if values else row_text(row)[:80])
    return " || ".join(parts)


def decide(product_candidates, offer_candidates):
    if not product_candidates:
        return "needs_product_registration"
    if not offer_candidates:
        return "needs_offer_check"
    return "ready_for_body_prompt"


def build_report(queue_id):
    queue_row = find_queue_row(queue_id)
    keyword = queue_row.get("keyword", "")
    title = queue_row.get("article_title", "")
    notes = queue_row.get("notes", "")
    source_url = extract_source_url(notes)
    product_candidates = find_product_candidates(keyword, title)
    offer_candidates = find_offer_candidates(keyword, title)
    decision = decide(product_candidates, offer_candidates)
    if not product_candidates and not offer_candidates:
        # Keep the product registration decision, but make the weak-data state explicit in notes.
        decision_note = "product_missing_and_offer_weak"
    else:
        decision_note = decision
    checked_at = datetime.now(timezone.utc).isoformat()

    product_summary = summarize_rows(product_candidates, ["product_id", "name", "category", "status"])
    offer_summary = summarize_rows(offer_candidates, ["offer_id", "platform", "status", "url"])
    product_card = product_card_yaml(keyword)
    cta_policy = " | ".join(CTA_POLICY)
    pre_body_checks = " | ".join(PRE_BODY_CHECKS)

    csv_row = {
        "queue_id": queue_id,
        "keyword": keyword,
        "article_title": title,
        "source_url": source_url,
        "decision": decision,
        "decision_note": decision_note,
        "product_candidates": product_summary,
        "offer_candidates": offer_summary,
        "product_card_candidate": product_card.replace("\n", "\\n"),
        "cta_policy": cta_policy,
        "pre_body_checks": pre_body_checks,
        "checked_at": checked_at,
    }

    md = [
        "# RSS Product Check Dry Run",
        "",
        f"- queue_id: {queue_id}",
        f"- keyword: {keyword}",
        f"- article_title: {title}",
        f"- source_url: {source_url or 'none'}",
        f"- decision: {decision}",
        f"- decision_note: {decision_note}",
        "",
        "## Product Candidates",
        product_summary,
        "",
        "## Offer Candidates",
        offer_summary,
        "",
        "## ProductCard Candidate",
        "```yaml",
        product_card,
        "```",
        "",
        "## CTA Policy",
    ]
    md.extend(f"- {item}" for item in CTA_POLICY)
    md.extend(["", "## Pre Body Checks"])
    md.extend(f"- {item}" for item in PRE_BODY_CHECKS)
    md.extend(["", "## Notes", "- This is a dry-run report. No CSV, article, or ProductCard files were changed."])

    return csv_row, "\n".join(md) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Dry-run ProductCard/CTA check for RSS article queue candidates.")
    parser.add_argument("--queue-id", required=True, help="Target article_queue queue_id.")
    args = parser.parse_args()

    row, markdown = build_report(args.queue_id)
    fieldnames = [
        "queue_id",
        "keyword",
        "article_title",
        "source_url",
        "decision",
        "decision_note",
        "product_candidates",
        "offer_candidates",
        "product_card_candidate",
        "cta_policy",
        "pre_body_checks",
        "checked_at",
    ]
    write_csv(REPORT_CSV, [row], fieldnames)
    write_text(REPORT_MD, markdown)
    print(f"queue_id={row['queue_id']} decision={row['decision']}")


if __name__ == "__main__":
    main()
