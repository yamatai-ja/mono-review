from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from pathlib import Path
from typing import Any

from cluster_generator import load_simple_yaml

ROOT = Path(__file__).resolve().parent
RULES_PATH = ROOT / "cluster_rules.yaml"
CLUSTER_QUEUE = ROOT / "article_cluster_queue.csv"
ARTICLE_QUEUE = ROOT / "data" / "article_queue.csv"
PRODUCTS_CSV = ROOT / "data" / "products.csv"
OFFERS_CSV = ROOT / "data" / "offers.csv"
PROMPT_DIR = ROOT / "output" / "cluster_body_prompts"
REPORT_CSV = ROOT / "output" / "cluster_prompt_report.csv"
REPORT_MD = ROOT / "output" / "cluster_prompt_report.md"

REQUIRED_CLUSTER_COLUMNS = {
    "parent_queue_id",
    "parent_slug",
    "category",
    "article_type",
    "priority",
    "candidate_title",
}

CLUSTER_QUEUE_COLUMNS = [
    "parent_queue_id",
    "parent_slug",
    "category",
    "article_type",
    "priority",
    "candidate_title",
    "status",
]

SAFE_NOTICE_TERMS = [
    "CTA挿入候補",
    "ProductCard",
    "frontmatter",
    "queue_id",
    "draft",
    "rel=",
    "HTMLで挿入",
    "URL確認後",
    "実機レビュー",
    "使ってみた",
    "最安値",
    "今すぐ購入",
    "絶対おすすめ",
]

CRITICAL_PROMPT_PATTERNS = [
    re.compile(r"CTA挿入候補.*本文に入れる"),
    re.compile(r"ProductCard.*本文に書く"),
    re.compile(r"rel=.*本文に明記"),
    re.compile(r"実機レビューとして書く"),
    re.compile(r"今すぐ購入.*促す"),
    re.compile(r"最安値はこちら.*案内"),
]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = [{k: (v or "") for k, v in row.items()} for row in reader]
        return list(reader.fieldnames or []), rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "parent_queue_id",
        "parent_slug",
        "article_type",
        "candidate_title",
        "prompt_file",
        "status",
        "reason",
        "critical_warnings",
        "safe_notices",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_cluster_queue(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CLUSTER_QUEUE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({
                column: row.get(column, "pending" if column == "status" else "")
                for column in CLUSTER_QUEUE_COLUMNS
            })


def require_columns(columns: list[str], required: set[str], label: str) -> None:
    missing = sorted(required - set(columns))
    if missing:
        raise SystemExit(f"Missing columns in {label}: {', '.join(missing)}")


def find_prompt_quality_notes(prompt: str) -> tuple[list[str], list[str]]:
    critical = []
    for pattern in CRITICAL_PROMPT_PATTERNS:
        if pattern.search(prompt):
            critical.append(pattern.pattern)

    safe_notices = [term for term in SAFE_NOTICE_TERMS if term in prompt]
    return critical, safe_notices


def normalize_cluster_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized = []
    for row in rows:
        copied = dict(row)
        if not copied.get("status"):
            copied["status"] = "pending"
        normalized.append(copied)
    return normalized


def normalize(value: str) -> str:
    return (value or "").strip().lower()


def slugify(value: str) -> str:
    text = normalize(value)
    text = re.sub(r"[^a-z0-9一-龯ぁ-んァ-ヶー]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "untitled"


def split_ids(value: str) -> list[str]:
    text = (value or "").replace("|", ";").replace(",", ";")
    return [part.strip() for part in text.split(";") if part.strip()]


def row_text(row: dict[str, str]) -> str:
    return " ".join(str(value or "") for value in row.values())


def load_rules() -> dict[str, Any]:
    if not RULES_PATH.exists():
        raise SystemExit("Missing cluster_rules.yaml.")
    rules = load_simple_yaml(RULES_PATH)
    if not isinstance(rules, dict):
        raise SystemExit("cluster_rules.yaml must contain a mapping.")
    return rules


def get_category_rules(rules: dict[str, Any], category: str) -> dict[str, Any]:
    categories = rules.get("categories", {})
    if not isinstance(categories, dict):
        return {}
    category_rules = categories.get(category, {})
    return category_rules if isinstance(category_rules, dict) else {}


def get_guidance(rules: dict[str, Any], category: str, article_type: str) -> tuple[str, list[str], str, str]:
    category_rules = get_category_rules(rules, category)
    category_guidance = category_rules.get("guidance", {})
    if isinstance(category_guidance, dict):
        guidance = category_guidance.get(article_type)
        if isinstance(guidance, dict):
            return normalize_guidance(guidance, category_rules, "category")

    default_guidance = rules.get("default_guidance", {})
    if isinstance(default_guidance, dict):
        guidance = default_guidance.get(article_type)
        if isinstance(guidance, dict):
            return normalize_guidance(guidance, category_rules, "default")

    fallback = {
        "intent": "購入前に確認すべきポイントを整理したい。",
        "outline": ["概要", "特徴", "注意点", "FAQ", "まとめ"],
    }
    return normalize_guidance(fallback, category_rules, "fallback")


def normalize_guidance(
    guidance: dict[str, Any],
    category_rules: dict[str, Any],
    source: str,
) -> tuple[str, list[str], str, str]:
    intent = str(guidance.get("intent", "") or "").strip()
    raw_outline = guidance.get("outline", [])
    if isinstance(raw_outline, list):
        outline = [str(item).strip() for item in raw_outline if str(item).strip()]
    else:
        outline = [part.strip() for part in str(raw_outline).split("|") if part.strip()]
    category_rule = str(category_rules.get("category_rule", "") or "").strip()
    return intent, outline, category_rule, source


def product_ids_for_parent(parent: dict[str, str], products: list[dict[str, str]]) -> list[str]:
    explicit_ids = split_ids(parent.get("assigned_product_ids", ""))
    if explicit_ids:
        return explicit_ids

    haystack = normalize(row_text(parent))
    matched: list[str] = []
    for product in products:
        product_id = product.get("product_id") or product.get("id")
        product_name = normalize(product.get("name") or product.get("title"))
        if product_id and product_name and product_name in haystack:
            matched.append(product_id)
    return matched


def format_products(product_ids: list[str], product_by_id: dict[str, dict[str, str]]) -> str:
    if not product_ids:
        return "- 商品候補なし。本文生成前に商品登録・商品URL確認が必要です。"
    lines = []
    for product_id in product_ids:
        product = product_by_id.get(product_id, {})
        lines.append(
            "- {product_id}: name={name} / category={category} / status={status} / amazon_url={amazon_url} / rakuten_url={rakuten_url} / notes={notes}".format(
                product_id=product_id,
                name=product.get("name", ""),
                category=product.get("category", ""),
                status=product.get("status", ""),
                amazon_url=product.get("amazon_url", ""),
                rakuten_url=product.get("rakuten_url", ""),
                notes=product.get("notes", ""),
            )
        )
    return "\n".join(lines)


def format_offers(product_ids: list[str], offers_by_product: dict[str, list[dict[str, str]]]) -> str:
    lines = []
    for product_id in product_ids:
        for offer in offers_by_product.get(product_id, []):
            lines.append(
                "- {offer_id}: product_id={product_id} / platform={platform} / url={url} / status={status} / notes={notes}".format(
                    offer_id=offer.get("offer_id", ""),
                    product_id=product_id,
                    platform=offer.get("platform", ""),
                    url=offer.get("url", ""),
                    status=offer.get("status", ""),
                    notes=offer.get("notes", ""),
                )
            )
    return "\n".join(lines) if lines else "- offer候補なし。強い購入CTAは入れないでください。"


def build_prompt(
    cluster: dict[str, str],
    parent: dict[str, str],
    products_text: str,
    offers_text: str,
    intent: str,
    outline: list[str],
    category_rule: str,
    guidance_source: str,
) -> str:
    article_type = cluster.get("article_type", "")
    sections = "\n".join(f"- {section}" for section in outline)
    source_url = ""
    notes = parent.get("notes", "")
    match = re.search(r"https?://\S+", notes)
    if match:
        source_url = match.group(0)

    category_rule_text = category_rule or "カテゴリ固有ルールなし。共通ルールに従ってください。"

    return f"""# GPTs本文生成プロンプト: {cluster.get('candidate_title', '')}

このMarkdownは記事本文ではありません。GPTsに渡すための本文生成プロンプトです。
以下の条件を守って、商品レビュー系の記事本文Markdownを作成してください。

## 対象記事候補

- parent_queue_id: {cluster.get('parent_queue_id', '')}
- parent_slug: {cluster.get('parent_slug', '')}
- category: {cluster.get('category', '')}
- article_type: {article_type}
- priority: {cluster.get('priority', '')}
- candidate_title: {cluster.get('candidate_title', '')}
- guidance_source: {guidance_source}

## 親記事の元キュー情報

- keyword: {parent.get('keyword', '')}
- original_article_title: {parent.get('article_title', '')}
- original_article_type: {parent.get('article_type', '')}
- status: {parent.get('status', '')}
- source_url: {source_url}
- notes: {notes}

## 検索意図

{intent}

## 推奨構成

{sections}

## カテゴリ固有ルール

{category_rule_text}

## 商品候補
{products_text}

## offer候補
{offers_text}

## 執筆ルール

- 記事本文だけをMarkdownで出力してください。
- 本文の大幅な推測補完はしないでください。
- 未確認スペックを断定しないでください。
- 「使ってみた」「本音レビュー」「実機レビュー」は使わないでください。
- 強い購入CTAは入れないでください。
- 価格・在庫・保証・販売条件は変動する前提で書いてください。
- URLを本文にベタ貼りしないでください。
- アフィリエイトリンクをHTMLで挿入する場合は `rel="sponsored nofollow"` を付ける前提で書いてください。
- 広告・PRを含む可能性があることを本文の冒頭付近に明記してください。
- 比較記事の場合、今回は比較対象を断定せず「比較するときの見るポイント」を中心にしてください。
- 金融・投資・保険・クレジットカードの話題へ広げないでください。

## 禁止表現

- 最強
- 完全
- 絶対
- 必ず
- 最安
- 使ってみた
- 本音レビュー
- 実機レビュー

## 出力形式

1. メタディスクリプション案
2. H1
3. リード文
4. H2/H3本文
5. 向いている人
6. 向いていない人
7. デメリット・注意点
8. FAQ
9. まとめ
"""


def load_context() -> tuple[
    list[dict[str, str]],
    dict[str, dict[str, str]],
    dict[str, dict[str, str]],
    dict[str, list[dict[str, str]]],
    dict[str, Any],
]:
    cluster_columns, cluster_rows = read_csv(CLUSTER_QUEUE)
    require_columns(cluster_columns, REQUIRED_CLUSTER_COLUMNS, "article_cluster_queue.csv")
    cluster_rows = normalize_cluster_rows(cluster_rows)

    _, article_rows = read_csv(ARTICLE_QUEUE)
    _, product_rows = read_csv(PRODUCTS_CSV)
    _, offer_rows = read_csv(OFFERS_CSV)
    rules = load_rules()

    article_by_id = {row.get("queue_id", ""): row for row in article_rows}
    product_by_id = {row.get("product_id", "") or row.get("id", ""): row for row in product_rows}
    offers_by_product: dict[str, list[dict[str, str]]] = {}
    for offer in offer_rows:
        offers_by_product.setdefault(offer.get("product_id", ""), []).append(offer)
    return cluster_rows, article_by_id, product_by_id, offers_by_product, rules


def filter_rows(rows: list[dict[str, str]], queue_id: str | None, article_type: str | None) -> list[dict[str, str]]:
    filtered = rows
    if queue_id:
        filtered = [row for row in filtered if row.get("parent_queue_id") == queue_id]
    if article_type:
        filtered = [row for row in filtered if row.get("article_type") == article_type]
    return filtered


def prompt_filename(row: dict[str, str]) -> str:
    queue_id = row.get("parent_queue_id", "unknown")
    slug = row.get("parent_slug") or "unknown"
    article_type = row.get("article_type") or "article"
    return f"{queue_id}_{slug}_{article_type}_prompt.md"


def write_report(rows: list[dict[str, str]], applied: bool) -> None:
    write_csv(REPORT_CSV, rows)
    counts = Counter(row.get("status", "") for row in rows)
    critical_count = sum(1 for row in rows if row.get("critical_warnings"))
    safe_notice_count = sum(1 for row in rows if row.get("safe_notices"))
    lines = [
        "# Cluster Prompt Report",
        "",
        f"mode: {'apply' if applied else 'dry-run'}",
        "",
        "## counts",
        "",
    ]
    for status, count in sorted(counts.items()):
        lines.append(f"- {status}: {count}")
    lines.append(f"- critical_warning_count: {critical_count}")
    lines.append(f"- safe_notice_count: {safe_notice_count}")
    lines.extend(["", "## samples", ""])
    for row in rows[:10]:
        critical_text = row.get("critical_warnings") or "none"
        safe_notice_text = row.get("safe_notices") or "none"
        lines.append(
            f"- {row.get('parent_queue_id')} / {row.get('article_type')} / "
            f"{row.get('candidate_title')} / {row.get('status')} / "
            f"critical={critical_text} / safe_notice={safe_notice_text}"
        )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GPTs body prompts from article_cluster_queue.csv.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="Show planned prompt files without writing them. Default.")
    group.add_argument("--apply", action="store_true", help="Write GPTs prompt Markdown files.")
    parser.add_argument("--queue-id", help="Filter by parent_queue_id.")
    parser.add_argument("--article-type", help="Filter by cluster article_type.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    applied = bool(args.apply)
    if not CLUSTER_QUEUE.exists():
        raise SystemExit("Missing article_cluster_queue.csv. Run cluster_generator.py --apply first.")

    cluster_rows, article_by_id, product_by_id, offers_by_product, rules = load_context()
    target_rows = filter_rows(cluster_rows, args.queue_id, args.article_type)
    report_rows: list[dict[str, str]] = []

    if applied:
        PROMPT_DIR.mkdir(parents=True, exist_ok=True)

    for cluster in target_rows:
        parent = article_by_id.get(cluster.get("parent_queue_id", ""), {})
        if not parent:
            status = "skipped"
            reason = "missing_parent_queue"
            prompt_file = ""
            critical_warnings: list[str] = []
            safe_notices: list[str] = []
        else:
            product_ids = product_ids_for_parent(parent, list(product_by_id.values()))
            products_text = format_products(product_ids, product_by_id)
            offers_text = format_offers(product_ids, offers_by_product)
            intent, outline, category_rule, guidance_source = get_guidance(
                rules,
                cluster.get("category", ""),
                cluster.get("article_type", ""),
            )
            prompt = build_prompt(
                cluster,
                parent,
                products_text,
                offers_text,
                intent,
                outline,
                category_rule,
                guidance_source,
            )
            prompt_file = str(PROMPT_DIR / prompt_filename(cluster))
            critical_warnings, safe_notices = find_prompt_quality_notes(prompt)
            status = "would_write"
            reason = f"dry_run_guidance={guidance_source}"
            if applied:
                Path(prompt_file).write_text(prompt, encoding="utf-8")
                if cluster.get("status", "pending") == "pending":
                    cluster["status"] = "prompt_generated"
                status = "written"
                reason = f"ok_guidance={guidance_source}"

        report_rows.append({
            "parent_queue_id": cluster.get("parent_queue_id", ""),
            "parent_slug": cluster.get("parent_slug", ""),
            "article_type": cluster.get("article_type", ""),
            "candidate_title": cluster.get("candidate_title", ""),
            "prompt_file": prompt_file,
            "status": status,
            "reason": reason,
            "critical_warnings": "/".join(critical_warnings),
            "safe_notices": "/".join(safe_notices),
        })

    write_report(report_rows, applied)
    if applied:
        write_cluster_queue(CLUSTER_QUEUE, cluster_rows)
    print(f"mode={'apply' if applied else 'dry-run'} target_count={len(target_rows)}")
    for status, count in sorted(Counter(row["status"] for row in report_rows).items()):
        print(f"{status}={count}")
    critical_count = sum(1 for row in report_rows if row.get("critical_warnings"))
    safe_notice_count = sum(1 for row in report_rows if row.get("safe_notices"))
    print(f"critical_warning_count={critical_count}")
    print(f"safe_notice_count={safe_notice_count}")
    print(f"report={REPORT_MD}")
    if not applied:
        print("dry-run: prompt files were not written")


if __name__ == "__main__":
    main()
