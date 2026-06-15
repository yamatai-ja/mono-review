from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"

QUEUE_CSV = DATA_DIR / "article_queue.csv"
PRODUCTS_CSV = DATA_DIR / "products.csv"
OFFERS_CSV = DATA_DIR / "offers.csv"
REPORT_CSV = OUTPUT_DIR / "editor_score_report.csv"
REPORT_MD = OUTPUT_DIR / "editor_score_report.md"

QUEUE_REQUIRED_COLUMNS = [
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
PRODUCT_REQUIRED_COLUMNS = ["product_id", "name", "category", "tags", "status"]
OFFER_REQUIRED_COLUMNS = ["offer_id", "product_id", "platform", "url", "status"]

COMMERCIAL_TERMS = ["??", "???", "?????", "??", "????", "???", "???", "??"]
YMYL_TERMS = ["??", "??", "AGA", "??", "?", "??", "??", "??", "??", "??", "??", "??", "??", "??"]
STRONG_TOPICS = [
    "?????",
    "???SSD",
    "SSD",
    "USB??",
    "USB-C",
    "????WiFi",
    "WiFi",
    "povo",
    "????",
    "UGREEN",
    "FS040W",
]
GOOD_ARTICLE_TYPES = {"review", "howto", "comparison"}
ACTIVE_OFFER_STATUSES = {"", "active", "candidate", "open"}
RSS_GENERIC_TERMS = {"ai", "pro", "plus", "max", "mini", "ultra", "スマホ セール"}
RSS_RISK_TERMS = ["政治", "規制", "輸出", "事件", "訴訟", "逮捕", "政府", "決算", "人事"]
RSS_PRODUCT_PATTERNS = [
    re.compile(r"\b[A-Za-z][A-Za-z0-9+-]{2,}(?:\s+[A-Za-z0-9][A-Za-z0-9+-]{1,}){0,3}\b"),
    re.compile(r"[A-Za-z]+[\s-]?[0-9][A-Za-z0-9+-]*"),
    re.compile(r"(第\d+世代|[0-9]+GB|[0-9]+TB|[0-9]+W|[0-9]+mAh|[0-9]+Wh|[0-9]+型)"),
]


@dataclass
class ScoreResult:
    queue_id: str
    keyword: str
    article_title: str
    article_type: str
    current_priority: str
    editor_score: int
    decision: str
    review_required: bool
    reasons: list[str]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), [{k: (v or "") for k, v in row.items()} for row in reader]


def require_columns(file_name: str, columns: list[str], required: list[str]) -> None:
    missing = [name for name in required if name not in columns]
    if missing:
        raise SystemExit(f"Missing required CSV columns in {file_name}: {', '.join(missing)}")


def split_ids(value: str) -> list[str]:
    return [part.strip() for part in (value or "").replace(",", ";").split(";") if part.strip()]


def normalize(value: str) -> str:
    return (value or "").strip().lower()


def to_int(value: str, default: int = 0) -> int:
    try:
        return int(float(value or default))
    except ValueError:
        return default


def has_any(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term.lower() in text.lower()]


def is_rss_candidate(row: dict[str, str]) -> bool:
    return row.get("status", "") == "candidate_from_rss" or "source=rss" in row.get("notes", "").lower()


def has_rss_product_like_text(keyword: str, article_title: str) -> bool:
    text = f"{keyword} {article_title}".strip()
    normalized_keyword = keyword.strip().lower()
    if normalized_keyword in RSS_GENERIC_TERMS:
        return False
    if len(normalized_keyword) < 4:
        return False
    return any(pattern.search(text) for pattern in RSS_PRODUCT_PATTERNS)


def has_rss_risk(text: str) -> bool:
    return bool(has_any(text, RSS_RISK_TERMS))


def product_text(product: dict[str, str]) -> str:
    return " ".join([
        product.get("name", ""),
        product.get("category", ""),
        product.get("tags", ""),
        product.get("notes", ""),
    ])


def decide(score: int, review_required: bool) -> str:
    if review_required:
        return "needs_review"
    if score >= 80:
        return "write_now"
    if score >= 60:
        return "write_later"
    if score >= 40:
        return "needs_review"
    return "skip"


def score_row(
    row: dict[str, str],
    products_by_id: dict[str, dict[str, str]],
    offers_by_product_id: dict[str, list[dict[str, str]]],
) -> ScoreResult:
    keyword = row.get("keyword", "")
    article_title = row.get("article_title", "")
    article_type = row.get("article_type", "")
    current_priority = row.get("priority", "")
    notes = row.get("notes", "")
    assigned_product_ids = split_ids(row.get("assigned_product_ids", ""))

    text = f"{keyword} {article_title} {article_type} {notes}"
    reasons: list[str] = []
    score = 30
    rss_candidate = is_rss_candidate(row)
    rss_product_like = rss_candidate and has_rss_product_like_text(keyword, article_title) and not has_rss_risk(text)

    priority_points = min(to_int(current_priority) * 3, 15)
    if priority_points:
        score += priority_points
        reasons.append(f"current_priority+{priority_points}")

    if rss_candidate and not has_rss_risk(text):
        score += 10
        reasons.append("rss_candidate_bonus+10")
    if rss_candidate and "source=rss" in notes.lower() and not has_rss_risk(text):
        score += 10
        reasons.append("rss_source_bonus+10")
    if rss_product_like:
        score += 15
        reasons.append("rss_product_like_bonus+15")

    commercial_matches = has_any(text, COMMERCIAL_TERMS)
    if commercial_matches:
        points = min(len(commercial_matches) * 8, 24)
        score += points
        reasons.append("commercial_terms+{}:{}".format(points, "/".join(commercial_matches)))

    matched_products = [products_by_id[pid] for pid in assigned_product_ids if pid in products_by_id]
    product_context = " ".join(product_text(product) for product in matched_products)
    topic_matches = has_any(f"{text} {product_context}", STRONG_TOPICS)
    if topic_matches:
        points = min(len(topic_matches) * 6, 24)
        score += points
        reasons.append("strong_topic+{}:{}".format(points, "/".join(topic_matches)))

    if article_type in GOOD_ARTICLE_TYPES:
        score += 12
        reasons.append(f"article_type+12:{article_type}")
    if rss_candidate and rss_product_like and article_type == "review":
        score += 5
        reasons.append("rss_review_bonus+5")

    if assigned_product_ids and matched_products:
        score += 14
        reasons.append("product_match+14:" + "/".join(pid for pid in assigned_product_ids if pid in products_by_id))
    elif assigned_product_ids:
        score -= 10
        reasons.append("product_missing-10")
    elif rss_candidate and rss_product_like:
        score -= 5
        reasons.append("no_assigned_product_rss_relaxed-5")
    else:
        score -= 15
        reasons.append("no_assigned_product-15")

    active_offers = []
    for pid in assigned_product_ids:
        for offer in offers_by_product_id.get(pid, []):
            if normalize(offer.get("status", "")) in ACTIVE_OFFER_STATUSES:
                active_offers.append(offer)
    if active_offers:
        score += 16
        reasons.append("offer_match+16:" + "/".join(o.get("offer_id", "") for o in active_offers[:3]))
    elif rss_candidate and rss_product_like:
        score -= 3
        reasons.append("no_offer_match_rss_relaxed-3")
    else:
        score -= 8
        reasons.append("no_offer_match-8")

    combined_risk_text = f"{text} {product_context}"
    ymyl_matches = has_any(combined_risk_text, YMYL_TERMS)
    review_required = bool(ymyl_matches)
    if review_required:
        score -= 25
        reasons.append("ymyl_review_required:" + "/".join(ymyl_matches))

    if len(keyword.strip()) <= 3:
        score -= 12
        reasons.append("keyword_too_broad-12")
    if "????" in notes or "??" in notes:
        score -= 10
        reasons.append("insufficient_info-10")

    score = max(0, min(100, score))
    decision = decide(score, review_required)
    return ScoreResult(
        queue_id=row.get("queue_id", ""),
        keyword=keyword,
        article_title=article_title,
        article_type=article_type,
        current_priority=current_priority,
        editor_score=score,
        decision=decision,
        review_required=review_required,
        reasons=reasons,
    )


def write_csv_report(results: list[ScoreResult]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "queue_id",
        "keyword",
        "article_title",
        "article_type",
        "current_priority",
        "editor_score",
        "decision",
        "review_required",
        "reasons",
    ]
    with REPORT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow({
                "queue_id": result.queue_id,
                "keyword": result.keyword,
                "article_title": result.article_title,
                "article_type": result.article_type,
                "current_priority": result.current_priority,
                "editor_score": result.editor_score,
                "decision": result.decision,
                "review_required": str(result.review_required).lower(),
                "reasons": " | ".join(result.reasons),
            })


def write_markdown_report(results: list[ScoreResult]) -> None:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.decision] = counts.get(result.decision, 0) + 1

    lines = [
        "# Editor Score Report",
        "",
        f"Total candidates: {len(results)}",
        "",
        "## Decisions",
        "",
    ]
    for decision in ["write_now", "write_later", "needs_review", "skip"]:
        lines.append(f"- {decision}: {counts.get(decision, 0)}")
    lines.extend([
        "",
        "## Scores",
        "",
        "| queue_id | keyword | editor_score | decision | review_required | reasons |",
        "| --- | --- | ---: | --- | --- | --- |",
    ])
    for result in sorted(results, key=lambda item: item.editor_score, reverse=True):
        lines.append(
            f"| {result.queue_id} | {result.keyword} | {result.editor_score} | {result.decision} | {str(result.review_required).lower()} | {' | '.join(result.reasons)} |"
        )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_scores() -> list[ScoreResult]:
    queue_columns, queue_rows = read_csv(QUEUE_CSV)
    product_columns, product_rows = read_csv(PRODUCTS_CSV)
    offer_columns, offer_rows = read_csv(OFFERS_CSV)

    require_columns("article_queue.csv", queue_columns, QUEUE_REQUIRED_COLUMNS)
    require_columns("products.csv", product_columns, PRODUCT_REQUIRED_COLUMNS)
    require_columns("offers.csv", offer_columns, OFFER_REQUIRED_COLUMNS)

    products_by_id = {row.get("product_id", ""): row for row in product_rows if row.get("product_id", "")}
    offers_by_product_id: dict[str, list[dict[str, str]]] = {}
    for offer in offer_rows:
        offers_by_product_id.setdefault(offer.get("product_id", ""), []).append(offer)

    results = [score_row(row, products_by_id, offers_by_product_id) for row in queue_rows]
    write_csv_report(results)
    write_markdown_report(results)
    return results


def main() -> None:
    results = build_scores()
    print(f"scored={len(results)} csv={REPORT_CSV} md={REPORT_MD}")
    for result in results:
        print(f"{result.queue_id}\t{result.editor_score}\t{result.decision}")


if __name__ == "__main__":
    main()
