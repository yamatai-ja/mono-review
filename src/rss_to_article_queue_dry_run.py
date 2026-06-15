from __future__ import annotations

import csv
import datetime as dt
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"

REFINED_PATH = OUTPUT_DIR / "rss_article_candidates_refined.csv"
ARTICLE_QUEUE_PATH = DATA_DIR / "article_queue.csv"
ARTICLES_PATH = DATA_DIR / "articles.csv"
KEYWORDS_PATH = DATA_DIR / "keywords.csv"
PRODUCTS_PATH = DATA_DIR / "products.csv"
OFFERS_PATH = DATA_DIR / "offers.csv"
INVENTORY_PATH = OUTPUT_DIR / "article_inventory_report.csv"

OUT_CSV_PATH = OUTPUT_DIR / "rss_to_article_queue_dry_run.csv"
OUT_MD_PATH = OUTPUT_DIR / "rss_to_article_queue_dry_run.md"

OUT_FIELDS = [
    "candidate_rank",
    "source_item_id",
    "article_title",
    "target_keyword",
    "article_type",
    "priority",
    "status",
    "source_url",
    "original_title",
    "refined_title",
    "duplicate_hint",
    "recommendation",
    "reason",
]

TYPE_MAP = {
    "deal": "seo_article",
    "review": "review",
    "comparison": "comparison",
    "howto": "howto",
    "service_explain": "seo_article",
    "news_to_affiliate": "seo_article",
    "rewrite": "rewrite",
}

GENERIC_KEYWORDS = {
    "スマホ セール",
    "スマホ",
    "PC",
    "AI",
    "Pro",
    "Plus",
    "USB",
    "ガジェット",
}

PRODUCTISH_PATTERNS = [
    re.compile(r"\b[A-Z][A-Za-z0-9+-]{2,}(?:\s+[A-Z0-9][A-Za-z0-9+-]{1,}){0,3}\b"),
    re.compile(r"(第\d+世代|[0-9]+GB|[0-9]+TB|[0-9]+W|[0-9]+mAh|[0-9]+Wh|[0-9]+型)"),
    re.compile(r"(Jackery|motorola|Xiaomi|MOTTERU|Polar Pacer|JAPANNEXT|PHILIPS|COK-N220KM|arrows We3)", re.I),
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


def next_queue_id(existing_rows: list[dict[str, str]]) -> str:
    max_num = 0
    for row in existing_rows:
        queue_id = row.get("queue_id", "")
        match = re.match(r"q(\d+)$", queue_id)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f"q{max_num + 1:06d}"


def collect_duplicate_texts() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    sources = [
        (ARTICLE_QUEUE_PATH, ["keyword", "article_title", "notes"]),
        (ARTICLES_PATH, ["keyword", "title", "article_title", "slug"]),
        (KEYWORDS_PATH, ["keyword", "topic_cluster", "notes"]),
        (INVENTORY_PATH, ["title", "slug", "category"]),
    ]
    for path, keys in sources:
        for row in read_csv_rows(path):
            label = ""
            parts = []
            for key in keys:
                value = row.get(key, "")
                if value:
                    parts.append(value)
                    if not label:
                        label = value
            if label and parts:
                pairs.append((label, " ".join(parts)))
    return pairs


def token_set(text: str) -> set[str]:
    parts = re.split(r"[^0-9a-zA-Zぁ-んァ-ヶ一-龠]+", (text or "").lower())
    return {part for part in parts if len(part) >= 2}


def duplicate_hint(text: str, duplicates: list[tuple[str, str]]) -> str:
    source_tokens = token_set(text)
    scored = []
    for label, target in duplicates:
        overlap = len(source_tokens & token_set(target))
        if overlap >= 2:
            scored.append((overlap, label))
    if not scored:
        return ""
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored[0][1]


def has_productish(value: str) -> bool:
    return any(pattern.search(value or "") for pattern in PRODUCTISH_PATTERNS)


def is_generic_keyword(keyword: str) -> bool:
    return (keyword or "").strip() in GENERIC_KEYWORDS or len((keyword or "").strip()) < 4


def is_short_term(row: dict[str, str]) -> bool:
    text = " ".join([row.get("original_title", ""), row.get("refined_title", ""), row.get("search_intent", "")])
    return any(word in text for word in ["セール", "値下げ", "お買い得", "割引", "クーポン"])


def is_long_term(row: dict[str, str]) -> bool:
    text = " ".join([row.get("refined_title", ""), row.get("target_keyword", ""), row.get("search_intent", "")])
    return any(word in text for word in ["注意点", "特徴", "選び方", "比較", "使い方", "料金", "確認", "向け"])


def calc_priority(row: dict[str, str], dup_hint: str) -> tuple[int, list[str]]:
    priority = int(row.get("score", "0") or 0)
    reasons = [f"base_score={priority}"]
    keyword = row.get("target_keyword", "")
    title = row.get("refined_title", "")

    if has_productish(keyword) or has_productish(title):
        priority += 20
        reasons.append("商品名/型番が明確:+20")
    if any(word in " ".join(row.values()) for word in ["Amazon", "楽天", "セール", "予約", "発売"]):
        priority += 20
        reasons.append("商品導線あり:+20")
    if is_short_term(row):
        priority -= 10
        reasons.append("短期セール寄り:-10")
    if is_long_term(row):
        priority += 20
        reasons.append("長期SEO化しやすい:+20")
    if dup_hint:
        reasons.append("既存記事に近い")
    if is_generic_keyword(keyword):
        priority -= 20
        reasons.append("target_keywordが汎用的:-20")
    if len(title) < 18:
        priority -= 10
        reasons.append("titleが短い/抽象的:-10")
    return max(priority, 0), reasons


def clean_article_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title or "").strip()
    title = title.replace("には買い？", "は買い？")
    return title


def make_candidate_row(row: dict[str, str], queue_id: str, dup_hint: str) -> dict[str, str]:
    mapped_type = TYPE_MAP.get(row.get("refined_article_type", ""), "seo_article")
    priority, reasons = calc_priority(row, dup_hint)
    keyword = row.get("target_keyword", "")
    article_title = clean_article_title(row.get("refined_title", ""))

    if dup_hint:
        recommendation = "rewrite_existing"
        reasons.append("既存記事に近いためrewrite_existing")
    elif is_generic_keyword(keyword):
        recommendation = "reject"
        reasons.append("target_keywordが汎用的すぎるためreject")
    elif priority >= 140 and is_long_term(row):
        recommendation = "hold"
        reasons.append("add_test_one候補")
    elif priority >= 100:
        recommendation = "hold"
        reasons.append("候補だが初回投入は保留")
    else:
        recommendation = "hold"
        reasons.append("優先度不足のためhold")

    return {
        "candidate_rank": queue_id,
        "source_item_id": row.get("item_id", ""),
        "article_title": article_title,
        "target_keyword": keyword,
        "article_type": mapped_type,
        "priority": str(priority),
        "status": "candidate_from_rss",
        "source_url": row.get("url", ""),
        "original_title": row.get("original_title", ""),
        "refined_title": row.get("refined_title", ""),
        "duplicate_hint": dup_hint,
        "recommendation": recommendation,
        "reason": "; ".join(reasons),
    }


def choose_add_test_one(rows: list[dict[str, str]]) -> None:
    eligible = [
        row for row in rows
        if row["recommendation"] == "hold"
        and "add_test_one候補" in row["reason"]
        and not row["duplicate_hint"]
        and not is_generic_keyword(row["target_keyword"])
    ]
    if not eligible:
        eligible = [
            row for row in rows
            if row["recommendation"] == "hold"
            and not row["duplicate_hint"]
            and not is_generic_keyword(row["target_keyword"])
        ]
    eligible.sort(key=lambda row: (-int(row["priority"]), "セール" in row["article_title"], row["article_title"]))
    if eligible:
        chosen = eligible[0]
        chosen["recommendation"] = "add_test_one"
        chosen["reason"] += "; 初回RSS投入に最適"


def write_markdown(rows: list[dict[str, str]]) -> None:
    counts = {key: 0 for key in ["add_test_one", "hold", "rewrite_existing", "reject"]}
    for row in rows:
        counts[row["recommendation"]] = counts.get(row["recommendation"], 0) + 1

    add_one = [row for row in rows if row["recommendation"] == "add_test_one"]
    holds = [row for row in rows if row["recommendation"] == "hold"][:5]
    rewrites = [row for row in rows if row["recommendation"] == "rewrite_existing"]
    rejects = [row for row in rows if row["recommendation"] == "reject"]

    lines = [
        "# RSS to Article Queue Dry Run",
        "",
        f"Generated: {dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}",
        "",
        "## Summary",
        "",
        f"- add_test_one: {counts.get('add_test_one', 0)}",
        f"- hold: {counts.get('hold', 0)}",
        f"- rewrite_existing: {counts.get('rewrite_existing', 0)}",
        f"- reject: {counts.get('reject', 0)}",
        "",
        "## Add Test One",
        "",
    ]
    if add_one:
        row = add_one[0]
        lines.extend(
            [
                f"- queue_id: {row['candidate_rank']}",
                f"- title: {row['article_title']}",
                f"- keyword: {row['target_keyword']}",
                f"- article_type: {row['article_type']}",
                f"- priority: {row['priority']}",
                f"- source: {row['source_url']}",
                f"- reason: {row['reason']}",
            ]
        )
    else:
        lines.append("- none")

    lines.extend(["", "## Hold Top 5", ""])
    for row in holds:
        lines.append(f"- {row['article_title']} ({row['reason']})")
    if not holds:
        lines.append("- none")

    lines.extend(["", "## Rewrite Existing", ""])
    for row in rewrites:
        lines.append(f"- {row['article_title']} -> {row['duplicate_hint']}")
    if not rewrites:
        lines.append("- none")

    lines.extend(["", "## Reject", ""])
    for row in rejects:
        lines.append(f"- {row['article_title']} ({row['reason']})")
    if not rejects:
        lines.append("- none")

    OUT_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    refined_rows = read_csv_rows(REFINED_PATH)
    duplicates = collect_duplicate_texts()
    existing_queue = read_csv_rows(ARTICLE_QUEUE_PATH)
    next_id = next_queue_id(existing_queue)
    next_number = int(next_id[1:])

    dry_rows = []
    for index, row in enumerate(refined_rows, start=0):
        queue_id = f"q{next_number + index:06d}"
        dup_hint = duplicate_hint(" ".join([row.get("refined_title", ""), row.get("target_keyword", "")]), duplicates)
        dry_rows.append(make_candidate_row(row, queue_id, dup_hint))

    choose_add_test_one(dry_rows)

    dry_rows.sort(
        key=lambda row: (
            {"add_test_one": 0, "hold": 1, "rewrite_existing": 2, "reject": 3}.get(row["recommendation"], 9),
            -int(row["priority"]),
            row["article_title"],
        )
    )

    write_csv_rows(OUT_CSV_PATH, OUT_FIELDS, dry_rows)
    write_markdown(dry_rows)

    counts = {key: 0 for key in ["add_test_one", "hold", "rewrite_existing", "reject"]}
    for row in dry_rows:
        counts[row["recommendation"]] = counts.get(row["recommendation"], 0) + 1
    print(f"add_test_one={counts.get('add_test_one', 0)}")
    print(f"hold={counts.get('hold', 0)}")
    print(f"rewrite_existing={counts.get('rewrite_existing', 0)}")
    print(f"reject={counts.get('reject', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
