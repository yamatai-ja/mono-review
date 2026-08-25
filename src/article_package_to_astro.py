from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = ROOT / "src" / "content" / "posts"
ALLOWED_MONETIZATION = {"AFFILIATE", "ADSENSE", "HYBRID", "LEAD_GENERATION"}
TYPE_MAP = {
    "comparison": "comparison", "比較": "comparison",
    "selection": "selection", "選び方": "selection",
    "troubleshooting": "troubleshooting", "トラブル解決": "troubleshooting",
    "new_product": "new_product", "新商品": "new_product", "新商品・トレンド": "new_product",
    "review": "review", "guide": "guide", "other": "other", "その他": "other",
}


def q(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def arr(values: list[object]) -> str:
    return "[" + ", ".join(q(v) for v in values if str(v).strip()) + "]"


def first(data: dict, *paths: str, default=None):
    for path in paths:
        cur: object = data
        ok = True
        for key in path.split("."):
            if not isinstance(cur, dict) or key not in cur:
                ok = False
                break
            cur = cur[key]
        if ok and cur not in (None, "", []):
            return cur
    return default


def validate(pkg: dict) -> list[str]:
    errors: list[str] = []
    decision = str(first(pkg, "decision", "candidate.decision", default="")).upper()
    score = first(pkg, "score", "candidate.score", default=0)
    monetization = str(first(pkg, "monetization", "monetization.type", default="")).upper()
    evidence = first(pkg, "evidence", "evidence.items", default=[])
    primary_count = sum(1 for e in evidence if isinstance(e, dict) and str(e.get("type", e.get("tier", ""))).upper() in {"PRIMARY", "PRIMARY_EVIDENCE", "1"})
    mutable_ok = bool(first(pkg, "mutable_facts_verified", "verification.mutable_facts_verified", default=False))
    html = first(pkg, "completed_html", "article.completed_html", "article.html", default="")
    ad = first(pkg, "advertising_disclosure", "article.advertising_disclosure", default="")
    unsupported = first(pkg, "unsupported_claims", "quality.unsupported_claims", default=[])
    handoff = bool(first(pkg, "ready_for_handoff", "quality.ready_for_handoff", default=False))
    publish = bool(first(pkg, "publish", default=False))
    if decision != "WRITE": errors.append("decision must be WRITE")
    try:
        if float(score) < 85: errors.append("score must be >= 85")
    except (TypeError, ValueError): errors.append("score must be numeric")
    if monetization not in ALLOWED_MONETIZATION: errors.append("unsupported monetization")
    if not isinstance(evidence, list) or len(evidence) < 2: errors.append("at least 2 evidence items required")
    if primary_count < 1: errors.append("at least 1 primary evidence required")
    if not mutable_ok: errors.append("mutable facts must be verified")
    if not str(html).strip(): errors.append("completed HTML required")
    if not str(ad).strip(): errors.append("advertising disclosure required")
    if unsupported not in ([], None, False, 0): errors.append("unsupported claims must be empty")
    if not handoff: errors.append("ready_for_handoff must be true")
    if publish: errors.append("publish must remain false")
    return errors


def strip_metadata_sections(html: str) -> str:
    # Metadata belongs in frontmatter, never in the visible article body.
    return re.sub(r"<h[1-6][^>]*>\s*メタディスクリプション(?:案)?\s*</h[1-6]>.*?(?=<h[1-6]\b|$)", "", html, flags=re.I | re.S).strip()


def build(pkg: dict) -> tuple[str, str]:
    title = str(first(pkg, "title", "article.title", "brief.title", default="")).strip()
    slug = str(first(pkg, "slug", "article.slug", default="")).strip()
    if not title or not slug:
        raise ValueError("title and slug are required")
    description = str(first(pkg, "description", "article.description", "meta.description", default="")).strip()
    article_type_raw = str(first(pkg, "article_type", "brief.article_type", default="other")).strip()
    article_type = TYPE_MAP.get(article_type_raw, TYPE_MAP.get(article_type_raw.lower(), "other"))
    categories = first(pkg, "categories", "article.categories", default=["others"])
    tags = first(pkg, "tags", "article.tags", default=["others"])
    answer = str(first(pkg, "answer_summary", "brief.first_answer", "article.answer_summary", default="")).strip()
    verified_at = str(first(pkg, "verified_at", "verification.verified_at", default="")).strip()
    candidate_id = str(first(pkg, "candidate_id", "candidate.id", default="")).strip()
    monetization = str(first(pkg, "monetization", "monetization.type", default="")).upper()
    version = str(first(pkg, "package_version", "version", default="1.0"))
    html = strip_metadata_sections(str(first(pkg, "completed_html", "article.completed_html", "article.html", default="")))
    lines = ["---", f"title: {q(title)}", f"slug: {q(slug)}", "draft: true", f"article_type: {q(article_type)}"]
    if description: lines.append(f"description: {q(description)}")
    if candidate_id: lines.append(f"candidate_id: {q(candidate_id)}")
    if monetization: lines.append(f"monetization: {q(monetization)}")
    if answer: lines.append(f"answer_summary: {q(answer)}")
    if verified_at: lines.append(f"evidence_verified_at: {q(verified_at)}")
    lines += ["mutable_facts_verified: true", f"package_version: {q(version)}", f"categories: {arr(categories if isinstance(categories, list) else [categories])}", f"tags: {arr(tags if isinstance(tags, list) else [tags])}", "---", "", html, ""]
    return slug, "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="Convert a completed article-package-v1 JSON into an Astro draft.")
    p.add_argument("package")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args()
    pkg = json.loads(Path(args.package).read_text(encoding="utf-8"))
    errors = validate(pkg)
    if errors:
        print("ready_for_astro=no")
        for error in errors: print(f"error={error}")
        return 2
    slug, output = build(pkg)
    target = POSTS_DIR / f"{slug}.md"
    if target.exists() and not args.overwrite:
        raise SystemExit(f"output exists: {target}")
    print("ready_for_astro=yes")
    print(f"output_file={target}")
    print(f"would_write={'yes' if args.apply else 'no'}")
    if args.apply:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output, encoding="utf-8")
        print("written=yes")
    else:
        print("written=no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
