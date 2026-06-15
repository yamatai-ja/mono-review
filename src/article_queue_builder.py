from __future__ import annotations

import argparse
import csv
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"

KEYWORDS_CSV = DATA_DIR / "keywords.csv"
PRODUCTS_CSV = DATA_DIR / "products.csv"
OFFERS_CSV = DATA_DIR / "offers.csv"
ARTICLES_CSV = DATA_DIR / "articles.csv"
QUEUE_CSV = DATA_DIR / "article_queue.csv"
REPORT_MD = OUTPUT_DIR / "article_queue_report.md"

QUEUE_COLUMNS = [
    "queue_id",
    "keyword",
    "article_title",
    "article_type",
    "priority",
    "status",
    "assigned_product_ids",
    "notes",
    "created_at",
]

PROFIT_TERMS = [
    "レビュー",
    "口コミ",
    "メリット",
    "比較",
    "おすすめ",
    "使い方",
    "価格",
    "値段",
    "セール",
    "選び方",
    "対策",
]
YMYL_TERMS = [
    "医療",
    "薬",
    "病気",
    "治療",
    "投資",
    "保険",
    "借金",
    "法律",
    "税金",
    "副作用",
]
TARGET_KEYWORD_STATUSES = {"idea", "candidate"}
ACTIVE_OFFER_STATUSES = {"", "active", "candidate", "open", "url_checked", "needs_url_check"}


@dataclass
class CandidateResult:
    keyword: str
    article_title: str
    action: str
    reason: str
    score: int = 0


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = [{k: (v or "") for k, v in row.items()} for row in reader]
        return list(reader.fieldnames or []), rows


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def normalize_queue_columns(current_columns: list[str], rows: list[dict[str, str]]) -> tuple[list[str], list[dict[str, str]], list[str]]:
    if not current_columns:
        return QUEUE_COLUMNS, [], ["article_queue.csv_missing_would_create"]

    missing = [name for name in QUEUE_COLUMNS if name not in current_columns]
    extra = [name for name in current_columns if name not in QUEUE_COLUMNS]
    warnings: list[str] = []
    if missing:
        warnings.append("missing_queue_columns=" + ",".join(missing))
    if extra:
        warnings.append("extra_queue_columns_preserved=" + ",".join(extra))

    updated_columns = QUEUE_COLUMNS + extra
    normalized = [{name: row.get(name, "") for name in updated_columns} for row in rows]
    return updated_columns, normalized, warnings


def normalize(value: str) -> str:
    return (value or "").strip().lower()


def split_terms(value: str) -> list[str]:
    text = (value or "").replace("|", ",").replace(";", ",")
    return [part.strip() for part in text.split(",") if part.strip()]


def product_matches(keyword: str, product: dict[str, str]) -> bool:
    haystack = keyword.lower()
    terms = [product.get("name", ""), product.get("category", ""), *split_terms(product.get("tags", ""))]
    return any(term and term.lower() in haystack for term in terms)


def score_keyword(keyword: str, products: list[dict[str, str]], offers: list[dict[str, str]]) -> tuple[int, list[str], list[str]]:
    score = 0
    reasons: list[str] = []

    matched_terms = [term for term in PROFIT_TERMS if term in keyword]
    if matched_terms:
        score += len(matched_terms) * 2
        reasons.append("commercial_terms=" + "/".join(matched_terms))

    matched_products = [p for p in products if product_matches(keyword, p)]
    if matched_products:
        score += min(len(matched_products), 3) * 2
        reasons.append("matched_products=" + "/".join(p.get("product_id", "") or p.get("name", "") for p in matched_products[:3]))

    product_ids = {p.get("product_id", "") for p in matched_products if p.get("product_id", "")}
    matched_offers = [
        offer for offer in offers
        if offer.get("product_id", "") in product_ids and normalize(offer.get("status", "")) in ACTIVE_OFFER_STATUSES
    ]
    if matched_offers:
        score += min(len(matched_offers), 3) * 3
        reasons.append("matched_offers=" + "/".join(o.get("offer_id", "") or o.get("platform", "") for o in matched_offers[:3]))

    return score, reasons, sorted(product_ids)


def detect_article_type(keyword: str) -> str:
    if "比較" in keyword or "おすすめ" in keyword:
        return "comparison"
    if "レビュー" in keyword or "口コミ" in keyword or "メリット" in keyword:
        return "review"
    if "使い方" in keyword or "対策" in keyword or "設定" in keyword:
        return "howto"
    if "価格" in keyword or "値段" in keyword or "セール" in keyword:
        return "deal"
    return "seo_article"


def make_article_title(keyword: str) -> str:
    if any(term in keyword for term in PROFIT_TERMS):
        return keyword
    return f"{keyword}の選び方と確認ポイント"


def next_queue_id(rows: list[dict[str, str]]) -> str:
    max_num = 0
    for row in rows:
        value = row.get("queue_id", "")
        digits = "".join(ch for ch in value if ch.isdigit())
        if digits:
            max_num = max(max_num, int(digits))
    return f"q{max_num + 1:06d}"


def has_ymyl_risk(keyword: str) -> bool:
    return any(term in keyword for term in YMYL_TERMS)


def validate_required_columns(required: dict[str, tuple[list[str], list[str]]]) -> list[str]:
    missing_messages = []
    for file_name, (columns, required_columns) in required.items():
        missing = [column for column in required_columns if column not in columns]
        if missing:
            missing_messages.append(f"{file_name}: {', '.join(missing)}")
    return missing_messages


def validate_unique_rows(rows: list[dict[str, str]]) -> list[str]:
    warnings: list[str] = []
    for key in ["queue_id", "keyword", "article_title"]:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for row in rows:
            value = normalize(row.get(key, ""))
            if not value:
                continue
            if value in seen:
                duplicates.add(value)
            seen.add(value)
        if duplicates:
            warnings.append(f"duplicate_{key}=" + ",".join(sorted(duplicates)))
    return warnings


def plan_queue() -> tuple[list[str], list[dict[str, str]], list[CandidateResult], list[str]]:
    keyword_columns, keywords = read_csv(KEYWORDS_CSV)
    product_columns, products = read_csv(PRODUCTS_CSV)
    offer_columns, offers = read_csv(OFFERS_CSV)
    article_columns, articles = read_csv(ARTICLES_CSV)
    current_queue_columns, current_queue_rows = read_csv(QUEUE_CSV)
    queue_columns, queue_rows, warnings = normalize_queue_columns(current_queue_columns, current_queue_rows)

    required = {
        "keywords.csv": (keyword_columns, ["keyword", "status"]),
        "products.csv": (product_columns, ["product_id", "name", "category", "tags"]),
        "offers.csv": (offer_columns, ["offer_id", "product_id", "platform", "status"]),
        "articles.csv": (article_columns, ["title", "keyword"]),
        "article_queue.csv": (queue_columns, QUEUE_COLUMNS),
    }
    missing_messages = validate_required_columns(required)
    if missing_messages:
        raise SystemExit("Missing required CSV columns:\n" + "\n".join(missing_messages))

    warnings.extend(validate_unique_rows(queue_rows))

    existing_keywords = {normalize(row.get("keyword", "")) for row in queue_rows}
    existing_keywords.update(normalize(row.get("keyword", "")) for row in articles)
    existing_titles = {normalize(row.get("article_title", "")) for row in queue_rows}
    existing_titles.update(normalize(row.get("title", "")) for row in articles)

    additions: list[dict[str, str]] = []
    results: list[CandidateResult] = []
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for item in keywords:
        keyword = item.get("keyword", "").strip()
        status = normalize(item.get("status", ""))
        if not keyword:
            results.append(CandidateResult(keyword="", article_title="", action="skipped", reason="empty_keyword"))
            continue
        if status not in TARGET_KEYWORD_STATUSES:
            results.append(CandidateResult(keyword=keyword, article_title="", action="skipped", reason=f"status_not_target:{status or 'blank'}"))
            continue

        article_title = make_article_title(keyword)
        if normalize(keyword) in existing_keywords:
            results.append(CandidateResult(keyword=keyword, article_title=article_title, action="skipped", reason="duplicate_keyword"))
            continue
        if normalize(article_title) in existing_titles:
            results.append(CandidateResult(keyword=keyword, article_title=article_title, action="skipped", reason="duplicate_article_title"))
            continue

        score, reasons, product_ids = score_keyword(keyword, products, offers)
        if score <= 0:
            results.append(CandidateResult(keyword=keyword, article_title=article_title, action="skipped", reason="low_profit_signal", score=score))
            continue

        review_required = has_ymyl_risk(keyword)
        next_id = next_queue_id(queue_rows + additions)
        notes = [f"score={score}", *reasons]
        if review_required:
            notes.append("review_required=ymyl")

        additions.append({
            "queue_id": next_id,
            "keyword": keyword,
            "article_title": article_title,
            "article_type": detect_article_type(keyword),
            "priority": str(score),
            "status": "review_required" if review_required else "pending",
            "assigned_product_ids": ";".join(product_ids),
            "notes": " | ".join(notes),
            "created_at": created_at,
        })
        existing_keywords.add(normalize(keyword))
        existing_titles.add(normalize(article_title))
        results.append(CandidateResult(keyword=keyword, article_title=article_title, action="would_add", reason="queued", score=score))

    planned_rows = [*queue_rows, *additions]
    warnings.extend(validate_unique_rows(planned_rows))
    return queue_columns, planned_rows, results, warnings


def backup_file(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = path.with_name(f"{path.name}.bak.{timestamp}")
    shutil.copy2(path, backup_path)
    return backup_path


def write_report(added_count: int, skipped_count: int, applied: bool, warnings: list[str], results: list[CandidateResult]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Article Queue Report",
        "",
        f"Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"Mode: {'apply' if applied else 'dry-run'}",
        "",
        f"Planned additions: {added_count}",
        f"Skipped: {skipped_count}",
        "",
        "## Warnings",
        "",
    ]
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- none")
    lines.extend([
        "",
        "## Details",
        "",
        "| action | keyword | article_title | score | reason |",
        "| --- | --- | --- | ---: | --- |",
    ])
    for result in results:
        lines.append(
            f"| {result.action} | {result.keyword} | {result.article_title} | {result.score} | {result.reason} |"
        )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build article queue candidates from data/keywords.csv.")
    parser.add_argument("--apply", action="store_true", help="Write planned additions to data/article_queue.csv. Defaults to dry-run.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    queue_columns, planned_rows, results, warnings = plan_queue()
    additions = [result for result in results if result.action == "would_add"]
    skipped_count = sum(1 for result in results if result.action == "skipped")
    backup_path = ""

    if args.apply:
        if QUEUE_CSV.exists():
            backup_path = str(backup_file(QUEUE_CSV))
        write_csv(QUEUE_CSV, queue_columns, planned_rows)
        for result in results:
            if result.action == "would_add":
                result.action = "added"

    write_report(len(additions), skipped_count, args.apply, warnings, results)
    mode = "apply" if args.apply else "dry-run"
    print(
        f"mode={mode} planned_additions={len(additions)} skipped={skipped_count} "
        f"backup={backup_path or 'none'} report={REPORT_MD}"
    )


if __name__ == "__main__":
    main()
