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
RSS_PRODUCT_CHECK = ROOT / "output" / "rss_product_check_report.csv"
REPORT_CSV = ROOT / "output" / "product_registration_dry_run.csv"
REPORT_MD = ROOT / "output" / "product_registration_dry_run.md"


URL_CHECK_NOTE = "Amazon/Rakuten/Yahoo/official URLs need manual confirmation"
BODY_CHECK_NOTE = "Check price, stock, bands, warranty, SIM-free/carrier variant before body generation"


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


def normalize(text):
    return (text or "").strip().lower()


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", normalize(text)).strip("-")


def extract_source_url(notes):
    match = re.search(r"\burl=(https?://\S+)", notes or "")
    return match.group(1).strip() if match else ""


def find_row(rows, key, value):
    for row in rows:
        if row.get(key) == value:
            return row
    return None


def choose_column(fieldnames, candidates):
    for candidate in candidates:
        if candidate in fieldnames:
            return candidate
    return None


def row_text(row):
    return " ".join(str(value or "") for value in row.values())


def build_notes(source_url, missing_columns):
    notes = [
        "RSS source candidate",
        f"Source: {source_url}" if source_url else "Source: needs confirmation",
        URL_CHECK_NOTE,
        BODY_CHECK_NOTE,
    ]
    if missing_columns:
        notes.append(f"Not in products.csv columns: {', '.join(missing_columns)}")
    return " | ".join(notes)


def build_candidate_row(fieldnames, queue_row, source_url):
    keyword = queue_row.get("keyword", "").strip()
    product_slug = slugify(keyword) or "rss-product"
    product_id = f"{product_slug}-product-001"
    missing_columns = []
    candidate = {field: "" for field in fieldnames}

    id_col = choose_column(fieldnames, ["product_id", "id"])
    name_col = choose_column(fieldnames, ["name", "title", "product_name"])
    category_col = choose_column(fieldnames, ["category", "product_category"])
    tags_col = choose_column(fieldnames, ["tags"])
    status_col = choose_column(fieldnames, ["status"])
    notes_col = choose_column(fieldnames, ["notes", "memo"])

    if id_col:
        candidate[id_col] = product_id
    else:
        missing_columns.append("product_id/id")
    if name_col:
        candidate[name_col] = keyword
    else:
        missing_columns.append("name/title")
    if category_col:
        candidate[category_col] = "スマホ"
    else:
        missing_columns.append("category")
    if tags_col:
        candidate[tags_col] = "motorola,edge 60,スマホ,Android,RSS"
    else:
        missing_columns.append("tags")
    if status_col:
        candidate[status_col] = "needs_url_check"
    else:
        missing_columns.append("status")

    url_columns = {
        "amazon_url": "",
        "rakuten_url": "",
        "yahoo_url": "",
        "official_url": "",
    }
    for column, value in url_columns.items():
        if column in fieldnames:
            candidate[column] = value
        else:
            missing_columns.append(column)

    if notes_col:
        candidate[notes_col] = build_notes(source_url, missing_columns)
    else:
        missing_columns.append("notes")

    return candidate, missing_columns, product_id


def find_duplicates(products, candidate, fieldnames, keyword, product_id):
    id_col = choose_column(fieldnames, ["product_id", "id"])
    name_col = choose_column(fieldnames, ["name", "title", "product_name"])
    duplicates = []
    for row in products:
        id_match = id_col and normalize(row.get(id_col)) == normalize(product_id)
        name_match = name_col and normalize(row.get(name_col)) == normalize(keyword)
        text_match = normalize(keyword) in normalize(row_text(row))
        if id_match or name_match or text_match:
            duplicates.append(row)
    return duplicates


def backup_products():
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    backup_path = PRODUCTS.with_name(f"{PRODUCTS.name}.bak.{timestamp}")
    shutil.copy2(PRODUCTS, backup_path)
    return backup_path


def load_source_url(queue_id, queue_row):
    source_url = extract_source_url(queue_row.get("notes", ""))
    if source_url:
        return source_url
    rows, _ = read_csv(RSS_PRODUCT_CHECK)
    row = find_row(rows, "queue_id", queue_id)
    return (row or {}).get("source_url", "")


def run(queue_id, apply=False):
    before_hash = file_sha256(PRODUCTS) if PRODUCTS.exists() else ""
    queue_rows, _ = read_csv(ARTICLE_QUEUE)
    products, product_fields = read_csv(PRODUCTS)
    rows_before = len(products)
    queue_row = find_row(queue_rows, "queue_id", queue_id)
    if not queue_row:
        raise SystemExit(f"queue_id not found: {queue_id}")

    source_url = load_source_url(queue_id, queue_row)
    candidate, missing_columns, product_id = build_candidate_row(product_fields, queue_row, source_url)
    duplicates = find_duplicates(products, candidate, product_fields, queue_row.get("keyword", ""), product_id)
    if duplicates:
        decision = "duplicate"
    elif (missing_columns and not choose_column(product_fields, ["product_id", "id"])) or not choose_column(product_fields, ["name", "title", "product_name"]):
        decision = "needs_manual_check"
    else:
        decision = "ready_to_register"

    mode = "apply" if apply else "dry_run"
    backup_path = ""
    applied = False
    apply_result = "not_requested"
    products_after = list(products)

    if apply:
        if decision != "ready_to_register":
            apply_result = f"skipped_{decision}"
        else:
            backup_path = str(backup_products())
            products_after.append(candidate)
            write_csv(PRODUCTS, products_after, product_fields)
            applied = True
            apply_result = "added"

            refreshed_products, _ = read_csv(PRODUCTS)
            post_duplicates = find_duplicates(refreshed_products, candidate, product_fields, queue_row.get("keyword", ""), product_id)
            if len(post_duplicates) != 1:
                apply_result = f"added_with_duplicate_warning:{len(post_duplicates)}"

    final_products, _ = read_csv(PRODUCTS)
    rows_after = len(final_products)
    after_hash = file_sha256(PRODUCTS) if PRODUCTS.exists() else ""
    sha_changed = before_hash != after_hash

    warnings = []
    optional_missing = [item for item in missing_columns if item in {"yahoo_url", "official_url"}]
    required_missing = [item for item in missing_columns if item not in {"yahoo_url", "official_url"}]
    if optional_missing:
        warnings.append(f"optional_columns_missing={','.join(optional_missing)}")
    if required_missing:
        warnings.append(f"required_or_existing_mapping_missing={','.join(required_missing)}")
    warnings.append("urls_need_manual_confirmation=amazon_url,rakuten_url,yahoo_url,official_url")

    checked_at = datetime.now(timezone.utc).isoformat()
    report_row = {
        "queue_id": queue_id,
        "mode": mode,
        "decision": decision,
        "apply_result": apply_result,
        "applied": str(applied).lower(),
        "product_fields": ",".join(product_fields),
        "candidate_row": " | ".join(f"{key}={candidate.get(key, '')}" for key in product_fields),
        "duplicate_count": str(len(duplicates)),
        "duplicate_rows": " || ".join(row_text(row) for row in duplicates) if duplicates else "none",
        "rows_before": str(rows_before),
        "rows_after": str(rows_after),
        "rows_added": str(rows_after - rows_before),
        "backup_path": backup_path or "none",
        "source_url": source_url,
        "missing_columns": ",".join(missing_columns) if missing_columns else "none",
        "products_sha256_before": before_hash,
        "products_sha256_after": after_hash,
        "products_sha256_changed": str(sha_changed).lower(),
        "warnings": " | ".join(warnings),
        "checked_at": checked_at,
    }

    csv_fields = [
        "queue_id",
        "mode",
        "decision",
        "apply_result",
        "applied",
        "product_fields",
        "candidate_row",
        "duplicate_count",
        "duplicate_rows",
        "rows_before",
        "rows_after",
        "rows_added",
        "backup_path",
        "source_url",
        "missing_columns",
        "products_sha256_before",
        "products_sha256_after",
        "products_sha256_changed",
        "warnings",
        "checked_at",
    ]
    write_csv(REPORT_CSV, [report_row], csv_fields)

    candidate_lines = [f"- {field}: {candidate.get(field, '')}" for field in product_fields]
    markdown = [
        "# Product Registration Dry Run",
        "",
        f"- queue_id: {queue_id}",
        f"- mode: {mode}",
        f"- decision: {decision}",
        f"- apply_result: {apply_result}",
        f"- applied: {str(applied).lower()}",
        f"- source_url: {source_url or 'none'}",
        f"- rows_before: {rows_before}",
        f"- rows_after: {rows_after}",
        f"- rows_added: {rows_after - rows_before}",
        f"- backup_path: {backup_path or 'none'}",
        f"- products_sha256_changed: {str(sha_changed).lower()}",
        "",
        "## products.csv Columns",
        ", ".join(product_fields) if product_fields else "none",
        "",
        "## Candidate Row",
        *candidate_lines,
        "",
        "## Duplicate Check",
        f"- duplicate_count: {len(duplicates)}",
        f"- duplicate_rows: {report_row['duplicate_rows']}",
        "",
        "## URL Unconfirmed Items",
        "- amazon_url",
        "- rakuten_url",
        "- yahoo_url",
        "- official_url",
        "",
        "## Why URLs Are Blank",
        "- Amazon/Rakuten/Yahoo/official URLs are intentionally blank because external site checks have not been performed yet.",
        "- status remains needs_url_check until URLs, price, stock, bands, warranty, and SIM-free/carrier variants are manually confirmed.",
        "",
        "## Warnings",
        *[f"- {warning}" for warning in warnings],
        "",
        "## Notes",
        "- Dry-run mode does not change data/products.csv.",
        "- Apply mode only appends one candidate row after duplicate checks pass.",
    ]
    write_text(REPORT_MD, "\n".join(markdown) + "\n")
    print(
        f"queue_id={queue_id} mode={mode} decision={decision} "
        f"apply_result={apply_result} rows_before={rows_before} rows_after={rows_after} "
        f"products_sha256_changed={str(sha_changed).lower()}"
    )


def main():
    parser = argparse.ArgumentParser(description="Dry-run product registration from an article queue item.")
    parser.add_argument("--queue-id", required=True, help="Target article_queue queue_id.")
    parser.add_argument("--apply", action="store_true", help="Append the candidate row to data/products.csv after safety checks.")
    args = parser.parse_args()
    run(args.queue_id, apply=args.apply)


if __name__ == "__main__":
    main()
