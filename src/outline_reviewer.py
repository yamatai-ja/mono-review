from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
OUTLINE_DIR = OUTPUT_DIR / "outlines"

QUEUE_CSV = DATA_DIR / "article_queue.csv"
PRODUCTS_CSV = DATA_DIR / "products.csv"
OFFERS_CSV = DATA_DIR / "offers.csv"
EDITOR_REPORT_CSV = OUTPUT_DIR / "editor_score_report.csv"
REVIEW_REPORT_CSV = OUTPUT_DIR / "outline_review_report.csv"
REVIEW_REPORT_MD = OUTPUT_DIR / "outline_review_report.md"
RSS_PRODUCT_CHECK_REPORT_CSV = OUTPUT_DIR / "rss_product_check_report.csv"

QUEUE_REQUIRED_COLUMNS = ["queue_id", "keyword", "article_title", "article_type", "assigned_product_ids", "notes"]
PRODUCT_REQUIRED_COLUMNS = ["product_id", "name", "category", "tags", "status"]
OFFER_REQUIRED_COLUMNS = ["offer_id", "product_id", "platform", "url", "status"]
EDITOR_REQUIRED_COLUMNS = ["queue_id", "decision", "editor_score", "review_required", "reasons"]
VALID_DECISIONS = {"ready_for_body", "needs_experience", "needs_product_check", "needs_outline_fix", "blocked"}
YMYL_TERMS = ["\u7f8e\u5bb9", "\u5065\u5eb7", "AGA", "\u533b\u7642", "\u85ac", "\u75c5\u6c17", "\u6cbb\u7642", "\u6295\u8cc7", "\u91d1\u878d", "\u526f\u696d", "\u6cd5\u5f8b", "\u7a0e\u91d1"]
RISK_TERMS = ["\u602a\u3057\u3044", "\u5fc5\u305a\u5132\u304b\u308b", "\u7d76\u5bfe", "\u6cbb\u308b", "\u526f\u4f5c\u7528\u306a\u3057"]
ACTIVE_OFFER_STATUSES = {"", "active", "candidate", "open"}


@dataclass
class ReviewResult:
    queue_id: str
    outline_file: str
    keyword: str
    article_title: str
    decision: str
    review_score: int
    missing_items: list[str]
    review_notes: list[str]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), [{k: (v or "") for k, v in row.items()} for row in reader]


def require_columns(file_name: str, columns: list[str], required: list[str]) -> None:
    missing = [column for column in required if column not in columns]
    if missing:
        raise SystemExit(f"Missing required CSV columns in {file_name}: {', '.join(missing)}")


def split_ids(value: str) -> list[str]:
    return [part.strip() for part in (value or "").replace(",", ";").split(";") if part.strip()]


def active_offers(product_ids: list[str], offers: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        offer
        for offer in offers
        if offer.get("product_id", "") in product_ids and offer.get("status", "").strip().lower() in ACTIVE_OFFER_STATUSES
    ]


def is_rss_candidate(queue_row: dict[str, str]) -> bool:
    return (
        queue_row.get("status", "").strip() == "candidate_from_rss"
        or "source=rss" in queue_row.get("notes", "")
    )


def has_any(text: str, terms: list[str]) -> list[str]:
    lower = text.lower()
    return [term for term in terms if term.lower() in lower]


def section_present(text: str, markers: list[str]) -> bool:
    return any(marker in text for marker in markers)


def count_lines_containing(text: str, marker: str) -> int:
    return sum(1 for line in text.splitlines() if marker in line)


def outline_file_for(queue_id: str) -> Path:
    return OUTLINE_DIR / f"{queue_id}_outline.md"


def decide(score: int, missing: list[str], weak_alternative: bool, product_or_offer_unclear: bool, risk: bool) -> str:
    if risk:
        return "blocked"
    if "h2_h3_outline" in missing or "search_intent" in missing:
        return "needs_outline_fix"
    if weak_alternative:
        return "needs_experience"
    if product_or_offer_unclear:
        return "needs_product_check"
    if missing:
        return "needs_outline_fix"
    if score >= 80:
        return "ready_for_body"
    if score >= 60:
        return "needs_outline_fix"
    return "blocked"


def evaluate_outline(
    queue_row: dict[str, str],
    editor_row: dict[str, str],
    products_by_id: dict[str, dict[str, str]],
    offers: list[dict[str, str]],
    rss_product_checks: dict[str, dict[str, str]],
) -> ReviewResult:
    queue_id = queue_row.get("queue_id", "")
    outline_path = outline_file_for(queue_id)
    outline_text = outline_path.read_text(encoding="utf-8-sig") if outline_path.exists() else ""
    product_ids = split_ids(queue_row.get("assigned_product_ids", ""))
    matched_products = [products_by_id[pid] for pid in product_ids if pid in products_by_id]
    matched_offers = active_offers(product_ids, offers)
    article_type = queue_row.get("article_type", "")
    rss_check = rss_product_checks.get(queue_id, {}) if is_rss_candidate(queue_row) else {}
    rss_ready_for_body_prompt = rss_check.get("decision", "").strip() == "ready_for_body_prompt"
    rss_url_needs_check = rss_ready_for_body_prompt and (
        "needs_url_check" in " ".join([
            rss_check.get("product_candidates", ""),
            rss_check.get("offer_candidates", ""),
            rss_check.get("product_card_candidate", ""),
            rss_check.get("cta_policy", ""),
            rss_check.get("pre_body_checks", ""),
        ])
        or 'amazon_url: ""' in rss_check.get("product_card_candidate", "")
        or 'rakuten_url: ""' in rss_check.get("product_card_candidate", "")
    )
    combined_text = " ".join([
        outline_text,
        queue_row.get("keyword", ""),
        queue_row.get("article_title", ""),
        queue_row.get("notes", ""),
        editor_row.get("reasons", ""),
        " ".join(product.get("name", "") + " " + product.get("tags", "") for product in matched_products),
        " ".join(offer.get("platform", "") + " " + offer.get("url", "") for offer in matched_offers),
    ])

    score = 100
    missing: list[str] = []
    notes: list[str] = []

    checks = [
        ("search_intent", section_present(outline_text, ["\u691c\u7d22\u610f\u56f3", "\u8aad\u8005\u610f\u56f3", "\u610f\u56f3"])),
        ("audience", section_present(outline_text, ["\u60f3\u5b9a\u8aad\u8005", "\u8aad\u8005\u50cf", "\u8aad\u8005"])),
        ("h2_h3_outline", count_lines_containing(outline_text, "H2:") >= 3 and count_lines_containing(outline_text, "H3:") >= 3),
        ("cta_policy", "CTA" in outline_text),
        ("product_or_offer", rss_ready_for_body_prompt or (bool(matched_products or matched_offers) and ("p_test_" in outline_text or "o_test_" in outline_text))),
        ("experience_required", section_present(outline_text, ["\u5b9f\u4f53\u9a13", "\u4f53\u9a13", "experience"])),
        ("no_experience_alternative", section_present(outline_text, ["\u4ee3\u66ff\u65b9\u91dd", "\u4ee3\u66ff", "alternative"])),
        ("expression_notes", section_present(outline_text, ["\u6ce8\u610f\u3059\u3079\u304d\u8868\u73fe", "\u8868\u73fe\u4e0a\u306e\u6ce8\u610f", "\u8868\u73fe"])),
        ("pre_body_checks", section_present(outline_text, ["\u672c\u6587\u751f\u6210\u524d", "\u751f\u6210\u524d\u306e\u78ba\u8a8d", "\u78ba\u8a8d\u4e8b\u9805"])),
    ]

    for item, ok in checks:
        if ok:
            notes.append(f"{item}=ok")
        else:
            missing.append(item)
            score -= 10
            notes.append(f"{item}=missing")

    experience_needed = article_type in {"review", "howto", "comparison"}
    alternative_lines = [
        line for line in outline_text.splitlines()
        if any(marker in line for marker in [
            "\u4ee3\u66ff\u65b9\u91dd",
            "\u516c\u958b\u60c5\u5831",
            "\u516c\u5f0f\u60c5\u5831",
            "\u8ca9\u58f2\u60c5\u5831",
            "\u8abf\u67fb",
            "\u6bd4\u8f03",
            "\u4f53\u9a13\u65ad\u5b9a",
            "\u672a\u78ba\u8a8d",
        ])
    ]
    weak_alternative = experience_needed and len(alternative_lines) < 2
    if weak_alternative:
        missing.append("weak_no_experience_alternative")
        score -= 20
        notes.append("experience_alternative=weak")
    else:
        notes.append("experience_alternative=ok")

    cta_present = "CTA" in outline_text
    cta_needs_check = "CTA???" in outline_text or "CTA?????" in outline_text
    no_product = not matched_products
    no_offer = not matched_offers
    product_or_offer_unclear = cta_present and ((no_product and no_offer) or cta_needs_check or (article_type == "howto" and no_offer))
    if rss_ready_for_body_prompt:
        product_or_offer_unclear = False
    if product_or_offer_unclear:
        missing.append("product_or_offer_cta_check")
        score -= 15
        notes.append("cta_product_offer=needs_check")
    else:
        notes.append("cta_product_offer=ok")

    if rss_ready_for_body_prompt:
        notes.append("rss_product_check=ready_for_body_prompt")
        if rss_url_needs_check:
            notes.append("url_check=needs_url_check")
            notes.append("strong_cta=not_allowed_until_url_confirmed")

    risk_matches = has_any(combined_text, YMYL_TERMS + RISK_TERMS)
    editor_review_required = editor_row.get("review_required", "").strip().lower() == "true"
    if risk_matches or editor_review_required:
        missing.append("risk_review")
        score -= 35
        notes.append("risk_detected=" + "/".join(risk_matches or ["editor_review_required"]))
    else:
        notes.append("risk=ok")

    score = max(0, min(100, score))
    decision = decide(score, missing, weak_alternative, product_or_offer_unclear, bool(risk_matches or editor_review_required))
    if decision not in VALID_DECISIONS:
        decision = "needs_outline_fix"

    return ReviewResult(
        queue_id=queue_id,
        outline_file=outline_path.relative_to(ROOT).as_posix(),
        keyword=queue_row.get("keyword", ""),
        article_title=queue_row.get("article_title", ""),
        decision=decision,
        review_score=score,
        missing_items=missing or ["none"],
        review_notes=notes,
    )


def write_csv_report(results: list[ReviewResult]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = ["queue_id", "outline_file", "keyword", "article_title", "decision", "review_score", "missing_items", "review_notes"]
    with REVIEW_REPORT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow({
                "queue_id": result.queue_id,
                "outline_file": result.outline_file,
                "keyword": result.keyword,
                "article_title": result.article_title,
                "decision": result.decision,
                "review_score": result.review_score,
                "missing_items": ";".join(result.missing_items),
                "review_notes": " | ".join(result.review_notes),
            })


def write_md_report(results: list[ReviewResult]) -> None:
    counts = {decision: 0 for decision in ["ready_for_body", "needs_experience", "needs_product_check", "needs_outline_fix", "blocked"]}
    for result in results:
        counts[result.decision] = counts.get(result.decision, 0) + 1

    lines = [
        "# Outline Review Report",
        "",
        f"Total: {len(results)}",
        f"ready_for_body: {counts['ready_for_body']}",
        f"needs_experience: {counts['needs_experience']}",
        f"needs_product_check: {counts['needs_product_check']}",
        f"needs_outline_fix: {counts['needs_outline_fix']}",
        f"blocked: {counts['blocked']}",
        "",
        "## Details",
        "",
    ]
    for result in results:
        lines.extend([
            f"### {result.queue_id}",
            f"- outline_file: {result.outline_file}",
            f"- decision: {result.decision}",
            f"- review_score: {result.review_score}",
            f"- missing_items: {';'.join(result.missing_items)}",
            f"- review_notes: {' | '.join(result.review_notes)}",
        ])
        if "url_check=needs_url_check" in result.review_notes:
            lines.append("- warning: URL未確認のため本文生成時は強い購入CTA禁止")
        lines.append("")
    REVIEW_REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    queue_columns, queue_rows = read_csv(QUEUE_CSV)
    product_columns, product_rows = read_csv(PRODUCTS_CSV)
    offer_columns, offer_rows = read_csv(OFFERS_CSV)
    editor_columns, editor_rows = read_csv(EDITOR_REPORT_CSV)
    _, rss_product_check_rows = read_csv(RSS_PRODUCT_CHECK_REPORT_CSV)

    require_columns("article_queue.csv", queue_columns, QUEUE_REQUIRED_COLUMNS)
    require_columns("products.csv", product_columns, PRODUCT_REQUIRED_COLUMNS)
    require_columns("offers.csv", offer_columns, OFFER_REQUIRED_COLUMNS)
    require_columns("editor_score_report.csv", editor_columns, EDITOR_REQUIRED_COLUMNS)

    queue_by_id = {row.get("queue_id", ""): row for row in queue_rows if row.get("queue_id", "")}
    products_by_id = {row.get("product_id", ""): row for row in product_rows if row.get("product_id", "")}
    rss_product_checks = {row.get("queue_id", ""): row for row in rss_product_check_rows if row.get("queue_id", "")}
    write_now_rows = [row for row in editor_rows if row.get("decision", "").strip() == "write_now"]

    results: list[ReviewResult] = []
    for editor_row in write_now_rows:
        queue_id = editor_row.get("queue_id", "")
        queue_row = queue_by_id.get(queue_id)
        if not queue_row:
            results.append(ReviewResult(
                queue_id=queue_id,
                outline_file=outline_file_for(queue_id).relative_to(ROOT).as_posix(),
                keyword="",
                article_title="",
                decision="blocked",
                review_score=0,
                missing_items=["missing_article_queue_row"],
                review_notes=["queue_row=missing"],
            ))
            continue
        results.append(evaluate_outline(queue_row, editor_row, products_by_id, offer_rows, rss_product_checks))

    write_csv_report(results)
    write_md_report(results)

    print(f"reviewed={len(results)} csv={REVIEW_REPORT_CSV} md={REVIEW_REPORT_MD}")
    for result in results:
        print(f"{result.queue_id}\t{result.decision}\t{result.review_score}")


if __name__ == "__main__":
    main()
