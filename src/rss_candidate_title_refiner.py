from __future__ import annotations

import csv
import datetime as dt
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
DATA_DIR = ROOT / "data"

INPUT_PATH = OUTPUT_DIR / "rss_article_candidates.csv"
ARTICLES_PATH = DATA_DIR / "articles.csv"
INVENTORY_PATH = OUTPUT_DIR / "article_inventory_report.csv"
OUT_CSV_PATH = OUTPUT_DIR / "rss_article_candidates_refined.csv"
OUT_MD_PATH = OUTPUT_DIR / "rss_article_candidates_refined.md"

OUT_FIELDS = [
    "candidate_rank",
    "item_id",
    "source_name",
    "category",
    "original_title",
    "candidate_title",
    "refined_title",
    "target_keyword",
    "refined_article_type",
    "search_intent",
    "url",
    "published_at",
    "score",
    "product_hint",
    "existing_article_hint",
    "note",
]

FORBIDDEN = ["最強", "完全", "絶対", "本音レビュー", "実機レビュー", "最安値"]
WEAK_KEYWORDS = {"pro", "plus", "ai", "max", "mini", "ultra", "pc", "usb"}
PRODUCT_PATTERNS = [
    re.compile(r"(Jackery|motorola edge 60|Xiaomi 17T 256GB|MOTTERU|Polar Pacer|JAPANNEXT|PHILIPS 27E1N2600AE／11|PHILIPS 27E1N2600AE/11|arrows We3|COK-N220KM)", re.I),
    re.compile(r"「([^」]{3,40})」"),
    re.compile(r"\b[A-Z][A-Za-z0-9+-]{2,}(?:\s+[A-Z0-9][A-Za-z0-9+-]{1,}){0,3}\b"),
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


def clean_title(title: str) -> str:
    title = re.sub(r"^【[^】]+】", "", title or "").strip()
    title = re.sub(r"\s+", " ", title)
    title = title.replace("！", "").replace("!", "")
    return title


def compact(text: str, limit: int = 28) -> str:
    text = clean_title(text)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def extract_keyword(title: str, product_hint: str, category: str) -> str:
    hint_parts = [part.strip() for part in re.split(r"[,/|、]+", product_hint or "") if part.strip()]
    for part in hint_parts:
        if part.lower() not in WEAK_KEYWORDS and len(part) >= 3:
            return part
    for pattern in PRODUCT_PATTERNS:
        match = pattern.search(title or "")
        if not match:
            continue
        candidate = match.group(1) if match.groups() else match.group(0)
        candidate = candidate.strip("「」 ")
        if candidate.lower() not in WEAK_KEYWORDS and len(candidate) >= 3:
            return candidate
    cleaned = clean_title(title)
    # Fallback to a meaningful phrase, not a one-word weak token.
    if "スマホ" in cleaned:
        return "スマホ セール"
    if "モニター" in cleaned:
        return "モニター セール"
    if "楽天モバイル" in cleaned:
        return "楽天モバイル 補償"
    if category:
        return category.replace("・", " ")
    return compact(cleaned, 18)


def infer_type(original_type: str, title: str, keyword: str) -> str:
    text = f"{title} {keyword}"
    if any(word in text for word in ["料金", "改定", "補償", "月額"]):
        return "service_explain"
    if any(word in text for word in ["セール", "値下げ", "お買い得", "割引", "クーポン", "予約"]):
        return "deal"
    if any(word in text for word in ["比較", "違い", "旧モデル"]):
        return "comparison"
    if any(word in text for word in ["使い方", "設定", "方法"]):
        return "howto"
    if original_type in {"deal", "review", "comparison", "howto", "news_to_affiliate", "rewrite"}:
        return original_type
    return "news_to_affiliate"


def search_intent(article_type: str, title: str) -> str:
    if article_type == "deal":
        return "セール購入判断・注意点確認"
    if article_type == "comparison":
        return "購入前比較・違いの確認"
    if article_type == "howto":
        return "使い方・設定・注意点確認"
    if article_type == "service_explain":
        return "料金変更・サービス内容の確認"
    if article_type == "rewrite":
        return "既存記事の更新・追記判断"
    if article_type == "review":
        return "特徴・向いている人の確認"
    return "ニュースから購入検討への接続"


def title_templates(article_type: str, index: int) -> list[str]:
    deal = [
        "{kw}は買い？セール時の注意点",
        "{kw}のセールは狙い目？選び方を整理",
        "{kw}を安く買う前に見る注意点",
        "{kw}の価格を見る前に確認したいこと",
    ]
    review = [
        "{kw}はおすすめ？特徴と注意点",
        "{kw}はどんな人向け？特徴を整理",
        "{kw}の評判を見る前に知りたいポイント",
    ]
    comparison = [
        "{kw}は何が違う？比較ポイントを整理",
        "{kw}を選ぶ前に見る違いと注意点",
    ]
    howto = [
        "{kw}の使い方と注意点まとめ",
        "{kw}で失敗しない設定・確認ポイント",
    ]
    service = [
        "{kw}は何が変わる？注意点を整理",
        "{kw}で損しないための確認ポイント",
    ]
    news = [
        "{kw}を選ぶ前に知りたい特徴と注意点",
        "{kw}は記事化向き？選び方を整理",
    ]
    mapping = {
        "deal": deal,
        "review": review,
        "comparison": comparison,
        "howto": howto,
        "service_explain": service,
        "rewrite": comparison,
        "news_to_affiliate": news,
    }
    return mapping.get(article_type, news)


def sanitize_title(title: str) -> str:
    for word in FORBIDDEN:
        title = title.replace(word, "")
    title = re.sub(r"\s+", " ", title).strip()
    return title


def refine_title(keyword: str, article_type: str, index: int) -> str:
    templates = title_templates(article_type, index)
    title = templates[(index - 1) % len(templates)].format(kw=keyword)
    return sanitize_title(title)


def is_questionable(title: str, keyword: str) -> bool:
    if any(word in title for word in FORBIDDEN):
        return True
    if len(keyword) < 3 or keyword.lower() in WEAK_KEYWORDS:
        return True
    if len(title) < 18:
        return True
    if len(title) > 55:
        return True
    return False


def existing_note(row: dict[str, str]) -> str:
    hint = row.get("existing_article_hint", "")
    if hint:
        return f"existing near: {hint}"
    return ""


def main() -> int:
    ready_rows = [
        row
        for row in read_csv_rows(INPUT_PATH)
        if row.get("filter_decision") == "ready_for_queue"
    ]
    output_rows = []
    questionable = []
    for index, row in enumerate(ready_rows, start=1):
        original_title = row.get("title", "")
        keyword = extract_keyword(original_title, row.get("product_hint", ""), row.get("category", ""))
        refined_type = infer_type(row.get("article_type", ""), original_title, keyword)
        refined = refine_title(keyword, refined_type, index)
        intent = search_intent(refined_type, original_title)
        note_parts = [f"{refined_type} template", "original_titleから再構成"]
        near = existing_note(row)
        if near:
            note_parts.append(near)
        if is_questionable(refined, keyword):
            note_parts.append("要確認: タイトル長/キーワード品質")
            questionable.append((row, refined, keyword))
        output_rows.append(
            {
                "candidate_rank": row.get("candidate_rank", str(index)),
                "item_id": row.get("item_id", ""),
                "source_name": row.get("source_name", ""),
                "category": row.get("category", ""),
                "original_title": original_title,
                "candidate_title": row.get("candidate_title", ""),
                "refined_title": refined,
                "target_keyword": keyword,
                "refined_article_type": refined_type,
                "search_intent": intent,
                "url": row.get("url", ""),
                "published_at": row.get("published_at", ""),
                "score": row.get("score", ""),
                "product_hint": row.get("product_hint", ""),
                "existing_article_hint": row.get("existing_article_hint", ""),
                "note": "; ".join(note_parts),
            }
        )

    write_csv_rows(OUT_CSV_PATH, OUT_FIELDS, output_rows)

    lines = [
        "# RSS Article Candidate Refined Titles",
        "",
        f"Generated: {now_iso()}",
        "",
        f"- refined_count: {len(output_rows)}",
        "",
        "## Top 10",
        "",
    ]
    for row in output_rows[:10]:
        lines.append(
            f"- #{row['candidate_rank']} {row['refined_title']} "
            f"({row['target_keyword']} / {row['refined_article_type']} / {row['search_intent']})"
        )
    lines.extend(["", "## Needs Review", ""])
    needs_review = [row for row in output_rows if "要確認" in row["note"]]
    if needs_review:
        for row in needs_review:
            lines.append(f"- #{row['candidate_rank']} {row['refined_title']} ({row['note']})")
    else:
        lines.append("- none")
    OUT_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"refined={len(output_rows)}")
    print(f"needs_review={len(needs_review)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
