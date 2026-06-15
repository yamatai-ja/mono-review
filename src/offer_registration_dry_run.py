import argparse
import csv
import hashlib
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTICLE_QUEUE = ROOT / "data" / "article_queue.csv"
PRODUCTS = ROOT / "data" / "products.csv"
OFFERS = ROOT / "data" / "offers.csv"
RSS_PRODUCT_CHECK = ROOT / "output" / "rss_product_check_report.csv"
REPORT_CSV = ROOT / "output" / "offer_registration_dry_run.csv"
REPORT_MD = ROOT / "output" / "offer_registration_dry_run.md"


URL_CHECK_NOTE = "Amazon/Rakuten/Yahoo/official URLs need manual confirmation"
BODY_CHECK_NOTE = "Do not use this offer for strong purchase CTA until URLs are manually confirmed"
VARIANT_CHECK_NOTE = "Check price, stock, bands, warranty, SIM-free/carrier variant before body generation"


def read_csv(path):
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), reader.fieldnames or []


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_offers():
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    backup_path = OFFERS.with_name(f"{OFFERS.name}.bak.{timestamp}")
    shutil.copy2(OFFERS, backup_path)
    return backup_path


def normalize(text):
    return (text or "").strip().lower()


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", normalize(text)).strip("-")


def extract_source_url(notes):
    match = re.search(r"\burl=(https?://\S+)", notes or "")
    return match.group(1).strip() if match else ""


def choose_column(fieldnames, candidates):
    for candidate in candidates:
        if candidate in fieldnames:
            return candidate
    return None


def find_row(rows, key, value):
    for row in rows:
        if row.get(key) == value:
            return row
    return None


def row_text(row):
    return " ".join(str(value or "") for value in row.values())


def load_source_url(queue_id, queue_row):
    source_url = extract_source_url(queue_row.get("notes", ""))
    if source_url:
        return source_url
    rows, _ = read_csv(RSS_PRODUCT_CHECK)
    row = find_row(rows, "queue_id", queue_id)
    return (row or {}).get("source_url", "")


def find_product(products, keyword):
    for row in products:
        text = normalize(row_text(row))
        if normalize(keyword) in text:
            return row
    return None


def build_notes(source_url, missing_columns):
    notes = [
        "RSS source candidate",
        f"Source: {source_url}" if source_url else "Source: needs confirmation",
        URL_CHECK_NOTE,
        BODY_CHECK_NOTE,
        VARIANT_CHECK_NOTE,
    ]
    if missing_columns:
        notes.append(f"Not in offers.csv columns: {', '.join(missing_columns)}")
    return " | ".join(notes)


def build_candidate_row(fieldnames, queue_row, product_row, source_url):
    keyword = queue_row.get("keyword", "").strip()
    product_id = product_row.get("product_id", "") or f"{slugify(keyword)}-product-001"
    offer_id = f"{slugify(keyword)}-offer-001"
    missing_columns = []
    candidate = {field: "" for field in fieldnames}

    mappings = {
        "offer_id": ["offer_id", "id"],
        "product_id": ["product_id"],
        "product_name": ["product_name", "name", "title"],
        "offer_type": ["offer_type", "type"],
        "platform": ["platform"],
        "url": ["url", "offer_url"],
        "status": ["status"],
        "updated_at": ["updated_at", "checked_at"],
        "notes": ["notes", "memo"],
    }

    columns = {key: choose_column(fieldnames, names) for key, names in mappings.items()}
    if columns["offer_id"]:
        candidate[columns["offer_id"]] = offer_id
    else:
        missing_columns.append("offer_id/id")
    if columns["product_id"]:
        candidate[columns["product_id"]] = product_id
    else:
        missing_columns.append("product_id")
    if columns["product_name"]:
        candidate[columns["product_name"]] = keyword
    else:
        missing_columns.append("product_name/name/title")
    if columns["offer_type"]:
        candidate[columns["offer_type"]] = "product_link"
    else:
        missing_columns.append("offer_type/type")
    if columns["platform"]:
        candidate[columns["platform"]] = "multi"
    else:
        missing_columns.append("platform")
    if columns["url"]:
        candidate[columns["url"]] = ""
    else:
        missing_columns.append("url")
    if columns["status"]:
        candidate[columns["status"]] = "needs_url_check"
    else:
        missing_columns.append("status")
    if columns["updated_at"]:
        candidate[columns["updated_at"]] = datetime.now(timezone.utc).date().isoformat()
    else:
        missing_columns.append("updated_at")
    if columns["notes"]:
        candidate[columns["notes"]] = build_notes(source_url, missing_columns)
    else:
        missing_columns.append("notes")

    return candidate, missing_columns, offer_id, product_id


def find_duplicates(offers, fieldnames, offer_id, product_id):
    offer_id_col = choose_column(fieldnames, ["offer_id", "id"])
    product_id_col = choose_column(fieldnames, ["product_id"])
    duplicates = []
    for row in offers:
        offer_match = offer_id_col and normalize(row.get(offer_id_col)) == normalize(offer_id)
        product_match = product_id_col and normalize(row.get(product_id_col)) == normalize(product_id)
        if offer_match or product_match:
            duplicates.append(row)
    return duplicates


def run(queue_id, apply=False):
    before_hash = file_sha256(OFFERS) if OFFERS.exists() else ""
    queue_rows, _ = read_csv(ARTICLE_QUEUE)
    products, _ = read_csv(PRODUCTS)
    offers, offer_fields = read_csv(OFFERS)
    rows_before = len(offers)
    queue_row = find_row(queue_rows, "queue_id", queue_id)
    if not queue_row:
        raise SystemExit(f"queue_id not found: {queue_id}")

    keyword = queue_row.get("keyword", "")
    product_row = find_product(products, keyword)
    source_url = load_source_url(queue_id, queue_row)
    if product_row:
        candidate, missing_columns, offer_id, product_id = build_candidate_row(offer_fields, queue_row, product_row, source_url)
        duplicates = find_duplicates(offers, offer_fields, offer_id, product_id)
    else:
        candidate = {field: "" for field in offer_fields}
        missing_columns = ["registered_product"]
        offer_id = ""
        product_id = ""
        duplicates = []

    required_missing = [
        item
        for item in missing_columns
        if item in {"offer_id/id", "product_id", "platform", "url", "status", "notes", "registered_product"}
    ]
    optional_missing = [item for item in missing_columns if item not in required_missing]

    if duplicates:
        decision = "duplicate"
    elif "registered_product" in required_missing:
        decision = "needs_manual_check"
    elif not choose_column(offer_fields, ["url", "offer_url"]):
        decision = "cta_policy_only"
    elif not choose_column(offer_fields, ["offer_id", "id"]) or not choose_column(offer_fields, ["product_id"]) or not choose_column(offer_fields, ["platform"]):
        decision = "needs_manual_check"
    else:
        decision = "ready_to_register"

    mode = "apply" if apply else "dry_run"
    backup_path = ""
    applied = False
    apply_result = "not_requested"

    if apply:
        if decision != "ready_to_register":
            apply_result = f"skipped_{decision}"
        else:
            backup_path = str(backup_offers())
            updated_offers = list(offers)
            updated_offers.append(candidate)
            write_csv(OFFERS, updated_offers, offer_fields)
            applied = True
            apply_result = "added"

            refreshed_offers, _ = read_csv(OFFERS)
            post_duplicates = find_duplicates(refreshed_offers, offer_fields, offer_id, product_id)
            if len(post_duplicates) != 1:
                apply_result = f"added_with_duplicate_warning:{len(post_duplicates)}"

    final_offers, _ = read_csv(OFFERS)
    rows_after = len(final_offers)
    after_hash = file_sha256(OFFERS) if OFFERS.exists() else ""
    sha_changed = before_hash != after_hash
    warnings = [
        "url_blank_allowed_as_needs_url_check_candidate",
        "do_not_use_for_strong_cta_until_url_confirmed",
        "urls_need_manual_confirmation=amazon_url,rakuten_url,yahoo_url,official_url,carrier_url",
    ]
    if optional_missing:
        warnings.append(f"optional_columns_missing={','.join(optional_missing)}")
    if required_missing:
        warnings.append(f"required_or_policy_columns_missing={','.join(required_missing)}")

    checked_at = datetime.now(timezone.utc).isoformat()
    report_row = {
        "queue_id": queue_id,
        "mode": mode,
        "decision": decision,
        "apply_result": apply_result,
        "applied": str(applied).lower(),
        "offer_fields": ",".join(offer_fields),
        "candidate_row": " | ".join(f"{field}={candidate.get(field, '')}" for field in offer_fields),
        "duplicate_count": str(len(duplicates)),
        "duplicate_rows": " || ".join(row_text(row) for row in duplicates) if duplicates else "none",
        "rows_before": str(rows_before),
        "rows_after": str(rows_after),
        "rows_added": str(rows_after - rows_before),
        "backup_path": backup_path or "none",
        "source_url": source_url,
        "product_id": product_id,
        "offer_id": offer_id,
        "missing_columns": ",".join(missing_columns) if missing_columns else "none",
        "offers_sha256_before": before_hash,
        "offers_sha256_after": after_hash,
        "offers_sha256_changed": str(sha_changed).lower(),
        "warnings": " | ".join(warnings),
        "checked_at": checked_at,
    }

    csv_fields = [
        "queue_id",
        "mode",
        "decision",
        "apply_result",
        "applied",
        "offer_fields",
        "candidate_row",
        "duplicate_count",
        "duplicate_rows",
        "rows_before",
        "rows_after",
        "rows_added",
        "backup_path",
        "source_url",
        "product_id",
        "offer_id",
        "missing_columns",
        "offers_sha256_before",
        "offers_sha256_after",
        "offers_sha256_changed",
        "warnings",
        "checked_at",
    ]
    write_csv(REPORT_CSV, [report_row], csv_fields)

    candidate_lines = [f"- {field}: {candidate.get(field, '')}" for field in offer_fields]
    markdown = [
        "# Offer Registration Dry Run",
        "",
        f"- queue_id: {queue_id}",
        f"- mode: {mode}",
        f"- decision: {decision}",
        f"- apply_result: {apply_result}",
        f"- applied: {str(applied).lower()}",
        f"- product_id: {product_id or 'none'}",
        f"- offer_id: {offer_id or 'none'}",
        f"- source_url: {source_url or 'none'}",
        f"- rows_before: {rows_before}",
        f"- rows_after: {rows_after}",
        f"- rows_added: {rows_after - rows_before}",
        f"- backup_path: {backup_path or 'none'}",
        f"- offers_sha256_changed: {str(sha_changed).lower()}",
        "",
        "## offers.csv Columns",
        ", ".join(offer_fields) if offer_fields else "none",
        "",
        "## Candidate Row",
        *candidate_lines,
        "",
        "## Duplicate Check",
        f"- duplicate_count: {len(duplicates)}",
        f"- duplicate_rows: {report_row['duplicate_rows']}",
        "",
        "## URL Unconfirmed Items",
        "- url",
        "- Amazon URL",
        "- Rakuten URL",
        "- Yahoo URL",
        "- official URL",
        "- carrier sales URL",
        "",
        "## CTA Safety",
        "- URL is intentionally blank because external site checks have not been performed yet.",
        "- status must remain needs_url_check while URL, price, stock, bands, warranty, and SIM-free/carrier variants are unconfirmed.",
        "- Do not use this offer for strong purchase CTA before manual URL confirmation.",
        "- Duplicate checks run before backup creation, so duplicate apply attempts do not create a new backup.",
        "",
        "## Warnings",
        *[f"- {warning}" for warning in warnings],
        "",
        "## Notes",
        "- Dry-run mode does not change data/offers.csv.",
        "- Apply mode only appends one candidate row after duplicate checks pass.",
    ]
    write_text(REPORT_MD, "\n".join(markdown) + "\n")
    print(
        f"queue_id={queue_id} mode={mode} decision={decision} apply_result={apply_result} "
        f"rows_before={rows_before} rows_after={rows_after} offers_sha256_changed={str(sha_changed).lower()}"
    )


def main():
    parser = argparse.ArgumentParser(description="Dry-run offer registration from an article queue item.")
    parser.add_argument("--queue-id", required=True, help="Target article_queue queue_id.")
    parser.add_argument("--apply", action="store_true", help="Append the candidate row to data/offers.csv after safety checks.")
    args = parser.parse_args()
    run(args.queue_id, apply=args.apply)


if __name__ == "__main__":
    main()
