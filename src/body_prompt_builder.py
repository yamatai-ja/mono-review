import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
BODY_PROMPT_DIR = OUTPUT_DIR / "body_prompts"

QUEUE_PATH = DATA_DIR / "article_queue.csv"
PRODUCTS_PATH = DATA_DIR / "products.csv"
OFFERS_PATH = DATA_DIR / "offers.csv"
REVIEW_REPORT_PATH = OUTPUT_DIR / "outline_review_report.csv"
RSS_PRODUCT_CHECK_REPORT_PATH = OUTPUT_DIR / "rss_product_check_report.csv"
REPORT_PATH = OUTPUT_DIR / "body_prompt_report.md"

REQUIRED_QUEUE_COLUMNS = {
    "queue_id",
    "keyword",
    "article_title",
    "article_type",
    "assigned_product_ids",
    "notes",
}
REQUIRED_REVIEW_COLUMNS = {"queue_id", "outline_file", "decision"}
REQUIRED_PRODUCT_COLUMNS = {"product_id", "name", "category", "tags", "status", "notes"}
REQUIRED_OFFER_COLUMNS = {"offer_id", "product_id", "platform", "url", "status", "notes"}


def read_csv(path):
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return reader.fieldnames or [], rows


def require_columns(label, columns, required):
    missing = sorted(required - set(columns))
    if missing:
        raise SystemExit(f"Missing columns in {label}: {', '.join(missing)}")


def split_ids(value):
    if not value:
        return []
    normalized = value.replace(";", ",").replace("|", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def load_context(target_queue_id=None):
    review_columns, review_rows = read_csv(REVIEW_REPORT_PATH)
    queue_columns, queue_rows = read_csv(QUEUE_PATH)
    product_columns, product_rows = read_csv(PRODUCTS_PATH)
    offer_columns, offer_rows = read_csv(OFFERS_PATH)
    _, rss_product_check_rows = read_csv(RSS_PRODUCT_CHECK_REPORT_PATH)

    require_columns("output/outline_review_report.csv", review_columns, REQUIRED_REVIEW_COLUMNS)
    require_columns("data/article_queue.csv", queue_columns, REQUIRED_QUEUE_COLUMNS)
    require_columns("data/products.csv", product_columns, REQUIRED_PRODUCT_COLUMNS)
    require_columns("data/offers.csv", offer_columns, REQUIRED_OFFER_COLUMNS)

    ready_rows = [row for row in review_rows if (row.get("decision") or "").strip() == "ready_for_body"]
    if target_queue_id:
        ready_rows = [row for row in ready_rows if (row.get("queue_id") or "").strip() == target_queue_id]

    queue_by_id = {row.get("queue_id", "").strip(): row for row in queue_rows}
    product_by_id = {row.get("product_id", "").strip(): row for row in product_rows}
    rss_product_check_by_id = {row.get("queue_id", "").strip(): row for row in rss_product_check_rows}

    offers_by_product = {}
    for offer in offer_rows:
        product_id = (offer.get("product_id") or "").strip()
        offers_by_product.setdefault(product_id, []).append(offer)

    return ready_rows, queue_by_id, product_by_id, offers_by_product, product_rows, rss_product_check_by_id


def row_text(row):
    return " ".join(str(value or "") for value in row.values())


def product_ids_for_queue(queue_row, product_rows):
    product_ids = split_ids(queue_row.get("assigned_product_ids", ""))
    if product_ids:
        return product_ids

    keyword = (queue_row.get("keyword") or "").strip().lower()
    if not keyword:
        return []

    matched = []
    for product in product_rows:
        if keyword in row_text(product).lower():
            product_id = (product.get("product_id") or "").strip()
            if product_id:
                matched.append(product_id)
    return matched


def format_products(product_ids, product_by_id):
    if not product_ids:
        return "- 商品候補なし。CTAは要確認。"
    lines = []
    for product_id in product_ids:
        product = product_by_id.get(product_id)
        if not product:
            lines.append(f"- {product_id}: 商品DBに該当なし。CTAは要確認。")
            continue
        lines.append(
            "- {product_id}: {name} / {category} / tags={tags} / status={status} / notes={notes}".format(
                product_id=product_id,
                name=product.get("name", ""),
                category=product.get("category", ""),
                tags=product.get("tags", ""),
                status=product.get("status", ""),
                notes=product.get("notes", ""),
            )
        )
    return "\n".join(lines)


def format_offers(product_ids, offers_by_product):
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
    if not lines:
        return "- 案件候補なし。サービス導線CTAは要確認。"
    return "\n".join(lines)


def build_rss_warning_block(rss_check):
    if not rss_check:
        return "- RSS商品チェック情報なし。通常の確認ルールを優先してください。"

    return """- rss_product_check decision: {decision}
- source URL: {source_url}
- product candidates: {product_candidates}
- offer candidates: {offer_candidates}
- URL未確認です。商品URL・offer URLが空欄のため、強い購入CTAは禁止です。
- ProductCardは未完成扱いです。本文内では「価格を確認する」「販売状況を確認する」程度の弱いCTAに留めてください。
- Amazon/楽天/Yahoo/公式/キャリア販売ページは本文生成前に要確認です。
- 価格・在庫・対応バンド・保証・SIMフリー版/キャリア版の違いを確認してください。
- CTA policy: {cta_policy}
- pre body checks: {pre_body_checks}""".format(
        decision=rss_check.get("decision", ""),
        source_url=rss_check.get("source_url", ""),
        product_candidates=rss_check.get("product_candidates", ""),
        offer_candidates=rss_check.get("offer_candidates", ""),
        cta_policy=rss_check.get("cta_policy", ""),
        pre_body_checks=rss_check.get("pre_body_checks", ""),
    )


def build_prompt(queue_row, outline_text, products_text, offers_text, rss_check):
    title = queue_row.get("article_title") or queue_row.get("keyword") or ""
    keyword = queue_row.get("keyword", "")
    article_type = queue_row.get("article_type", "")
    notes = queue_row.get("notes", "")
    rss_warning_block = build_rss_warning_block(rss_check)

    return f"""# 本文生成用プロンプト: {title}

このMarkdownは記事本文ではありません。GPTに渡すための本文生成プロンプトです。
以下の条件を守って、次工程で記事本文Markdownを生成してください。

## 最重要注意事項
{rss_warning_block}

- 実機レビューではありません。
- 「使ってみた」「本音レビュー」「実機レビュー」は使わないでください。
- 公開情報・RSS元ニュース・公式情報確認前提の購入判断記事として書いてください。
- 購入判断記事として、特徴・向いている人・注意点・競合比較・FAQを中心にしてください。

## 記事タイトル
- {title}

## 対象キーワード
- {keyword}

## 記事タイプ
- {article_type}

## キュー情報
- notes: {notes}

## 検索意図・想定読者・H2/H3構成案
以下の構成案を素材として使ってください。本文ではなく、構成・方針として参照してください。

```markdown
{outline_text.strip()}
```

## 紹介候補商品
{products_text}

## 紹介候補案件
{offers_text}

## CTA方針
- 商品紹介CTAとサービス申込CTAは、本文の自然な位置に「候補」として設計してください。
- 本文中に実URLをベタ貼りしないでください。
- 商品・案件の一致に不安がある場合は、CTA文を断定せず「確認後に挿入」としてください。
- URL未確認の場合は、強い購入CTAにせず「価格を確認する」「販売状況を確認する」程度の弱い表現にしてください。
- ProductCardが未完成の場合は、本文内でProductCard完成済みのように扱わないでください。

## 実体験の有無
- 実体験が明記されていない場合は、実体験なしとして扱ってください。

## 実体験がない場合の書き方
- 実際に使っていない商品を「使ってみた」「本音レビュー」「実機レビュー」と書かないでください。
- 公式情報・公開情報・RSS元ニュース・口コミ傾向をもとにした調査記事として書いてください。
- 未確認情報と確認済み情報を分けてください。
- 体験談風の断定表現は避けてください。

## 禁止表現
- 誇大表現を避けてください。
- 効果や結果を断定しすぎないでください。
- 価格、在庫、キャンペーン、通信品質、保証内容を未確認のまま断定しないでください。
- 「使ってみた」「本音レビュー」「実機レビュー」は使わないでください。
- 医療・金融・法務に見える断定表現は避けてください。

## PR表記・広告表記の注意
- 記事冒頭またはアフィリエイト導線の近くに、広告・PRを含む可能性があることを明記してください。
- 読者の購入判断を助ける中立的な説明を優先してください。

## rel=\"sponsored\" の注意
- アフィリエイトリンクをHTMLで出す場合は、リンクに `rel=\"sponsored nofollow\"` を付ける前提で書いてください。
- Markdown本文ではURLを直接貼らず、リンク挿入候補として示してください。

## 本文生成時のルール
- 記事本文はMarkdown形式で生成してください。
- H1は1つだけにしてください。
- H2/H3構造を構成案に沿って守ってください。
- 商品・サービスのデメリットも必ず書いてください。
- 買うべき人 / 買わない方がいい人を必ず入れてください。
- FAQを必ず入れてください。
- メタディスクリプション案も出してください。
- アフィリエイトリンクの位置は候補だけ示し、本文中に実URLをベタ貼りしないでください。
- 読者が選び方で失敗しないよう、注意点を具体化してください。

## 出力形式
以下の順番で出力してください。

1. メタディスクリプション案
2. H1
3. リード文
4. H2/H3本文
5. 買うべき人
6. 買わない方がいい人
7. デメリット・注意点
8. CTA挿入候補
9. FAQ
10. まとめ
"""


def main():
    parser = argparse.ArgumentParser(description="Build body-generation prompt Markdown files for ready outlines.")
    parser.add_argument("--queue-id", help="Generate a prompt for one queue_id only.")
    args = parser.parse_args()

    ready_rows, queue_by_id, product_by_id, offers_by_product, product_rows, rss_product_check_by_id = load_context(args.queue_id)
    BODY_PROMPT_DIR.mkdir(parents=True, exist_ok=True)

    generated = []
    skipped = []

    for review_row in ready_rows:
        queue_id = (review_row.get("queue_id") or "").strip()
        queue_row = queue_by_id.get(queue_id)
        if not queue_row:
            skipped.append((queue_id, "missing queue row"))
            continue

        outline_file = review_row.get("outline_file") or f"output/outlines/{queue_id}_outline.md"
        outline_path = ROOT / outline_file
        if not outline_path.exists():
            skipped.append((queue_id, "missing outline file"))
            continue

        outline_text = outline_path.read_text(encoding="utf-8-sig")
        product_ids = product_ids_for_queue(queue_row, product_rows)
        products_text = format_products(product_ids, product_by_id)
        offers_text = format_offers(product_ids, offers_by_product)
        rss_check = rss_product_check_by_id.get(queue_id, {})

        prompt_text = build_prompt(queue_row, outline_text, products_text, offers_text, rss_check)
        output_path = BODY_PROMPT_DIR / f"{queue_id}_body_prompt.md"
        output_path.write_text(prompt_text, encoding="utf-8")
        generated.append((queue_id, output_path.relative_to(ROOT).as_posix()))

    report_lines = [
        "# Body Prompt Report",
        "",
        f"Generated: {len(generated)}",
        f"Skipped: {len(skipped)}",
        f"Target queue_id: {args.queue_id or 'all ready_for_body'}",
        "",
        "## Generated Prompts",
    ]
    if generated:
        report_lines.extend([f"- {queue_id}: {path}" for queue_id, path in generated])
    else:
        report_lines.append("- none")

    report_lines.extend(["", "## Skipped"])
    if skipped:
        report_lines.extend([f"- {queue_id}: {reason}" for queue_id, reason in skipped])
    else:
        report_lines.append("- none")

    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"generated={len(generated)} skipped={len(skipped)} report={REPORT_PATH}")
    for queue_id, path in generated:
        print(f"{queue_id} {path}")


if __name__ == "__main__":
    main()
