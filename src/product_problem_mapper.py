from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTICLE_QUEUE = ROOT / "data" / "article_queue.csv"
PRODUCTS_CSV = ROOT / "data" / "products.csv"
RSS_ITEMS_CSV = ROOT / "data" / "rss_items.csv"
OUTPUT_CSV = ROOT / "output" / "problem_keyword_candidates.csv"

OUTPUT_COLUMNS = [
    "source_type",
    "source_id",
    "source_title",
    "product_name",
    "detected_category",
    "problem_keyword",
    "article_type",
    "search_intent",
    "priority",
    "reason",
    "recommended_product_hint",
    "status",
    "created_at",
]


@dataclass(frozen=True)
class SourceItem:
    source_type: str
    source_id: str
    source_title: str
    product_name: str
    raw_category: str
    text: str


PROBLEM_TEMPLATES = {
    "smartphone": [
        ("Androidスマホ 電池持ち 選び方", "電池持ちを重視してAndroidスマホを選びたい", 5),
        ("FeliCa対応 Androidスマホ 選び方", "キャッシュレス決済に使いやすいAndroidスマホを選びたい", 5),
        ("大画面スマホ 片手操作 注意点", "大画面スマホの使い勝手や注意点を知りたい", 4),
        ("microSD対応スマホ 必要か", "microSD対応スマホが自分に必要か判断したい", 3),
        ("スマホ 対応バンド 確認方法", "購入前に対応バンドを確認したい", 5),
    ],
    "smartwatch": [
        ("スマートウォッチ 通知 来ない 原因", "スマートウォッチの通知トラブルを解決したい", 5),
        ("スマートウォッチ 電池持ち 長い 選び方", "電池持ちが長いスマートウォッチを選びたい", 5),
        ("睡眠記録 スマートウォッチ 選び方", "睡眠記録に使いやすいスマートウォッチを選びたい", 4),
        ("スマートウォッチ iPhone Android 違い", "スマートウォッチのスマホ別の違いを知りたい", 4),
        ("Apple Watch 高い 代わり", "Apple Watch以外の選択肢を探したい", 4),
    ],
    "pc_accessory": [
        ("外付けSSD 接続が切れる 原因", "外付けSSDの接続不安定の原因を知りたい", 5),
        ("外付けSSD 接続が切れる 対策", "外付けSSDの接続切れを防ぎたい", 5),
        ("USB-Cハブ 外付けSSD 安定", "外付けSSDを安定して使えるUSB-Cハブを選びたい", 4),
        ("ノートパソコン USBポート 足りない 対策", "ノートPCのポート不足を解決したい", 4),
        ("HDMI 有線LAN USB-Cハブ 選び方", "必要な端子を備えたUSB-Cハブを選びたい", 4),
    ],
    "storage": [
        ("外付けSSD 接続が切れる 原因", "外付けSSDの接続不安定の原因を知りたい", 5),
        ("外付けSSD 接続が切れる 対策", "外付けSSDの接続切れを防ぎたい", 5),
        ("外付けSSD 発熱 対策", "外付けSSDの発熱が気になる", 4),
        ("外付けSSD 容量 選び方", "用途に合う外付けSSD容量を選びたい", 3),
        ("外付けSSD バックアップ 注意点", "バックアップ用途の注意点を知りたい", 3),
    ],
    "network": [
        ("停電 WiFi 使えない 対策", "停電時のネット接続を確保したい", 5),
        ("回線障害 ネット つながらない 対策", "回線障害時の代替手段を知りたい", 5),
        ("非常用 モバイルWiFi 選び方", "非常用のモバイルWiFiを選びたい", 4),
        ("povo 非常用 WiFi 使い方", "povoを非常用回線として使いたい", 4),
    ],
    "home_appliance": [
        ("生ごみ 臭い 対策", "生ごみの臭いを減らしたい", 5),
        ("生ごみ処理機 電気代 注意点", "生ごみ処理機の維持費を知りたい", 4),
        ("夏 生ごみ コバエ 対策", "夏場のコバエ対策をしたい", 5),
        ("家庭用生ごみ処理機 選び方", "家庭用生ごみ処理機を比較したい", 4),
    ],
    "beauty": [
        ("白髪染めシャンプー 色移り 対策", "白髪染めシャンプーの色移りを避けたい", 5),
        ("白髪シャンプー 浴室 汚れ 対策", "浴室汚れを抑えて白髪ケアしたい", 4),
        ("白髪染め 手袋 面倒 対策", "白髪染めの手間を減らしたい", 4),
        ("白髪を目立ちにくくする シャンプー 選び方", "白髪を自然に目立ちにくくしたい", 4),
    ],
    "outdoor": [
        ("アウトドア 電源 確保 方法", "屋外でスマホや家電の電源を確保したい", 4),
        ("キャンプ モバイルバッテリー 選び方", "キャンプ向けの電源を選びたい", 4),
        ("車中泊 ポータブル電源 注意点", "車中泊で使う電源の注意点を知りたい", 4),
    ],
    "disaster_prevention": [
        ("停電 暑さ対策", "停電時の暑さ対策を知りたい", 5),
        ("停電 スマホ充電 対策", "停電時のスマホ充電手段を用意したい", 5),
        ("台風 停電 WiFi 対策", "台風停電時の通信手段を確保したい", 5),
        ("非常用電源 選び方", "非常用電源を選びたい", 4),
    ],
    "unknown": [
        ("ガジェット 選び方 失敗しない", "用途に合うガジェットを選びたい", 2),
        ("便利グッズ 買う前 注意点", "便利グッズ購入前の注意点を知りたい", 2),
    ],
}

CATEGORY_HINTS = {
    "smartphone": [
        "スマホ",
        "Android",
        "iPhone",
        "motorola",
        "edge 60",
        "Pixel",
        "Galaxy",
        "AQUOS",
        "OPPO",
        "Xiaomi",
    ],
    "smartwatch": [
        "スマートウォッチ",
        "smartwatch",
        "Amazfit",
        "Apple Watch",
        "睡眠記録",
        "Active 3",
        "Premium",
        "Fitbit",
        "Garmin",
    ],
    "pc_accessory": [
        "USB-C",
        "USBハブ",
        "ハブ",
        "ドック",
        "Revodok",
        "HDMI",
        "有線LAN",
        "PC周辺機器",
    ],
    "storage": [
        "SSD",
        "ストレージ",
        "外付け",
        "バックアップ",
    ],
    "network": [
        "WiFi",
        "Wi-Fi",
        "ルーター",
        "モバイルWiFi",
        "FS040W",
        "povo",
        "回線",
        "ネット",
    ],
    "home_appliance": [
        "家電",
        "生ごみ",
        "冷蔵庫",
        "洗濯機",
        "掃除機",
        "調理",
    ],
    "beauty": [
        "白髪",
        "シャンプー",
        "美容",
        "ヘア",
        "染め",
    ],
    "outdoor": [
        "キャンプ",
        "アウトドア",
        "車中泊",
    ],
    "disaster_prevention": [
        "停電",
        "防災",
        "非常用",
        "台風",
        "ポータブル電源",
        "Jackery",
    ],
}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = [{key: (value or "") for key, value in row.items()} for row in reader]
        return list(reader.fieldnames or []), rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in OUTPUT_COLUMNS})


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def source_items_from_article_queue(rows: list[dict[str, str]]) -> list[SourceItem]:
    items: list[SourceItem] = []
    for row in rows:
        title = normalize_text(row.get("article_title") or row.get("keyword"))
        keyword = normalize_text(row.get("keyword"))
        source_id = normalize_text(row.get("queue_id"))
        if not source_id or not title:
            continue
        product_name = keyword or title
        text = " ".join([
            title,
            keyword,
            row.get("article_type", ""),
            row.get("assigned_product_ids", ""),
            row.get("notes", ""),
        ])
        items.append(SourceItem("article_queue", source_id, title, product_name, "", text))
    return items


def source_items_from_products(rows: list[dict[str, str]]) -> list[SourceItem]:
    items: list[SourceItem] = []
    for row in rows:
        product_id = normalize_text(row.get("product_id") or row.get("id"))
        name = normalize_text(row.get("name") or row.get("title"))
        if not product_id or not name:
            continue
        text = " ".join([
            name,
            row.get("category", ""),
            row.get("tags", ""),
            row.get("notes", ""),
        ])
        items.append(SourceItem("products", product_id, name, name, row.get("category", ""), text))
    return items


def infer_product_name_from_rss(title: str) -> str:
    quoted = re.findall(r"「([^」]{2,80})」", title)
    if quoted:
        return quoted[0]
    ascii_product = re.findall(r"\b[A-Z][A-Za-z0-9+.\- ]{3,60}\b", title)
    if ascii_product:
        return normalize_text(ascii_product[0])
    return normalize_text(title)


def source_items_from_rss(rows: list[dict[str, str]]) -> list[SourceItem]:
    items: list[SourceItem] = []
    for row in rows:
        item_id = normalize_text(row.get("item_id"))
        title = normalize_text(row.get("title"))
        if not item_id or not title:
            continue
        text = " ".join([title, row.get("category", ""), row.get("summary", ""), row.get("source_name", "")])
        items.append(SourceItem("rss_items", item_id, title, infer_product_name_from_rss(title), row.get("category", ""), text))
    return items


def detect_category(item: SourceItem) -> tuple[str, str]:
    haystack = f"{item.raw_category} {item.text}".lower()
    scores: dict[str, int] = {}
    for category, hints in CATEGORY_HINTS.items():
        score = sum(1 for hint in hints if hint.lower() in haystack)
        if score:
            scores[category] = score

    if not scores:
        return "unknown", "no_category_hint_matched"

    category, score = max(scores.items(), key=lambda pair: (pair[1], pair[0]))
    return category, f"matched_{score}_category_hints"


def build_candidates(items: list[SourceItem], existing_keywords: set[str]) -> list[dict[str, str]]:
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows: list[dict[str, str]] = []
    seen_keywords = set(existing_keywords)
    seen_sources: set[tuple[str, str]] = set()

    for item in items:
        source_key = (item.source_type, item.source_id)
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)

        category, reason = detect_category(item)
        templates = PROBLEM_TEMPLATES.get(category, PROBLEM_TEMPLATES["unknown"])
        limit = 2 if category == "unknown" else 5

        emitted = 0
        for keyword, intent, priority in templates:
            if keyword in seen_keywords:
                continue
            seen_keywords.add(keyword)
            emitted += 1
            rows.append({
                "source_type": item.source_type,
                "source_id": item.source_id,
                "source_title": item.source_title,
                "product_name": item.product_name,
                "detected_category": category,
                "problem_keyword": keyword,
                "article_type": "problem_solution",
                "search_intent": intent,
                "priority": str(priority),
                "reason": reason,
                "recommended_product_hint": item.product_name,
                "status": "candidate",
                "created_at": created_at,
            })
            if emitted >= limit:
                break
    return rows


def load_sources() -> list[SourceItem]:
    _, article_rows = read_csv(ARTICLE_QUEUE)
    _, product_rows = read_csv(PRODUCTS_CSV)
    _, rss_rows = read_csv(RSS_ITEMS_CSV)

    return [
        *source_items_from_article_queue(article_rows),
        *source_items_from_products(product_rows),
        *source_items_from_rss(rss_rows),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Map product-like RSS/article candidates to problem keyword candidates.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="Preview candidates without writing output. Default.")
    group.add_argument("--apply", action="store_true", help="Append unique candidates to output/problem_keyword_candidates.csv.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    apply = bool(args.apply)

    existing_columns, existing_rows = read_csv(OUTPUT_CSV)
    existing_keywords = {row.get("problem_keyword", "") for row in existing_rows if row.get("problem_keyword")}
    candidates = build_candidates(load_sources(), existing_keywords)

    if apply:
        output_rows = existing_rows + candidates
        write_csv(OUTPUT_CSV, output_rows)

    category_counts: dict[str, int] = {}
    for row in candidates:
        category_counts[row["detected_category"]] = category_counts.get(row["detected_category"], 0) + 1

    print(f"mode={'apply' if apply else 'dry-run'}")
    print(f"source_count={len(load_sources())}")
    print(f"candidate_count={len(candidates)}")
    print(f"existing_output_count={len(existing_rows)}")
    if apply:
        print(f"written_total={len(existing_rows) + len(candidates)}")
        print(f"output={OUTPUT_CSV}")
    for category, count in sorted(category_counts.items()):
        print(f"category.{category}={count}")
    print("samples:")
    for row in candidates[:10]:
        print(f"- {row['source_id']} / {row['detected_category']} / {row['problem_keyword']}")


if __name__ == "__main__":
    main()
