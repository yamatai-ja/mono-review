from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
ARTICLE_QUEUE = ROOT / "data" / "article_queue.csv"
PRODUCTS_CSV = ROOT / "data" / "products.csv"
RULES_PATH = ROOT / "cluster_rules.yaml"
OUTPUT_CSV = ROOT / "article_cluster_queue.csv"

OUTPUT_COLUMNS = [
    "parent_queue_id",
    "parent_slug",
    "category",
    "article_type",
    "priority",
    "candidate_title",
    "status",
]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = [{k: (v or "") for k, v in row.items()} for row in reader]
        return list(reader.fieldnames or []), rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({
                column: row.get(column, "pending" if column == "status" else "")
                for column in OUTPUT_COLUMNS
            })


def parse_scalar(value: str) -> Any:
    text = value.strip()
    if not text:
        return ""
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1]
    if text.startswith("'") and text.endswith("'"):
        return text[1:-1]
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def load_simple_yaml(path: Path) -> dict[str, Any]:
    """Small YAML subset parser for this repository's cluster_rules.yaml."""
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    last_key_at_indent: dict[int, tuple[Any, str]] = {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]

        if line.startswith("- "):
            value = parse_scalar(line[2:])
            if not isinstance(parent, list):
                raise ValueError(f"List item without list parent: {raw_line}")
            parent.append(value)
            continue

        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not value:
            container: Any = [] if key in {"aliases", "enabled_article_types"} else {}
            if isinstance(parent, dict):
                parent[key] = container
                last_key_at_indent[indent] = (parent, key)
                stack.append((indent, container))
            else:
                raise ValueError(f"Nested mapping under non-dict parent: {raw_line}")
            continue

        if isinstance(parent, dict):
            parent[key] = parse_scalar(value)
        else:
            raise ValueError(f"Scalar under non-dict parent: {raw_line}")

    return root


def normalize(value: str) -> str:
    return (value or "").strip().lower()


def slugify(value: str) -> str:
    text = normalize(value)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[^a-z0-9一-龥ぁ-んァ-ヶー]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "untitled"


def split_ids(value: str) -> list[str]:
    text = (value or "").replace("|", ";").replace(",", ";")
    return [part.strip() for part in text.split(";") if part.strip()]


def product_lookup(products: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    lookup = {}
    for product in products:
        product_id = product.get("product_id") or product.get("id")
        if product_id:
            lookup[product_id] = product
    return lookup


def infer_category(
    queue_row: dict[str, str],
    product_by_id: dict[str, dict[str, str]],
    rules: dict[str, Any],
) -> str:
    haystack_parts = [
        queue_row.get("category", ""),
        queue_row.get("keyword", ""),
        queue_row.get("article_title", ""),
        queue_row.get("notes", ""),
    ]
    base_haystack = normalize(" ".join(haystack_parts))
    for product_id in split_ids(queue_row.get("assigned_product_ids", "")):
        product = product_by_id.get(product_id, {})
        haystack_parts.extend([
            product.get("category", ""),
            product.get("name", ""),
            product.get("title", ""),
            product.get("tags", ""),
        ])
    for product in product_by_id.values():
        product_name = normalize(product.get("name", "") or product.get("title", ""))
        if product_name and product_name in base_haystack:
            haystack_parts.extend([
                product.get("category", ""),
                product.get("name", ""),
                product.get("title", ""),
                product.get("tags", ""),
            ])

    haystack = normalize(" ".join(haystack_parts))
    categories = rules.get("categories", {})
    for category, config in categories.items():
        aliases = config.get("aliases", [])
        if normalize(category) in haystack:
            return category
        for alias in aliases:
            if normalize(str(alias)) and normalize(str(alias)) in haystack:
                return category
    return ""


def product_name_from_queue(row: dict[str, str]) -> str:
    title = row.get("article_title") or row.get("title") or row.get("keyword") or "商品"
    cleanup_patterns = [
        r"はどんな人向け.*$",
        r"の評判.*$",
        r"のデメリット.*$",
        r"の比較ポイント.*$",
        r"のよくある疑問.*$",
        r"レビュー.*$",
        r"口コミ.*$",
    ]
    result = title.strip()
    for pattern in cleanup_patterns:
        result = re.sub(pattern, "", result).strip()
    return result or title.strip()


def existing_keys(rows: list[dict[str, str]]) -> set[tuple[str, str, str]]:
    keys = set()
    for row in rows:
        keys.add((
            row.get("parent_queue_id", ""),
            row.get("parent_slug", ""),
            row.get("article_type", ""),
        ))
    return keys


def normalize_existing_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized = []
    for row in rows:
        copied = dict(row)
        if not copied.get("status"):
            copied["status"] = "pending"
        normalized.append(copied)
    return normalized


def generate_candidates(
    queue_rows: list[dict[str, str]],
    products: list[dict[str, str]],
    rules: dict[str, Any],
    existing_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    product_by_id = product_lookup(products)
    keys = existing_keys(existing_rows)
    candidates: list[dict[str, str]] = []
    for row in queue_rows:
        parent_queue_id = row.get("queue_id", "").strip()
        if not parent_queue_id:
            continue
        category = infer_category(row, product_by_id, rules)
        if not category:
            continue
        config = rules.get("categories", {}).get(category, {})
        parent_slug = row.get("slug") or slugify(row.get("keyword") or row.get("article_title") or parent_queue_id)
        product_name = product_name_from_queue(row)
        for article_type in config.get("enabled_article_types", []):
            key = (parent_queue_id, parent_slug, article_type)
            if key in keys:
                continue
            priority = str(config.get("priority", {}).get(article_type, 1))
            template = config.get("templates", {}).get(article_type, "{product_name}の確認ポイント")
            candidates.append({
                "parent_queue_id": parent_queue_id,
                "parent_slug": parent_slug,
                "category": category,
                "article_type": article_type,
                "priority": priority,
                "candidate_title": str(template).format(product_name=product_name),
                "status": "pending",
            })
            keys.add(key)
    return candidates


def print_summary(candidates: list[dict[str, str]], target_count: int) -> None:
    by_category = Counter(row["category"] for row in candidates)
    by_priority = Counter(row["priority"] for row in candidates)
    print(f"対象記事数: {target_count}")
    print(f"生成予定件数: {len(candidates)}")
    print("カテゴリ別件数:")
    for category, count in sorted(by_category.items()):
        print(f"  {category}: {count}")
    print("優先度別件数:")
    for priority, count in sorted(by_priority.items(), key=lambda item: str(item[0])):
        print(f"  {priority}: {count}")
    print("生成サンプル:")
    for row in candidates[:10]:
        print(
            "  "
            f"{row['parent_queue_id']},{row['parent_slug']},{row['category']},"
            f"{row['article_type']},{row['priority']},{row['candidate_title']}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate product review article cluster candidates.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Show planned cluster candidates without writing files.")
    group.add_argument("--apply", action="store_true", help="Append planned cluster candidates to article_cluster_queue.csv.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not RULES_PATH.exists():
        raise SystemExit(f"Missing rules file: {RULES_PATH}")

    _, queue_rows = read_csv(ARTICLE_QUEUE)
    _, products = read_csv(PRODUCTS_CSV)
    _, existing_rows = read_csv(OUTPUT_CSV)
    existing_rows = normalize_existing_rows(existing_rows)
    rules = load_simple_yaml(RULES_PATH)
    candidates = generate_candidates(queue_rows, products, rules, existing_rows)
    target_count = len({row["parent_queue_id"] for row in candidates})
    print_summary(candidates, target_count)

    if args.apply:
        write_csv(OUTPUT_CSV, [*existing_rows, *candidates])
        print(f"written: {OUTPUT_CSV}")
    else:
        print("dry-run: no files changed")


if __name__ == "__main__":
    main()
