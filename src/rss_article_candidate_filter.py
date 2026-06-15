from __future__ import annotations

import csv
import datetime as dt
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"

SCORE_REPORT_PATH = OUTPUT_DIR / "rss_candidate_score_report.csv"
PRODUCTS_PATH = DATA_DIR / "products.csv"
OFFERS_PATH = DATA_DIR / "offers.csv"
ARTICLES_PATH = DATA_DIR / "articles.csv"
INVENTORY_PATH = OUTPUT_DIR / "article_inventory_report.csv"

OUT_CSV_PATH = OUTPUT_DIR / "rss_article_candidates.csv"
OUT_MD_PATH = OUTPUT_DIR / "rss_article_candidates.md"

OUT_FIELDS = [
    "candidate_rank",
    "item_id",
    "source_name",
    "category",
    "title",
    "candidate_title",
    "article_type",
    "url",
    "published_at",
    "score",
    "filter_decision",
    "product_hint",
    "existing_article_hint",
    "reason",
]

MAX_READY = 20

STRONG_INTENT = [
    "セール",
    "値下げ",
    "お買い得",
    "割引",
    "クーポン",
    "発売",
    "予約",
    "新製品",
    "レビュー",
    "比較",
    "おすすめ",
    "どっち",
    "Amazon",
    "楽天",
]

PRODUCT_CATEGORIES = [
    "スマホ",
    "モバイル",
    "モバイル回線",
    "SIM",
    "Wi-Fi",
    "WiFi",
    "ルーター",
    "ポータブル電源",
    "バッテリー",
    "PC",
    "周辺機器",
    "USB",
    "SSD",
    "家電",
    "ガジェット",
    "イヤホン",
    "ヘッドホン",
    "モニター",
    "充電器",
    "防災",
    "カメラ",
    "ウォッチ",
    "プロジェクター",
]

NEGATIVE_TOPICS = [
    "政治",
    "規制",
    "輸出",
    "輸出規制",
    "決算",
    "業績",
    "株価",
    "人事",
    "事件",
    "訴訟",
    "政府",
]

AI_TOOL_WORDS = [
    "ChatGPT",
    "Claude",
    "Gemini",
    "Copilot",
    "生成AI",
    "AIツール",
    "料金",
    "使い方",
    "新モデル",
    "比較",
    "API",
]

WEAK_HINTS = {"pro", "plus", "ai", "max", "mini", "ultra", "new", "pc", "usb"}

PRODUCTISH_PATTERNS = [
    re.compile(r"\b[A-Z][A-Za-z0-9+-]{2,}\b"),
    re.compile(r"[A-Za-z]+[\s-]?[0-9][A-Za-z0-9+-]*"),
    re.compile(r"(第\d+世代|[0-9]+GB|[0-9]+TB|[0-9]+W|[0-9]+mAh|[0-9]+Wh|[0-9]+型)"),
]


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            return [{k: (v or "") for k, v in row.items()} for row in reader]
    except OSError:
        return []


def write_csv_rows(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def contains_any(text: str, words: list[str]) -> list[str]:
    lower = text.lower()
    return [word for word in words if word.lower() in lower]


def clean_product_hint(value: str) -> str:
    parts = [part.strip() for part in re.split(r"[,/|、]+", value or "") if part.strip()]
    useful = []
    for part in parts:
        normalized = part.lower()
        if normalized in WEAK_HINTS:
            continue
        if len(part) <= 2 and not re.search(r"\d", part):
            continue
        useful.append(part)
    return ", ".join(dict.fromkeys(useful))


def has_productish(text: str) -> bool:
    return any(pattern.search(text) for pattern in PRODUCTISH_PATTERNS)


def collect_terms(rows: list[dict[str, str]], keys: list[str]) -> list[str]:
    terms = []
    for row in rows:
        for key in keys:
            value = row.get(key, "")
            if not value:
                continue
            for part in re.split(r"[,/|、\s]+", value):
                part = part.strip()
                if len(part) >= 3 and part.lower() not in WEAK_HINTS:
                    terms.append(part)
    return list(dict.fromkeys(terms))[:500]


def match_terms(text: str, terms: list[str], limit: int = 3) -> list[str]:
    lower = text.lower()
    matched = []
    for term in terms:
        if term.lower() in lower:
            matched.append(term)
        if len(matched) >= limit:
            break
    return matched


def load_reference_terms() -> tuple[list[str], list[str]]:
    product_terms = collect_terms(
        read_csv_rows(PRODUCTS_PATH),
        ["name", "product_name", "category", "tags", "product_id"],
    )
    offer_terms = collect_terms(
        read_csv_rows(OFFERS_PATH),
        ["platform", "product_id", "offer_name", "name", "notes"],
    )
    return product_terms, offer_terms


def load_existing_titles() -> list[str]:
    titles = []
    for path, keys in [
        (ARTICLES_PATH, ["article_title", "title", "keyword", "slug"]),
        (INVENTORY_PATH, ["title", "slug", "category"]),
    ]:
        for row in read_csv_rows(path):
            for key in keys:
                value = row.get(key, "")
                if value:
                    titles.append(value)
                    break
    return titles


def token_set(text: str) -> set[str]:
    parts = re.split(r"[^0-9a-zA-Zぁ-んァ-ヶ一-龠]+", (text or "").lower())
    return {part for part in parts if len(part) >= 2}


def find_existing_hint(text: str, fallback_hint: str, existing_titles: list[str]) -> str:
    if fallback_hint:
        return fallback_hint
    source_tokens = token_set(text)
    scored = []
    for title in existing_titles:
        overlap = len(source_tokens & token_set(title))
        if overlap >= 2:
            scored.append((overlap, title))
    if not scored:
        return ""
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored[0][1]


def guess_article_type(text: str, existing_hint: str) -> str:
    if existing_hint:
        return "rewrite"
    if contains_any(text, ["セール", "値下げ", "お買い得", "割引", "クーポン", "予約"]):
        return "deal"
    if contains_any(text, ["比較", "どっち"]):
        return "comparison"
    if contains_any(text, ["使い方", "設定", "方法", "料金"]):
        return "howto"
    if contains_any(text, ["レビュー", "おすすめ", "新製品", "発売"]):
        return "review"
    return "news_to_affiliate"


def make_candidate_title(title: str, article_type: str) -> str:
    base = re.sub(r"^【[^】]+】", "", title or "").strip()
    base = re.sub(r"\s+", " ", base)
    if len(base) > 58:
        base = base[:58].rstrip() + "…"
    if article_type == "deal":
        return f"{base}は買い？セール価格と注意点を整理"
    if article_type == "comparison":
        return f"{base}を比較検討する前に見るポイント"
    if article_type == "howto":
        return f"{base}の使い方・料金・注意点まとめ"
    if article_type == "rewrite":
        return f"{base}の最新情報と既存記事への追記ポイント"
    if article_type == "review":
        return f"{base}はおすすめ？特徴と向いている人を整理"
    return f"{base}を記事化するなら？収益導線と選び方を整理"


def is_ai_news(text: str) -> bool:
    return bool(contains_any(text, ["AI", "Claude", "Gemini", "ChatGPT", "LLM", "Copilot"]))


def ai_can_affiliate(text: str) -> bool:
    return bool(contains_any(text, AI_TOOL_WORDS)) and bool(
        contains_any(text, ["料金", "使い方", "比較", "新モデル", "ツール", "API", "プラン", "活用"])
    )


def evaluate_row(
    row: dict[str, str],
    product_terms: list[str],
    offer_terms: list[str],
    existing_titles: list[str],
) -> dict[str, str]:
    title = row.get("title", "")
    text = " ".join([title, row.get("category", ""), row.get("matched_keywords", ""), row.get("reason", "")])
    score = int(row.get("score", "0") or 0)
    raw_product_hint = row.get("product_hint", "")
    product_hint = clean_product_hint(raw_product_hint)
    ref_matches = match_terms(text, product_terms + offer_terms)
    if ref_matches:
        product_hint = ", ".join(dict.fromkeys([part for part in [product_hint, ", ".join(ref_matches)] if part]))

    intent_matches = contains_any(text, STRONG_INTENT)
    category_matches = contains_any(text, PRODUCT_CATEGORIES)
    negative_matches = contains_any(text, NEGATIVE_TOPICS)
    existing_hint = find_existing_hint(text, row.get("existing_article_hint", ""), existing_titles)
    product_clear = bool(product_hint) or has_productish(title) or bool(category_matches)
    title_possible = bool(title.strip())
    monetization_possible = bool(intent_matches) or bool(product_hint) or bool(
        contains_any(text, ["Amazon", "楽天", "セール", "発売", "レビュー", "比較", "おすすめ"])
    )
    article_type = guess_article_type(text, existing_hint)
    candidate_title = make_candidate_title(title, article_type)

    reasons = []
    if existing_hint:
        decision = "rewrite_candidate"
        reasons.append("既存記事と近くリライト/追記候補")
    elif negative_matches:
        decision = "reject"
        reasons.append("政治/規制/企業ニュース寄り")
    elif is_ai_news(text) and not ai_can_affiliate(text):
        decision = "hold"
        reasons.append("AIニュースだが商品/使い方/料金記事に落としにくい")
    elif not product_clear:
        decision = "hold"
        reasons.append("商品名または商品カテゴリが弱い")
    elif not title_possible:
        decision = "hold"
        reasons.append("記事タイトル案が作れない")
    elif not monetization_possible:
        decision = "hold"
        reasons.append("収益導線が弱い")
    elif score >= 70:
        decision = "ready_for_queue"
        reasons.append("商品/カテゴリ/収益導線が明確")
    else:
        decision = "hold"
        reasons.append("スコア不足")

    if intent_matches:
        reasons.append("intent=" + ",".join(intent_matches[:4]))
    if category_matches:
        reasons.append("category=" + ",".join(category_matches[:4]))
    if product_hint:
        reasons.append("product_hint=" + product_hint)

    return {
        "candidate_rank": "",
        "item_id": row.get("item_id", ""),
        "source_name": row.get("source_name", ""),
        "category": row.get("category", ""),
        "title": title,
        "candidate_title": candidate_title,
        "article_type": article_type,
        "url": row.get("url", ""),
        "published_at": row.get("published_at", ""),
        "score": str(score),
        "filter_decision": decision,
        "product_hint": product_hint,
        "existing_article_hint": existing_hint,
        "reason": "; ".join(reasons),
    }


def write_markdown(rows: list[dict[str, str]]) -> None:
    counts = {key: 0 for key in ["ready_for_queue", "rewrite_candidate", "hold", "reject"]}
    for row in rows:
        counts[row["filter_decision"]] = counts.get(row["filter_decision"], 0) + 1

    ready = [row for row in rows if row["filter_decision"] == "ready_for_queue"][:10]
    rewrites = [row for row in rows if row["filter_decision"] == "rewrite_candidate"][:5]
    holds = [row for row in rows if row["filter_decision"] == "hold"][:5]

    lines = [
        "# RSS Article Candidates",
        "",
        f"Generated: {now_iso()}",
        "",
        "## Summary",
        "",
        f"- ready_for_queue: {counts.get('ready_for_queue', 0)}",
        f"- rewrite_candidate: {counts.get('rewrite_candidate', 0)}",
        f"- hold: {counts.get('hold', 0)}",
        f"- reject: {counts.get('reject', 0)}",
        "",
        "## Ready For Queue Top 10",
        "",
    ]
    if ready:
        for row in ready:
            lines.append(f"- #{row['candidate_rank']} score {row['score']}: {row['candidate_title']} ({row['reason']})")
    else:
        lines.append("- none")

    lines.extend(["", "## Rewrite Candidate Top 5", ""])
    if rewrites:
        for row in rewrites:
            lines.append(f"- score {row['score']}: {row['candidate_title']} -> {row['existing_article_hint']}")
    else:
        lines.append("- none")

    lines.extend(["", "## Hold Examples", ""])
    if holds:
        for row in holds:
            lines.append(f"- score {row['score']}: {row['title']} ({row['reason']})")
    else:
        lines.append("- none")

    OUT_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    rows = [row for row in read_csv_rows(SCORE_REPORT_PATH) if row.get("decision") == "article_candidate"]
    product_terms, offer_terms = load_reference_terms()
    existing_titles = load_existing_titles()

    filtered = [evaluate_row(row, product_terms, offer_terms, existing_titles) for row in rows]
    filtered.sort(key=lambda row: (-int(row["score"]), row["filter_decision"], row["title"]))

    ready_rows = [row for row in filtered if row["filter_decision"] == "ready_for_queue"]
    for index, row in enumerate(ready_rows, start=1):
        if index <= MAX_READY:
            row["candidate_rank"] = str(index)
        else:
            row["filter_decision"] = "hold"
            row["candidate_rank"] = ""
            row["reason"] = "ready_for_queue上限超過のためhold; " + row["reason"]

    filtered.sort(
        key=lambda row: (
            {"ready_for_queue": 0, "rewrite_candidate": 1, "hold": 2, "reject": 3}.get(row["filter_decision"], 9),
            int(row["candidate_rank"] or "9999"),
            -int(row["score"]),
            row["title"],
        )
    )

    write_csv_rows(OUT_CSV_PATH, OUT_FIELDS, filtered)
    write_markdown(filtered)

    counts = {key: 0 for key in ["ready_for_queue", "rewrite_candidate", "hold", "reject"]}
    for row in filtered:
        counts[row["filter_decision"]] = counts.get(row["filter_decision"], 0) + 1

    print(f"ready_for_queue={counts.get('ready_for_queue', 0)}")
    print(f"rewrite_candidate={counts.get('rewrite_candidate', 0)}")
    print(f"hold={counts.get('hold', 0)}")
    print(f"reject={counts.get('reject', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
