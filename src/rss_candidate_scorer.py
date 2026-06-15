from __future__ import annotations

import csv
import datetime as dt
from email.utils import parsedate_to_datetime
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"

RSS_ITEMS_PATH = DATA_DIR / "rss_items.csv"
RSS_SOURCES_PATH = DATA_DIR / "rss_sources.csv"
PRODUCTS_PATH = DATA_DIR / "products.csv"
OFFERS_PATH = DATA_DIR / "offers.csv"
ARTICLES_PATH = DATA_DIR / "articles.csv"
INVENTORY_PATH = OUTPUT_DIR / "article_inventory_report.csv"

REPORT_CSV_PATH = OUTPUT_DIR / "rss_candidate_score_report.csv"
REPORT_MD_PATH = OUTPUT_DIR / "rss_candidate_score_report.md"

REPORT_FIELDS = [
    "item_id",
    "source_name",
    "category",
    "title",
    "url",
    "published_at",
    "score",
    "decision",
    "matched_keywords",
    "product_hint",
    "existing_article_hint",
    "reason",
]


TOPIC_KEYWORDS = {
    "ガジェット": 20,
    "家電": 20,
    "通信": 20,
    "スマホ": 20,
    "PC": 20,
    "パソコン": 20,
    "周辺機器": 20,
    "モバイル": 20,
    "Wi-Fi": 20,
    "WiFi": 20,
    "ルーター": 20,
    "防災": 20,
    "生活用品": 20,
    "ポータブル電源": 20,
    "バッテリー": 20,
}

MONETIZE_KEYWORDS = {
    "Amazon": 15,
    "楽天": 15,
    "セール": 15,
    "値下げ": 15,
    "お買い得": 15,
    "新製品": 15,
    "発売": 15,
    "比較": 15,
    "レビュー": 15,
    "おすすめ": 15,
    "割引": 15,
    "クーポン": 15,
}

NICHE_KEYWORDS = {
    "AI": 10,
    "スマホ": 10,
    "USB": 10,
    "SSD": 10,
    "モニター": 10,
    "キーボード": 10,
    "マウス": 10,
    "充電器": 10,
    "ポータブル電源": 10,
    "モバイル通信": 10,
    "SIM": 10,
    "povo": 10,
    "Wi-Fi": 10,
    "WiFi": 10,
}

NEGATIVE_STRONG = {
    "決算": -30,
    "業績": -30,
    "株価": -30,
    "政治": -30,
    "規制": -30,
    "訴訟": -30,
    "事件": -30,
    "逮捕": -30,
    "政府": -30,
    "輸出規制": -30,
}

NEGATIVE_WEAK = {
    "発表会": -20,
    "調査": -20,
    "方針": -20,
    "提携": -20,
    "買収": -20,
    "人事": -20,
    "サービス終了": -20,
}

PRODUCTISH_PATTERNS = [
    re.compile(r"\b[A-Z][A-Za-z0-9+-]{2,}\b"),
    re.compile(r"[A-Za-z]+[\s-]?[0-9][A-Za-z0-9+-]*"),
    re.compile(r"(第\d+世代|[0-9]+GB|[0-9]+TB|[0-9]+W|[0-9]+mAh|[0-9]+Wh)"),
]


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [{k: (v or "") for k, v in row.items()} for row in reader]


def write_csv_rows(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def token_set(text: str) -> set[str]:
    text = (text or "").lower()
    parts = re.split(r"[^0-9a-zA-Zぁ-んァ-ヶ一-龠]+", text)
    return {part for part in parts if len(part) >= 2}


def parse_priority(value: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 3


def source_priorities() -> dict[str, int]:
    priorities = {}
    for row in read_csv_rows(RSS_SOURCES_PATH):
        source_name = row.get("source_name", "")
        if source_name:
            priorities[source_name] = parse_priority(row.get("priority", ""))
    return priorities


def collect_hint_terms(rows: list[dict[str, str]], preferred_keys: list[str]) -> list[str]:
    terms: list[str] = []
    for row in rows:
        for key in preferred_keys:
            value = row.get(key, "")
            if value:
                terms.extend(part for part in re.split(r"[,/|、\s]+", value) if len(part) >= 2)
    seen = set()
    clean_terms = []
    for term in terms:
        key = term.lower()
        if key not in seen:
            seen.add(key)
            clean_terms.append(term)
    return clean_terms[:500]


def load_product_terms() -> list[str]:
    product_rows = read_csv_rows(PRODUCTS_PATH)
    return collect_hint_terms(product_rows, ["name", "product_name", "category", "tags", "product_id"])


def load_offer_terms() -> list[str]:
    offer_rows = read_csv_rows(OFFERS_PATH)
    return collect_hint_terms(offer_rows, ["platform", "product_id", "offer_name", "name", "notes"])


def load_existing_article_terms() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for path, title_keys in [
        (ARTICLES_PATH, ["article_title", "title", "keyword", "queue_id"]),
        (INVENTORY_PATH, ["title", "slug", "category"]),
    ]:
        for row in read_csv_rows(path):
            label = ""
            for key in title_keys:
                if row.get(key):
                    label = row[key]
                    break
            text = " ".join(row.get(key, "") for key in title_keys)
            if label and text:
                pairs.append((label, text))
    return pairs


def match_terms(text: str, terms: list[str], limit: int = 3) -> list[str]:
    lower = text.lower()
    matches = []
    for term in terms:
        clean = term.strip()
        if len(clean) < 2:
            continue
        if clean.lower() in lower:
            matches.append(clean)
        if len(matches) >= limit:
            break
    return matches


def existing_article_hint(text: str, existing: list[tuple[str, str]]) -> str:
    item_tokens = token_set(text)
    scored = []
    for label, target_text in existing:
        target_tokens = token_set(target_text)
        overlap = len(item_tokens & target_tokens)
        if overlap >= 2:
            scored.append((overlap, label))
    if not scored:
        return ""
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return scored[0][1]


def has_productish_word(text: str) -> bool:
    return any(pattern.search(text) for pattern in PRODUCTISH_PATTERNS)


def add_keyword_scores(text: str, keywords: dict[str, int]) -> tuple[int, list[str], list[str]]:
    score = 0
    matched = []
    reasons = []
    lower = text.lower()
    for keyword, points in keywords.items():
        if keyword.lower() in lower:
            score += points
            matched.append(keyword)
            reasons.append(f"{keyword}:{points:+d}")
    return score, matched, reasons


def score_item(
    item: dict[str, str],
    product_terms: list[str],
    offer_terms: list[str],
    existing_terms: list[tuple[str, str]],
    priorities: dict[str, int],
) -> dict[str, str]:
    text = " ".join(
        [
            item.get("title", ""),
            item.get("summary", ""),
            item.get("category", ""),
            item.get("source_name", ""),
        ]
    )
    score = 0
    matched_keywords: list[str] = []
    reasons: list[str] = []

    for keyword_map in [TOPIC_KEYWORDS, MONETIZE_KEYWORDS, NICHE_KEYWORDS, NEGATIVE_STRONG, NEGATIVE_WEAK]:
        points, matched, point_reasons = add_keyword_scores(text, keyword_map)
        score += points
        matched_keywords.extend(matched)
        reasons.extend(point_reasons)

    if has_productish_word(item.get("title", "")):
        score += 20
        matched_keywords.append("商品名らしき語")
        reasons.append("productish_title:+20")

    category = item.get("category", "").lower()
    if any(term in category for term in ["pc", "ガジェット", "家電", "生活", "通信", "スマホ"]):
        score += 15
        matched_keywords.append("既存カテゴリ適性")
        reasons.append("category_fit:+15")

    product_matches = match_terms(text, product_terms)
    offer_matches = match_terms(text, offer_terms)
    product_hint = ", ".join(product_matches + offer_matches)
    if product_hint:
        score += 10
        matched_keywords.append("商品/案件関連")
        reasons.append("product_or_offer_hint:+10")

    article_hint = existing_article_hint(text, existing_terms)
    if article_hint:
        score += 10
        matched_keywords.append("既存記事関連")
        reasons.append("existing_article_related:+10")

    if score < 0:
        score = 0

    has_monetize_path = bool(product_hint) or any(
        keyword in matched_keywords
        for keyword in ["Amazon", "楽天", "セール", "値下げ", "お買い得", "新製品", "発売", "比較", "レビュー", "おすすめ"]
    )
    has_topic_path = any(
        keyword in matched_keywords
        for keyword in ["ガジェット", "家電", "通信", "スマホ", "PC", "パソコン", "周辺機器", "モバイル", "防災", "生活用品", "ポータブル電源", "既存カテゴリ適性"]
    )

    if score >= 70 and has_monetize_path and has_topic_path:
        decision = "article_candidate"
    elif score >= 45:
        decision = "maybe"
    else:
        decision = "ignore"

    # Keep article_candidate tighter, but keep maybe broad for exploration.
    if score >= 70 and decision != "article_candidate":
        decision = "maybe"

    return {
        "item_id": item.get("item_id", ""),
        "source_name": item.get("source_name", ""),
        "category": item.get("category", ""),
        "title": item.get("title", ""),
        "url": item.get("url", ""),
        "published_at": item.get("published_at", ""),
        "score": str(score),
        "decision": decision,
        "matched_keywords": ", ".join(dict.fromkeys(matched_keywords)),
        "product_hint": product_hint,
        "existing_article_hint": article_hint,
        "reason": "; ".join(reasons) if reasons else "no scoring signals",
    }


def published_timestamp(value: str) -> float:
    if not value:
        return 0.0
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError, IndexError, OverflowError):
        return 0.0


def write_markdown_report(rows: list[dict[str, str]]) -> None:
    counts = {"article_candidate": 0, "maybe": 0, "ignore": 0}
    for row in rows:
        counts[row["decision"]] = counts.get(row["decision"], 0) + 1

    top_rows = rows[:10]
    lines = [
        "# RSS Candidate Score Report",
        "",
        f"Generated: {utc_now_iso()}",
        "",
        "## Summary",
        "",
        f"- total: {len(rows)}",
        f"- article_candidate: {counts.get('article_candidate', 0)}",
        f"- maybe: {counts.get('maybe', 0)}",
        f"- ignore: {counts.get('ignore', 0)}",
        "",
        "## Top 10",
        "",
        "| score | decision | source | title | matched_keywords | product_hint | existing_article_hint |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in top_rows:
        title = row["title"].replace("|", "\\|")
        matched = row["matched_keywords"].replace("|", "\\|")
        product = row["product_hint"].replace("|", "\\|")
        existing = row["existing_article_hint"].replace("|", "\\|")
        lines.append(
            f"| {row['score']} | {row['decision']} | {row['source_name']} | "
            f"[{title}]({row['url']}) | {matched} | {product} | {existing} |"
        )

    REPORT_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    OUTPUT_DIR.mkdir(exist_ok=True)
    rss_items = read_csv_rows(RSS_ITEMS_PATH)
    product_terms = load_product_terms()
    offer_terms = load_offer_terms()
    existing_terms = load_existing_article_terms()
    priorities = source_priorities()

    scored = [
        score_item(item, product_terms, offer_terms, existing_terms, priorities)
        for item in rss_items
    ]
    scored.sort(
        key=lambda row: (
            -int(row["score"]),
            priorities.get(row["source_name"], 3),
            -published_timestamp(row.get("published_at", "")),
        )
    )

    write_csv_rows(REPORT_CSV_PATH, REPORT_FIELDS, scored)
    write_markdown_report(scored)

    counts = {"article_candidate": 0, "maybe": 0, "ignore": 0}
    for row in scored:
        counts[row["decision"]] = counts.get(row["decision"], 0) + 1

    print(f"total={len(scored)}")
    print(f"article_candidate={counts.get('article_candidate', 0)}")
    print(f"maybe={counts.get('maybe', 0)}")
    print(f"ignore={counts.get('ignore', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
