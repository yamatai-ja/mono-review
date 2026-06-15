from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
OUTLINE_DIR = OUTPUT_DIR / "outlines"

EDITOR_REPORT_CSV = OUTPUT_DIR / "editor_score_report.csv"
QUEUE_CSV = DATA_DIR / "article_queue.csv"
PRODUCTS_CSV = DATA_DIR / "products.csv"
OFFERS_CSV = DATA_DIR / "offers.csv"
OUTLINE_REPORT_MD = OUTPUT_DIR / "outline_report.md"
TARGET_QUEUE_IDS = {"q000003"}

EDITOR_REQUIRED_COLUMNS = ["queue_id", "decision", "editor_score", "review_required", "reasons"]
QUEUE_REQUIRED_COLUMNS = ["queue_id", "keyword", "article_title", "article_type", "assigned_product_ids", "notes"]
PRODUCT_REQUIRED_COLUMNS = ["product_id", "name", "category", "tags", "status"]
OFFER_REQUIRED_COLUMNS = ["offer_id", "product_id", "platform", "url", "status"]
ACTIVE_OFFER_STATUSES = {"", "active", "candidate", "open"}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), [{k: (v or "") for k, v in row.items()} for row in reader]


def require_columns(file_name: str, columns: list[str], required: Iterable[str]) -> None:
    missing = [column for column in required if column not in columns]
    if missing:
        raise SystemExit(f"Missing required CSV columns in {file_name}: {', '.join(missing)}")


def split_ids(value: str) -> list[str]:
    return [part.strip() for part in (value or "").replace(",", ";").split(";") if part.strip()]


def safe_file_stem(value: str) -> str:
    return "".join(char for char in value if char.isalnum() or char in {"-", "_"}) or "outline"


def products_for_ids(product_ids: list[str], products_by_id: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    return [products_by_id[product_id] for product_id in product_ids if product_id in products_by_id]


def active_offers_for_product_ids(product_ids: list[str], offers: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        offer for offer in offers
        if offer.get("product_id", "") in product_ids and offer.get("status", "").strip().lower() in ACTIVE_OFFER_STATUSES
    ]


def is_rss_candidate(queue_row: dict[str, str]) -> bool:
    return queue_row.get("status", "") == "candidate_from_rss" or "source=rss" in queue_row.get("notes", "").lower()


def format_product_list(products: list[dict[str, str]]) -> list[str]:
    if not products:
        return ["- CTA\u8981\u78ba\u8a8d: \u7d39\u4ecb\u5019\u88dc\u5546\u54c1\u306a\u3057"]
    return [f"- {product.get('product_id', '')}: {product.get('name', '')}" for product in products]


def format_offer_list(offers: list[dict[str, str]]) -> list[str]:
    if not offers:
        return ["- CTA\u8981\u78ba\u8a8d: \u7d39\u4ecb\u5019\u88dc\u6848\u4ef6\u306a\u3057"]
    return [f"- {offer.get('offer_id', '')}: {offer.get('platform', '')} / {offer.get('url', '')}" for offer in offers]


def build_outline(score_row: dict[str, str], queue_row: dict[str, str], products_by_id: dict[str, dict[str, str]], offers: list[dict[str, str]]) -> str:
    queue_id = queue_row.get("queue_id", "")
    keyword = queue_row.get("keyword", "")
    title = queue_row.get("article_title", "") or score_row.get("article_title", "")
    article_type = queue_row.get("article_type", "") or score_row.get("article_type", "seo_article")
    product_ids = split_ids(queue_row.get("assigned_product_ids", ""))
    products = products_for_ids(product_ids, products_by_id)
    matched_offers = active_offers_for_product_ids(product_ids, offers)

    rss_review = is_rss_candidate(queue_row) and article_type == "review"
    if rss_review:
        search_intent = f"{keyword} \u304c\u81ea\u5206\u306b\u5408\u3046\u304b\u3001\u4fa1\u683c\u30fb\u6027\u80fd\u30fb\u6ce8\u610f\u70b9\u30fb\u8cfc\u5165\u5148\u3092\u6bd4\u8f03\u3057\u3066\u5224\u65ad\u3057\u305f\u3044\u3002"
        audience = f"{keyword} \u306e\u8cfc\u5165\u3092\u691c\u8a0e\u3057\u3066\u3044\u308b\u4eba\u3001\u30b9\u30de\u30db\u306e\u4fa1\u683c\u30fb\u6027\u80fd\u30fb\u4fdd\u8a3c\u30fb\u8ca9\u58f2\u7d4c\u8def\u3092\u78ba\u8a8d\u3057\u305f\u3044\u4eba\u3002"
        sections = [
            (f"H2: \u7d50\u8ad6\uff1a{keyword}\u306f\u3069\u3093\u306a\u4eba\u306b\u5411\u3044\u3066\u3044\u308b\u304b", ["H3: \u5148\u306b\u78ba\u8a8d\u3057\u305f\u3044\u5224\u65ad\u57fa\u6e96"]),
            (f"H2: {keyword}\u306e\u4e3b\u306a\u7279\u5fb4", ["H3: \u6027\u80fd\u30fb\u753b\u9762\u30fb\u30ab\u30e1\u30e9\u306e\u78ba\u8a8d\u30dd\u30a4\u30f3\u30c8", "H3: \u30d0\u30c3\u30c6\u30ea\u30fc\u30fb\u30b5\u30a4\u30ba\u30fb\u4f7f\u3044\u3084\u3059\u3055\u306e\u898b\u65b9"]),
            ("H2: \u8cfc\u5165\u524d\u306b\u78ba\u8a8d\u3057\u305f\u3044\u6ce8\u610f\u70b9", ["H3: \u5bfe\u5fdc\u30d0\u30f3\u30c9\u30fbSIM\u30fb\u8ca9\u58f2\u30e2\u30c7\u30eb\u306e\u78ba\u8a8d", "H3: \u4fa1\u683c\u30fb\u5728\u5eab\u30fb\u4fdd\u8a3c\u306f\u5909\u52d5\u3059\u308b"]),
            ("H2: \u7af6\u5408\u30fb\u65e7\u30e2\u30c7\u30eb\u3068\u6bd4\u8f03\u3059\u308b\u3068\u304d\u306e\u898b\u308b\u30dd\u30a4\u30f3\u30c8", ["H3: \u4fa1\u683c\u5e2f\u3068\u6027\u80fd\u5dee", "H3: \u30ad\u30e3\u30ea\u30a2\u7248\u3068SIM\u30d5\u30ea\u30fc\u7248\u306e\u9055\u3044"]),
            ("H2: \u3069\u3053\u3067\u8cb7\u3046\u3079\u304d\u304b", ["H3: Amazon\u30fb\u697d\u5929\u30fb\u516c\u5f0f\u30fb\u30ad\u30e3\u30ea\u30a2\u8ca9\u58f2\u306e\u78ba\u8a8d", "H3: \u8cfc\u5165\u524d\u306b\u898b\u308b\u3079\u304d\u4fa1\u683c\u30fb\u4fdd\u8a3c\u30fb\u5728\u5eab"]),
            ("H2: \u5411\u3044\u3066\u3044\u308b\u4eba\u30fb\u5411\u3044\u3066\u3044\u306a\u3044\u4eba", ["H3: \u5411\u3044\u3066\u3044\u308b\u4eba", "H3: \u5225\u306e\u7aef\u672b\u3082\u691c\u8a0e\u3057\u305f\u3044\u4eba"]),
            ("H2: FAQ", ["H3: \u3088\u304f\u3042\u308b\u8cea\u554f"]),
            ("H2: \u307e\u3068\u3081", ["H3: \u8cfc\u5165\u524d\u306e\u6700\u7d42\u78ba\u8a8d"]),
        ]
        no_experience_lines = [
            "- \u516c\u958b\u60c5\u5831\u30fb\u516c\u5f0f\u60c5\u5831\u30fb\u8ca9\u58f2\u60c5\u5831\u30fbRSS\u5143\u30cb\u30e5\u30fc\u30b9\u3092\u3082\u3068\u306b\u3057\u305f\u8cfc\u5165\u5224\u65ad\u8a18\u4e8b\u3068\u3057\u3066\u69cb\u6210\u3059\u308b\u3002",
            "- \u672a\u78ba\u8a8d\u306e\u4f7f\u7528\u611f\u306f\u65ad\u5b9a\u305b\u305a\u3001\u4ed5\u69d8\u30fb\u4fa1\u683c\u30fb\u8ca9\u58f2\u6761\u4ef6\u306e\u78ba\u8a8d\u30dd\u30a4\u30f3\u30c8\u3068\u3057\u3066\u6574\u7406\u3059\u308b\u3002",
        ]
        cta_policy = "- \u4fa1\u683c\u30fb\u5728\u5eab\u30fb\u5bfe\u5fdc\u30d0\u30f3\u30c9\u30fb\u4fdd\u8a3c\u3092\u78ba\u8a8d\u3057\u3066\u304b\u3089\u8cfc\u5165\u3059\u308b\u5c0e\u7dda\u306b\u3059\u308b\u3002ProductCard\u3084Amazon/\u697d\u5929\u30ea\u30f3\u30af\u304c\u672a\u8a2d\u5b9a\u306a\u3089\u672c\u6587\u751f\u6210\u524d\u306b\u5546\u54c1\u30fb\u6848\u4ef6\u78ba\u8a8d\u3092\u5fc5\u9808\u306b\u3059\u308b\u3002"
        internal_links = [
            "- \u30b9\u30de\u30db\u6bd4\u8f03\u3001\u30e2\u30d0\u30a4\u30eb\u901a\u4fe1\u3001Android\u30b9\u30de\u30db\u3001Amazon/\u697d\u5929\u306e\u8cfc\u5165\u5c0e\u7dda\u306b\u95a2\u9023\u3059\u308b\u8a18\u4e8b\u304c\u3042\u308c\u3070\u5185\u90e8\u30ea\u30f3\u30af\u5019\u88dc\u306b\u3059\u308b\u3002",
            "- \u307e\u3060\u95a2\u9023\u8a18\u4e8b\u304c\u306a\u3044\u5834\u5408\u306f\u3001\u672c\u6587\u751f\u6210\u524d\u306b\u95a2\u9023\u5019\u88dc\u3092\u78ba\u8a8d\u3059\u308b\u3002",
        ]
        expression_notes = [
            "- \u8a66\u7528\u6e08\u307f\u3068\u8aa4\u89e3\u3055\u308c\u308b\u8868\u73fe\u3092\u907f\u3051\u3001\u8abf\u67fb\u30fb\u6bd4\u8f03\u30fb\u8cfc\u5165\u5224\u65ad\u306e\u6587\u8108\u3067\u66f8\u304f\u3002",
            "- \u4fa1\u683c\u3001\u5728\u5eab\u3001\u30ad\u30e3\u30f3\u30da\u30fc\u30f3\u3001\u901a\u4fe1\u54c1\u8cea\u3001\u4fdd\u8a3c\u5185\u5bb9\u306f\u5909\u52d5\u3059\u308b\u305f\u3081\u65ad\u5b9a\u3057\u306a\u3044\u3002",
            "- \u5bfe\u5fdc\u30d0\u30f3\u30c9\u3001SIM\u3001\u8ca9\u58f2\u30e2\u30c7\u30eb\u3001\u4fdd\u8a3c\u6761\u4ef6\u306f\u516c\u5f0f\u60c5\u5831\u306e\u78ba\u8a8d\u3092\u4fc3\u3059\u3002",
        ]
    else:
        search_intent = "- FS040W\u3067povo\u3092\u4f7f\u3046\u305f\u3081\u306e\u8a2d\u5b9a\u624b\u9806\u3001\u9078\u3073\u65b9\u3001\u6ce8\u610f\u70b9\u3001\u95a2\u9023\u30b5\u30fc\u30d3\u30b9\u3092\u77ed\u6642\u9593\u3067\u78ba\u8a8d\u3057\u305f\u3044\u3002"
        audience = "- \u30e2\u30d0\u30a4\u30eb\u56de\u7dda\u3084\u30eb\u30fc\u30bf\u30fc\u8a2d\u5b9a\u3067\u8ff7\u3063\u3066\u3044\u308b\u521d\u5fc3\u8005\u304b\u3089\u4e2d\u7d1a\u8005\u3002"
        sections = [
            ("H2: \u7d50\u8ad6", ["H3: \u5148\u306b\u62bc\u3055\u3048\u308b\u5224\u65ad\u57fa\u6e96"]),
            ("H2: FS040W\u3067povo\u3092\u4f7f\u3046\u524d\u306b\u78ba\u8a8d\u3059\u308b\u3053\u3068", ["H3: \u5bfe\u5fdc\u56de\u7dda\u3068SIM\u306e\u78ba\u8a8d", "H3: \u6599\u91d1\u30fb\u7528\u9014\u30fb\u901a\u4fe1\u91cf\u306e\u8003\u3048\u65b9"]),
            ("H2: FS040W povo\u8a2d\u5b9a\u306e\u57fa\u672c\u624b\u9806", ["H3: \u521d\u671f\u8a2d\u5b9a\u306e\u6d41\u308c", "H3: APN\u8a2d\u5b9a\u3067\u78ba\u8a8d\u3059\u308b\u9805\u76ee"]),
            ("H2: \u9078\u3073\u65b9\u3068\u304a\u3059\u3059\u3081\u5019\u88dc", ["H3: FS040W\u304c\u5411\u3044\u3066\u3044\u308b\u4eba", "H3: povo\u95a2\u9023\u30b5\u30fc\u30d3\u30b9\u5c0e\u7dda\u306e\u8003\u3048\u65b9"]),
            ("H2: \u6ce8\u610f\u70b9", ["H3: \u5951\u7d04\u30fb\u4fdd\u8a3c\u30fb\u4e92\u63db\u6027\u306e\u78ba\u8a8d", "H3: \u4fa1\u683c\u3084\u30ad\u30e3\u30f3\u30da\u30fc\u30f3\u3092\u65ad\u5b9a\u3057\u306a\u3044"]),
            ("H2: FAQ", ["H3: \u3088\u304f\u3042\u308b\u8cea\u554f"]),
        ]
        no_experience_lines = [
            "- \u5b9f\u6a5f\u30ec\u30d3\u30e5\u30fc\u65ad\u5b9a\u3092\u907f\u3051\u3001\u516c\u5f0f\u60c5\u5831\u30fb\u516c\u958b\u60c5\u5831\u30fb\u65e2\u5b58\u53e3\u30b3\u30df\u306e\u50be\u5411\u3092\u6574\u7406\u3059\u308b\u8abf\u67fb\u8a18\u4e8b\u3068\u3057\u3066\u69cb\u6210\u3059\u308b\u3002",
            "- \u4f53\u9a13\u8ac7\u98a8\u306e\u65ad\u5b9a\u8868\u73fe\u306f\u4f7f\u308f\u305a\u3001\u78ba\u8a8d\u6e08\u307f\u60c5\u5831\u3068\u672a\u78ba\u8a8d\u60c5\u5831\u3092\u5206\u3051\u308b\u3002",
        ]
        cta_policy = "- \u5546\u54c1\u7d39\u4ecbCTA\u3068\u30b5\u30fc\u30d3\u30b9\u7533\u8fbcCTA\u3092\u5206\u3051\u3001\u8a2d\u5b9a\u624b\u9806\u5f8c\u3068\u6bd4\u8f03\u30fb\u6ce8\u610f\u70b9\u5f8c\u306b\u5019\u88dc\u3068\u3057\u3066\u914d\u7f6e\u3059\u308b\u3002"
        internal_links = [
            "- \u30e2\u30d0\u30a4\u30ebWiFi\u3001povo\u3001\u30eb\u30fc\u30bf\u30fc\u8a2d\u5b9a\u3001\u901a\u4fe1\u30c8\u30e9\u30d6\u30eb\u5bfe\u7b56\u306e\u8a18\u4e8b\u304c\u3042\u308c\u3070\u5185\u90e8\u30ea\u30f3\u30af\u5019\u88dc\u306b\u3059\u308b\u3002",
            "- \u307e\u3060\u95a2\u9023\u8a18\u4e8b\u304c\u306a\u3044\u5834\u5408\u306f\u3001\u672c\u6587\u751f\u6210\u524d\u306b\u95a2\u9023\u5019\u88dc\u3092\u78ba\u8a8d\u3059\u308b\u3002",
        ]
        expression_notes = [
            "- \u5b9f\u4f53\u9a13\u304c\u306a\u3044\u5834\u5408\u306f\u300e\u4f7f\u3063\u3066\u308f\u304b\u3063\u305f\u300f\u306a\u3069\u306e\u4f53\u9a13\u65ad\u5b9a\u3092\u907f\u3051\u308b\u3002",
            "- \u4fa1\u683c\u3001\u5728\u5eab\u3001\u30ad\u30e3\u30f3\u30da\u30fc\u30f3\u3001\u901a\u4fe1\u54c1\u8cea\u3001\u4fdd\u8a3c\u5185\u5bb9\u306f\u5909\u52d5\u3059\u308b\u305f\u3081\u65ad\u5b9a\u3057\u306a\u3044\u3002",
            "- \u901a\u4fe1\u3001\u5951\u7d04\u3001\u4fdd\u8a3c\u3001\u4e92\u63db\u6027\u306f\u516c\u5f0f\u60c5\u5831\u306e\u78ba\u8a8d\u3092\u4fc3\u3059\u3002",
        ]

    lines = [
        f"# Outline: {title}",
        "",
        "## \u8a18\u4e8b\u30bf\u30a4\u30c8\u30eb",
        f"- {title}",
        "",
        "## \u5bfe\u8c61\u30ad\u30fc\u30ef\u30fc\u30c9",
        f"- {keyword}",
        "",
        "## \u691c\u7d22\u610f\u56f3",
        search_intent,
        "",
        "## \u60f3\u5b9a\u8aad\u8005",
        audience,
        "",
        "## \u8a18\u4e8b\u30bf\u30a4\u30d7",
        f"- {article_type}",
        "",
        "## \u5b9f\u4f53\u9a13\u304c\u5fc5\u8981\u304b",
        "- no",
        "",
        "## \u5b9f\u4f53\u9a13\u304c\u306a\u3044\u5834\u5408\u306e\u4ee3\u66ff\u65b9\u91dd",
        *no_experience_lines,
        "",
        "## H2/H3\u69cb\u6210\u6848",
    ]
    for h2, h3s in sections:
        lines.append(f"- {h2}")
        for h3 in h3s:
            lines.append(f"  - {h3}")

    lines.extend([
        "",
        "## CTA\u65b9\u91dd",
        cta_policy,
        "",
        "## \u7d39\u4ecb\u5019\u88dc\u5546\u54c1",
        *format_product_list(products),
        "",
        "## \u7d39\u4ecb\u5019\u88dc\u6848\u4ef6",
        *format_offer_list(matched_offers),
        "",
        "## \u5185\u90e8\u30ea\u30f3\u30af\u5019\u88dc\u30e1\u30e2",
        *internal_links,
        "",
        "## \u6ce8\u610f\u3059\u3079\u304d\u8868\u73fe",
        *expression_notes,
        "",
        "## \u672c\u6587\u751f\u6210\u524d\u306e\u78ba\u8a8d\u4e8b\u9805",
        f"- queue_id: {queue_id}",
        f"- editor_score: {score_row.get('editor_score', '')}",
        f"- review_required: {score_row.get('review_required', '')}",
        f"- queue notes: {queue_row.get('notes', '')}",
        f"- score reasons: {score_row.get('reasons', '')}",
        "- \u5546\u54c1\u30fb\u6848\u4ef6\u30ea\u30f3\u30af\u306e\u6709\u52b9\u6027\u3092\u78ba\u8a8d\u3059\u308b\u3002",
        "- \u3053\u306e\u5de5\u7a0b\u3067\u306f\u672c\u6587\u751f\u6210\u3092\u307e\u3060\u884c\u308f\u306a\u3044\u3002",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate outline markdown files for write_now article queue items.")
    parser.add_argument("--queue-id", help="Generate an outline for one queue_id instead of the default target set.")
    args = parser.parse_args()
    target_queue_ids = {args.queue_id} if args.queue_id else TARGET_QUEUE_IDS

    editor_columns, editor_rows = read_csv(EDITOR_REPORT_CSV)
    queue_columns, queue_rows = read_csv(QUEUE_CSV)
    product_columns, product_rows = read_csv(PRODUCTS_CSV)
    offer_columns, offer_rows = read_csv(OFFERS_CSV)

    require_columns("editor_score_report.csv", editor_columns, EDITOR_REQUIRED_COLUMNS)
    require_columns("article_queue.csv", queue_columns, QUEUE_REQUIRED_COLUMNS)
    require_columns("products.csv", product_columns, PRODUCT_REQUIRED_COLUMNS)
    require_columns("offers.csv", offer_columns, OFFER_REQUIRED_COLUMNS)

    queue_by_id = {row.get("queue_id", ""): row for row in queue_rows if row.get("queue_id", "")}
    products_by_id = {row.get("product_id", ""): row for row in product_rows if row.get("product_id", "")}
    targets = [row for row in editor_rows if row.get("decision", "").strip() == "write_now" and row.get("queue_id", "") in target_queue_ids]

    OUTLINE_DIR.mkdir(parents=True, exist_ok=True)
    generated: list[tuple[str, Path]] = []
    skipped: list[str] = []

    for target in targets:
        queue_id = target.get("queue_id", "")
        queue_row = queue_by_id.get(queue_id)
        if not queue_row:
            skipped.append(f"{queue_id}: missing article_queue row")
            continue
        outline = build_outline(target, queue_row, products_by_id, offer_rows)
        output_path = OUTLINE_DIR / f"{safe_file_stem(queue_id)}_outline.md"
        output_path.write_text(outline, encoding="utf-8")
        generated.append((queue_id, output_path))

    report_lines = ["# Outline Report", "", f"Generated outlines: {len(generated)}", "", "## Generated", ""]
    if generated:
        for queue_id, path in generated:
            report_lines.append(f"- {queue_id}: {path.relative_to(ROOT).as_posix()}")
    else:
        report_lines.append("- none")

    report_lines.extend(["", "## Skipped", ""])
    if skipped:
        report_lines.extend(f"- {item}" for item in skipped)
    else:
        report_lines.append("- none")

    OUTLINE_REPORT_MD.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"generated={len(generated)} report={OUTLINE_REPORT_MD}")
    for queue_id, path in generated:
        print(f"{queue_id}\t{path}")


if __name__ == "__main__":
    main()
