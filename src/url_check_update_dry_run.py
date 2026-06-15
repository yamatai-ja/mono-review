from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCTS_CSV = ROOT / "data" / "products.csv"
OFFERS_CSV = ROOT / "data" / "offers.csv"
ARTICLE_MD = ROOT / "src" / "content" / "posts" / "motorola-edge-60.md"
REPORT_CSV = ROOT / "output" / "url_check_update_dry_run.csv"
REPORT_MD = ROOT / "output" / "url_check_update_dry_run.md"

QUEUE_ID = "q000005"
PRODUCT_ID = "motorola-edge-60-product-001"
OFFER_ID = "motorola-edge-60-offer-001"

REPORT_FIELDS = [
    "queue_id",
    "decision",
    "product_found",
    "offer_found",
    "url_input_status",
    "update_candidates",
    "sha256_changed",
    "backup_files",
    "checked_at",
]


def sha256(path: Path) -> str:
    if not path.exists():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames or [], list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def find_row(rows: list[dict[str, str]], key: str, value: str) -> dict[str, str] | None:
    for row in rows:
        if (row.get(key) or "").strip() == value:
            return row
    return None


def valid_url(value: str) -> bool:
    return not value or value.startswith("http://") or value.startswith("https://")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_reports(row: dict[str, str], details: list[str]) -> None:
    REPORT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerow(row)

    lines = [
        "# URL Check Update Dry Run",
        "",
        f"- queue_id: {row['queue_id']}",
        f"- decision: {row['decision']}",
        f"- product_found: {row['product_found']}",
        f"- offer_found: {row['offer_found']}",
        f"- url_input_status: {row['url_input_status']}",
        f"- sha256_changed: {row['sha256_changed']}",
        f"- backup_files: {row['backup_files'] or 'none'}",
        "",
        "## Update Candidates",
    ]
    lines.extend([f"- {item}" for item in details] or ["- none"])
    lines.extend(
        [
            "",
            "Note: without --apply this is a dry-run only. With --apply, only q000005 URL status fields are updated.",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_candidates(args, product_columns: list[str], offer_columns: list[str]) -> tuple[list[str], list[str]]:
    candidates: list[str] = []
    notes: list[str] = []

    if "amazon_url" in product_columns:
        candidates.append(f"products.csv amazon_url -> {args.amazon_url or '(empty; no change candidate)'}")
    if "rakuten_url" in product_columns:
        candidates.append(f"products.csv rakuten_url -> {args.rakuten_url or '(empty; no change candidate)'}")
    if args.amazon_url or args.rakuten_url or args.official_url or args.yahoo_url:
        if "status" in product_columns:
            candidates.append("products.csv status -> url_checked")

    if "url" in offer_columns:
        offer_url = args.amazon_url or args.rakuten_url or args.official_url or args.yahoo_url
        candidates.append(f"offers.csv url -> {offer_url or '(empty; no change candidate)'}")
    if args.amazon_url or args.rakuten_url or args.official_url or args.yahoo_url:
        if "status" in offer_columns:
            candidates.append("offers.csv status -> url_checked")
        if "updated_at" in offer_columns:
            candidates.append(f"offers.csv updated_at -> {date.today().isoformat()}")

    if args.official_url and "official_url" not in product_columns:
        notes.append(f"official_url not in products.csv columns; notes candidate -> {args.official_url}")
    if args.yahoo_url and "yahoo_url" not in product_columns:
        notes.append(f"yahoo_url not in products.csv columns; notes candidate -> {args.yahoo_url}")

    candidates.append('Markdown frontmatter url_status -> "url_checked"')
    candidates.append('Markdown frontmatter cta_policy -> "weak_cta_allowed_after_url_confirmed"')
    return candidates, notes


def markdown_has_updated_values() -> bool:
    if not ARTICLE_MD.exists():
        return False
    text = ARTICLE_MD.read_text(encoding="utf-8")
    return (
        'url_status: "url_checked"' in text
        and 'cta_policy: "weak_cta_allowed_after_url_confirmed"' in text
    )


def already_updated(product: dict[str, str] | None, offer: dict[str, str] | None, amazon_url: str) -> bool:
    if not product or not offer or not amazon_url:
        return False
    return (
        (product.get("amazon_url") or "").strip() == amazon_url
        and (product.get("status") or "").strip() == "url_checked"
        and (offer.get("url") or "").strip() == amazon_url
        and (offer.get("status") or "").strip() == "url_checked"
        and markdown_has_updated_values()
    )


def make_backup(path: Path, backup_stamp: str) -> Path:
    backup_path = path.with_name(f"{path.name}.bak.{backup_stamp}")
    shutil.copy2(path, backup_path)
    return backup_path


def apply_updates(
    product_columns: list[str],
    product_rows: list[dict[str, str]],
    offer_columns: list[str],
    offer_rows: list[dict[str, str]],
    amazon_url: str,
) -> list[str]:
    backup_stamp = stamp()
    backups = [
        make_backup(PRODUCTS_CSV, backup_stamp),
        make_backup(OFFERS_CSV, backup_stamp),
        make_backup(ARTICLE_MD, backup_stamp),
    ]

    for row in product_rows:
        if (row.get("product_id") or "").strip() == PRODUCT_ID:
            if "amazon_url" in product_columns:
                row["amazon_url"] = amazon_url
            if "status" in product_columns:
                row["status"] = "url_checked"

    for row in offer_rows:
        if (row.get("offer_id") or "").strip() == OFFER_ID:
            if "url" in offer_columns:
                row["url"] = amazon_url
            if "status" in offer_columns:
                row["status"] = "url_checked"
            if "updated_at" in offer_columns:
                row["updated_at"] = date.today().isoformat()

    write_csv(PRODUCTS_CSV, product_columns, product_rows)
    write_csv(OFFERS_CSV, offer_columns, offer_rows)

    text = ARTICLE_MD.read_text(encoding="utf-8")
    text = text.replace('url_status: "needs_url_check"', 'url_status: "url_checked"')
    text = text.replace(
        'cta_policy: "strong_cta_not_allowed_until_url_confirmed"',
        'cta_policy: "weak_cta_allowed_after_url_confirmed"',
    )
    ARTICLE_MD.write_text(text, encoding="utf-8")

    return [path.relative_to(ROOT).as_posix() for path in backups]


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run or apply URL confirmation updates for q000005.")
    parser.add_argument("--queue-id", required=True)
    parser.add_argument("--amazon-url", default="")
    parser.add_argument("--rakuten-url", default="")
    parser.add_argument("--official-url", default="")
    parser.add_argument("--yahoo-url", default="")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    before = {
        "products": sha256(PRODUCTS_CSV),
        "offers": sha256(OFFERS_CSV),
        "markdown": sha256(ARTICLE_MD),
    }

    product_columns, product_rows = read_csv(PRODUCTS_CSV)
    offer_columns, offer_rows = read_csv(OFFERS_CSV)
    product = find_row(product_rows, "product_id", PRODUCT_ID)
    offer = find_row(offer_rows, "offer_id", OFFER_ID)

    urls = [args.amazon_url, args.rakuten_url, args.official_url, args.yahoo_url]
    has_url = any(urls)
    invalid_urls = [url for url in urls if url and not valid_url(url)]

    if args.queue_id != QUEUE_ID:
        decision = "unsupported_queue_id"
    elif not product or not offer:
        decision = "missing_product_or_offer"
    elif invalid_urls:
        decision = "needs_manual_check"
    elif not has_url:
        decision = "needs_manual_url_input"
    else:
        decision = "ready_to_update"

    backup_files: list[str] = []
    if decision == "ready_to_update" and already_updated(product, offer, args.amazon_url):
        decision = "already_updated"
    elif args.apply and decision == "ready_to_update":
        backup_files = apply_updates(product_columns, product_rows, offer_columns, offer_rows, args.amazon_url)
        decision = "updated"

    candidates, notes = build_candidates(args, product_columns, offer_columns)
    if decision == "needs_manual_url_input":
        candidates = ["URL未指定のため、更新候補は作成するが反映不可"] + candidates
    if invalid_urls:
        notes.append("invalid_url_format: " + ", ".join(invalid_urls))
    if decision == "already_updated":
        notes.append("already_updated: target rows and frontmatter already contain requested values")

    after = {
        "products": sha256(PRODUCTS_CSV),
        "offers": sha256(OFFERS_CSV),
        "markdown": sha256(ARTICLE_MD),
    }
    changed = [key for key in before if before[key] != after[key]]
    sha_changed = "yes:" + ",".join(changed) if changed else "no"

    details = [
        f"product_id={PRODUCT_ID} found={str(product is not None).lower()}",
        f"offer_id={OFFER_ID} found={str(offer is not None).lower()}",
        f"amazon_url={args.amazon_url or '(not provided)'}",
        f"rakuten_url={args.rakuten_url or '(not provided)'}",
        f"official_url={args.official_url or '(not provided)'}",
        f"yahoo_url={args.yahoo_url or '(not provided)'}",
        *candidates,
        *notes,
    ]

    row = {
        "queue_id": args.queue_id,
        "decision": decision,
        "product_found": str(product is not None).lower(),
        "offer_found": str(offer is not None).lower(),
        "url_input_status": "provided" if has_url else "not_provided",
        "update_candidates": " | ".join(candidates + notes),
        "sha256_changed": sha_changed,
        "backup_files": " | ".join(backup_files),
        "checked_at": now_iso(),
    }
    write_reports(row, details)
    print(
        f"decision={decision} product_found={row['product_found']} "
        f"offer_found={row['offer_found']} sha256_changed={sha_changed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
