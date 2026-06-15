from __future__ import annotations

import csv
import datetime as dt
import hashlib
import html
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
SOURCES_PATH = DATA_DIR / "rss_sources.csv"
ITEMS_PATH = DATA_DIR / "rss_items.csv"
REPORT_CSV_PATH = OUTPUT_DIR / "rss_source_collector_report.csv"
REPORT_MD_PATH = OUTPUT_DIR / "rss_source_collector_report.md"

SOURCE_FIELDS = ["source_name", "category", "feed_url", "priority", "enabled", "notes"]
ITEM_FIELDS = [
    "item_id",
    "source_name",
    "category",
    "title",
    "url",
    "published_at",
    "summary",
    "status",
    "checked_at",
]
REPORT_FIELDS = [
    "source_name",
    "category",
    "feed_url",
    "status",
    "fetched_count",
    "added_count",
    "duplicate_count",
    "error",
    "checked_at",
]


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def is_enabled(value: str) -> bool:
    return (value or "").strip().lower() in {"true", "1", "yes"}


def parse_priority(value: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 3


def stable_item_id(url: str, title: str) -> str:
    key = (url or title or "").strip()
    digest = hashlib.sha256(key.encode("utf-8", errors="ignore")).hexdigest()
    return digest[:16]


def clean_text(value: str, limit: int | None = None) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if limit and len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


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


def append_items(path: Path, existing_rows: list[dict[str, str]], new_rows: list[dict[str, str]]) -> None:
    rows = []
    for row in existing_rows:
        rows.append({field: row.get(field, "") for field in ITEM_FIELDS})
    rows.extend(new_rows)
    write_csv_rows(path, ITEM_FIELDS, rows)


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def first_child_text(node: ET.Element, names: set[str]) -> str:
    for child in list(node):
        if local_name(child.tag) in names:
            return "".join(child.itertext()).strip()
    return ""


def first_link(node: ET.Element) -> str:
    for child in list(node):
        if local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href", "").strip()
        if href:
            return href
        text = "".join(child.itertext()).strip()
        if text:
            return text
    return first_child_text(node, {"guid", "id"})


def parse_feed(xml_bytes: bytes, source: dict[str, str], checked_at: str) -> list[dict[str, str]]:
    root = ET.fromstring(xml_bytes)
    candidates = []
    for node in root.iter():
        name = local_name(node.tag)
        if name in {"item", "entry"}:
            candidates.append(node)

    items = []
    for node in candidates:
        title = clean_text(first_child_text(node, {"title"}))
        url = first_link(node)
        published_at = clean_text(first_child_text(node, {"pubDate", "published", "updated", "date", "dc:date"}))
        summary = clean_text(
            first_child_text(node, {"description", "summary", "content", "encoded"}),
            limit=450,
        )
        items.append(
            {
                "item_id": stable_item_id(url, title),
                "source_name": source.get("source_name", ""),
                "category": source.get("category", ""),
                "title": title,
                "url": url,
                "published_at": published_at,
                "summary": summary,
                "status": "candidate",
                "checked_at": checked_at,
            }
        )
    return items


def fetch_feed(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "monoslog-rss-source-collector/0.1 (+https://monoslog.com)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def ensure_sources_file() -> None:
    if SOURCES_PATH.exists():
        return
    default_rows = [
        {
            "source_name": "PC Watch",
            "category": "PC・ガジェット",
            "feed_url": "https://pc.watch.impress.co.jp/data/rss/1.0/pcw/feed.rdf",
            "priority": "1",
            "enabled": "true",
            "notes": "Impress Watch RSS",
        },
        {
            "source_name": "家電 Watch",
            "category": "家電・生活用品",
            "feed_url": "https://kaden.watch.impress.co.jp/data/rss/1.0/kdw/feed.rdf",
            "priority": "1",
            "enabled": "true",
            "notes": "Impress Watch RSS",
        },
        {
            "source_name": "ケータイ Watch",
            "category": "通信・スマホ",
            "feed_url": "https://k-tai.watch.impress.co.jp/data/rss/1.0/ktw/feed.rdf",
            "priority": "1",
            "enabled": "true",
            "notes": "Impress Watch RSS",
        },
        {
            "source_name": "AV Watch",
            "category": "AV・ガジェット",
            "feed_url": "https://av.watch.impress.co.jp/data/rss/1.0/avw/feed.rdf",
            "priority": "2",
            "enabled": "true",
            "notes": "Impress Watch RSS",
        },
        {
            "source_name": "ITmedia NEWS",
            "category": "IT・ニュース",
            "feed_url": "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml",
            "priority": "2",
            "enabled": "true",
            "notes": "ITmedia RSS",
        },
        {
            "source_name": "ITmedia Mobile",
            "category": "通信・スマホ",
            "feed_url": "https://rss.itmedia.co.jp/rss/2.0/mobile.xml",
            "priority": "2",
            "enabled": "true",
            "notes": "ITmedia RSS",
        },
        {
            "source_name": "ITmedia PC USER",
            "category": "PC・ガジェット",
            "feed_url": "https://rss.itmedia.co.jp/rss/2.0/pcuser.xml",
            "priority": "2",
            "enabled": "true",
            "notes": "ITmedia RSS",
        },
    ]
    write_csv_rows(SOURCES_PATH, SOURCE_FIELDS, default_rows)


def write_markdown_report(report_rows: list[dict[str, str]], added_rows: list[dict[str, str]]) -> None:
    total_fetched = sum(int(row["fetched_count"]) for row in report_rows)
    total_added = sum(int(row["added_count"]) for row in report_rows)
    total_duplicates = sum(int(row["duplicate_count"]) for row in report_rows)
    total_errors = sum(1 for row in report_rows if row["status"] == "error")

    lines = [
        "# RSS Source Collector Report",
        "",
        f"Generated: {utc_now_iso()}",
        "",
        "## Summary",
        "",
        f"- fetched_count: {total_fetched}",
        f"- added_count: {total_added}",
        f"- duplicate_count: {total_duplicates}",
        f"- error_count: {total_errors}",
        "",
        "## Sources",
        "",
        "| source | category | status | fetched | added | duplicate | error |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in report_rows:
        lines.append(
            f"| {row['source_name']} | {row['category']} | {row['status']} | "
            f"{row['fetched_count']} | {row['added_count']} | {row['duplicate_count']} | {row['error']} |"
        )

    lines.extend(["", "## Representative Items", ""])
    for item in added_rows[:5]:
        lines.append(f"- [{item['source_name']}] {item['title']} - {item['url']}")
    if not added_rows:
        lines.append("- No newly added items.")

    REPORT_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    DATA_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    ensure_sources_file()

    checked_at = utc_now_iso()
    sources = read_csv_rows(SOURCES_PATH)
    sources = sorted(sources, key=lambda row: parse_priority(row.get("priority", "")))
    existing_rows = read_csv_rows(ITEMS_PATH)

    seen_urls = {row.get("url", "").strip() for row in existing_rows if row.get("url", "").strip()}
    seen_titles = {row.get("title", "").strip() for row in existing_rows if row.get("title", "").strip()}

    new_rows: list[dict[str, str]] = []
    report_rows: list[dict[str, str]] = []

    for source in sources:
        source_name = source.get("source_name", "")
        feed_url = source.get("feed_url", "")
        category = source.get("category", "")
        if not is_enabled(source.get("enabled", "")):
            report_rows.append(
                {
                    "source_name": source_name,
                    "category": category,
                    "feed_url": feed_url,
                    "status": "disabled",
                    "fetched_count": "0",
                    "added_count": "0",
                    "duplicate_count": "0",
                    "error": "",
                    "checked_at": checked_at,
                }
            )
            continue

        added_count = 0
        duplicate_count = 0
        fetched_count = 0
        error = ""
        status = "ok"
        try:
            xml_bytes = fetch_feed(feed_url)
            items = parse_feed(xml_bytes, source, checked_at)
            fetched_count = len(items)
            for item in items:
                url = item.get("url", "").strip()
                title = item.get("title", "").strip()
                is_duplicate = bool(url and url in seen_urls) or bool(not url and title and title in seen_titles)
                if is_duplicate:
                    duplicate_count += 1
                    continue
                new_rows.append(item)
                if url:
                    seen_urls.add(url)
                if title:
                    seen_titles.add(title)
                added_count += 1
        except (urllib.error.URLError, TimeoutError, ET.ParseError, OSError) as exc:
            status = "error"
            error = clean_text(str(exc), limit=300)

        report_rows.append(
            {
                "source_name": source_name,
                "category": category,
                "feed_url": feed_url,
                "status": status,
                "fetched_count": str(fetched_count),
                "added_count": str(added_count),
                "duplicate_count": str(duplicate_count),
                "error": error,
                "checked_at": checked_at,
            }
        )

    append_items(ITEMS_PATH, existing_rows, new_rows)
    write_csv_rows(REPORT_CSV_PATH, REPORT_FIELDS, report_rows)
    write_markdown_report(report_rows, new_rows)

    print(f"fetched={sum(int(row['fetched_count']) for row in report_rows)}")
    print(f"added={sum(int(row['added_count']) for row in report_rows)}")
    print(f"duplicates={sum(int(row['duplicate_count']) for row in report_rows)}")
    print(f"errors={sum(1 for row in report_rows if row['status'] == 'error')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
