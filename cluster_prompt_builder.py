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
RESEARCH_NOTES_DIR = ROOT / "input" / "research_notes"

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

MATERIAL_REQUIREMENTS = {
    "reputation": [
        "実際の口コミ傾向",
        "良い評判",
        "悪い評判",
        "レビュー/評判ソース",
        "商品固有の評価ポイント",
    ],
    "comparison": [
        "比較対象",
        "比較軸",
        "商品ごとの差",
        "どんな人にどちらが向くか",
    ],
    "disadvantages": [
        "商品固有の欠点",
        "仕様上の制約",
        "購入前の注意点",
        "競合と比べて弱い点",
    ],
    "review": [
        "公式仕様",
        "主な特徴",
        "向いている人",
        "注意点",
    ],
    "faq": [
        "想定質問",
        "購入前不安",
        "仕様確認ポイント",
    ],
}

RESEARCH_KEYWORD_GROUPS = {
    "reputation": {
        "実際の口コミ傾向": ["口コミ", "評判", "レビュー", "SNS", "Amazon", "楽天"],
        "良い評判": ["良い評判", "高評価", "メリット", "良い口コミ", "評価され"],
        "悪い評判": ["悪い評判", "低評価", "デメリット", "悪い口コミ", "不満", "気になる"],
        "レビュー/評判ソース": ["source", "Source", "URL", "http", "出典", "参照", "レビュー"],
        "商品固有の評価ポイント": ["Amazfit", "Active 3", "Premium", "商品固有", "評価ポイント"],
    },
    "comparison": {
        "比較対象": ["比較対象", "競合", "他機種", "VS", "vs", "Pixel", "Apple", "Garmin"],
        "比較軸": ["比較軸", "価格", "機能", "バッテリー", "画面", "センサー", "通知"],
        "商品ごとの差": ["差", "違い", "優位", "弱い", "強い"],
        "どんな人にどちらが向くか": ["向いている", "おすすめ", "選ぶ", "どちら"],
    },
    "disadvantages": {
        "商品固有の欠点": ["欠点", "デメリット", "弱点", "不満", "注意"],
        "仕様上の制約": ["制約", "非対応", "未対応", "仕様", "制限"],
        "購入前の注意点": ["購入前", "注意点", "確認", "保証", "価格"],
        "競合と比べて弱い点": ["競合", "比較", "弱い", "劣る", "他機種"],
    },
    "review": {
        "公式仕様": ["公式", "仕様", "スペック", "http", "Source"],
        "主な特徴": ["特徴", "機能", "ポイント"],
        "向いている人": ["向いている", "おすすめ", "適して"],
        "注意点": ["注意", "確認", "デメリット"],
    },
    "faq": {
        "想定質問": ["FAQ", "質問", "疑問", "Q"],
        "購入前不安": ["不安", "心配", "購入前", "注意"],
        "仕様確認ポイント": ["仕様", "確認", "スペック", "対応"],
    },
}


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
        "research_note_found",
        "needs_research",
        "research_missing_items",
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


def research_note_path(queue_id: str, article_type: str) -> Path:
    safe_queue_id = re.sub(r"[^A-Za-z0-9_-]+", "", queue_id or "unknown")
    safe_article_type = re.sub(r"[^A-Za-z0-9_-]+", "", article_type or "article")
    return RESEARCH_NOTES_DIR / f"{safe_queue_id}_{safe_article_type}.md"


def load_research_note(queue_id: str, article_type: str) -> tuple[bool, str, Path]:
    path = research_note_path(queue_id, article_type)
    if not path.exists():
        return False, "", path
    return True, path.read_text(encoding="utf-8-sig").strip(), path


def research_missing_items(article_type: str, note_text: str) -> list[str]:
    requirements = MATERIAL_REQUIREMENTS.get(article_type, [])
    if not requirements:
        return []
    if not note_text.strip():
        return requirements

    keyword_groups = RESEARCH_KEYWORD_GROUPS.get(article_type, {})
    missing: list[str] = []
    for item in requirements:
        keywords = keyword_groups.get(item, [item])
        if not any(keyword in note_text for keyword in keywords):
            missing.append(item)
    return missing


def format_research_section(
    article_type: str,
    found: bool,
    note_text: str,
    missing_items: list[str],
    note_path: Path,
) -> str:
    requirements = MATERIAL_REQUIREMENTS.get(article_type, [])
    requirement_lines = "\n".join(f"- {item}" for item in requirements) or "- 追加要件なし"
    missing_lines = "\n".join(f"- {item}" for item in missing_items) or "- none"
    if found and note_text:
        note_block = f"""## 根拠メモ

以下は本文作成前の根拠メモです。丸写しせず、読者向けに再構成してください。
根拠メモにない口コミ・評判・仕様は捏造しないでください。
価格、発売日、FeliCa/Suica、医療効果、保証、対応バンドなどは根拠がない限り断定しないでください。

```text
{note_text}
```"""
    else:
        note_block = f"""## 根拠メモ

根拠メモは未提供です。
想定パス: {note_path}
商品固有情報・口コミ・比較材料が不足している場合は、無理に完成記事を書かず、情報不足として追加調査項目を返してください。
一般論だけで記事を完成させないでください。"""

    reputation_rule = ""
    if article_type == "reputation":
        reputation_rule = """

reputation記事では、実際の口コミ、レビュー傾向、良い評判、悪い評判の材料がない場合は、評判記事として完成させないでください。口コミを推測で作らないでください。"""

    return f"""{note_block}

## 素材不足チェック

この記事タイプで必要な材料:
{requirement_lines}

不足または未確認の材料:
{missing_lines}

商品固有情報・口コミ・比較材料が不足している場合は、無理に完成記事を書かず、情報不足として追加調査項目を返してください。
一般論だけで記事を完成させないでください。{reputation_rule}
"""


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
    research_section: str,
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

{research_section}

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

1. H1
2. リード文
3. H2/H3本文
4. 向いている人
5. 向いていない人
6. デメリット・注意点
7. FAQ
8. まとめ
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
    research_note_found_count = sum(1 for row in rows if row.get("research_note_found") == "yes")
    research_note_missing_count = sum(1 for row in rows if row.get("research_note_found") == "no")
    needs_research_count = sum(1 for row in rows if row.get("needs_research") == "yes")
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
    lines.append(f"- research_note_found_count: {research_note_found_count}")
    lines.append(f"- research_note_missing_count: {research_note_missing_count}")
    lines.append(f"- needs_research_count: {needs_research_count}")
    lines.append(f"- critical_warning_count: {critical_count}")
    lines.append(f"- safe_notice_count: {safe_notice_count}")
    lines.extend(["", "## needs_research", ""])
    needs_research_rows = [row for row in rows if row.get("needs_research") == "yes"]
    if needs_research_rows:
        for row in needs_research_rows[:20]:
            lines.append(
                f"- {row.get('parent_queue_id')} / {row.get('article_type')} / "
                f"{row.get('candidate_title')} / missing={row.get('research_missing_items')}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## samples", ""])
    for row in rows[:10]:
        critical_text = row.get("critical_warnings") or "none"
        safe_notice_text = row.get("safe_notices") or "none"
        lines.append(
            f"- {row.get('parent_queue_id')} / {row.get('article_type')} / "
            f"{row.get('candidate_title')} / {row.get('status')} / "
            f"needs_research={row.get('needs_research')} / "
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
            research_found = False
            missing_research_items: list[str] = []
        else:
            product_ids = product_ids_for_parent(parent, list(product_by_id.values()))
            products_text = format_products(product_ids, product_by_id)
            offers_text = format_offers(product_ids, offers_by_product)
            intent, outline, category_rule, guidance_source = get_guidance(
                rules,
                cluster.get("category", ""),
                cluster.get("article_type", ""),
            )
            research_found, research_note, research_path = load_research_note(
                cluster.get("parent_queue_id", ""),
                cluster.get("article_type", ""),
            )
            missing_research_items = research_missing_items(
                cluster.get("article_type", ""),
                research_note,
            )
            research_section = format_research_section(
                cluster.get("article_type", ""),
                research_found,
                research_note,
                missing_research_items,
                research_path,
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
                research_section,
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
            "research_note_found": "yes" if research_found else "no",
            "needs_research": "yes" if missing_research_items else "no",
            "research_missing_items": " / ".join(missing_research_items),
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
    research_note_found_count = sum(1 for row in report_rows if row.get("research_note_found") == "yes")
    research_note_missing_count = sum(1 for row in report_rows if row.get("research_note_found") == "no")
    needs_research_count = sum(1 for row in report_rows if row.get("needs_research") == "yes")
    print(f"research_note_found_count={research_note_found_count}")
    print(f"research_note_missing_count={research_note_missing_count}")
    print(f"needs_research_count={needs_research_count}")
    print(f"critical_warning_count={critical_count}")
    print(f"safe_notice_count={safe_notice_count}")
    print(f"report={REPORT_MD}")
    if not applied:
        print("dry-run: prompt files were not written")


if __name__ == "__main__":
    main()
