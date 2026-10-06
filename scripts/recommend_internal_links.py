"""Recommend contextual internal links for Astro Markdown posts.

Complements scripts/audit_internal_links.mjs: the existing audit finds broken
references and orphan pages; this module proposes source -> target links without
editing any article automatically.

The recommender is deterministic and dependency-free. It uses title/category/tag
and heading/body character-bigram similarity so Japanese text works without a
tokenizer. Recommendations below the minimum similarity are omitted rather than
forced.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

BLOG_LINK_RE = re.compile(
    r"(?:https?://(?:www\\.)?monoslog\\.com)?/blog/([^\\s\\)\\\"'#?<>]+)",
    re.I,
)
HEADING_RE = re.compile(r"^#{2,3}\\s+(.+?)\\s*$", re.M)
MARKDOWN_LINK_RE = re.compile(r"\\[([^\\]]+)\\]\\([^)]*\\)")
HTML_TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\\s+")
CSV_FIELDS = (
    "source_slug",
    "source_title",
    "target_slug",
    "target_title",
    "similarity",
    "suggested_anchor",
    "placement_heading",
    "reason",
)


@dataclass(frozen=True)
class Post:
    path: Path
    slug: str
    title: str
    draft: bool
    categories: tuple[str, ...]
    tags: tuple[str, ...]
    related_posts: tuple[str, ...]
    body: str
    headings: tuple[str, ...]
    links: frozenset[str]


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _list_value(value: str) -> tuple[str, ...]:
    value = value.strip()
    if not value:
        return ()
    if value.startswith("[") and value.endswith("]"):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return tuple(str(item).strip() for item in parsed if str(item).strip())
    return tuple(
        item
        for item in (_strip_quotes(part.strip()) for part in value.split(","))
        if item
    )


def _split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    end = next((i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    if end is None:
        return {}, text

    metadata: dict[str, object] = {}
    active_list: str | None = None
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.lstrip().startswith("- ") and active_list:
            current = list(metadata.get(active_list) or ())
            item = _strip_quotes(raw.lstrip()[2:].strip())
            if item:
                current.append(item)
            metadata[active_list] = tuple(current)
            continue
        if ":" not in raw:
            continue
        key, raw_value = raw.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        active_list = None
        if key in {"categories", "tags", "relatedPosts"}:
            metadata[key] = _list_value(value)
            if not value:
                active_list = key
        elif key == "draft":
            metadata[key] = value.casefold() == "true"
        else:
            metadata[key] = _strip_quotes(value)

    body = "\\n".join(lines[end + 1 :])
    return metadata, body


def _normalize_slug(value: object) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^https?://(?:www\\.)?monoslog\\.com", "", text, flags=re.I)
    text = re.sub(r"^/?blog/", "", text)
    text = re.sub(r"[?#].*$", "", text).strip("/")
    return text


def _visible_text(markdown: str) -> str:
    text = MARKDOWN_LINK_RE.sub(r"\\1", markdown)
    text = HTML_TAG_RE.sub(" ", text)
    text = re.sub(r"[#*_>\x60~|=-]+", " ", text)
    return html.unescape(SPACE_RE.sub(" ", text)).strip()


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return "".join(ch for ch in value if ch.isalnum() or "\\u3040" <= ch <= "\\u30ff" or "\\u3400" <= ch <= "\\u9fff")


def _grams(value: str) -> set[str]:
    text = _normalize(value)
    if not text:
        return set()
    if len(text) < 2:
        return {text}
    return {text[i : i + 2] for i in range(len(text) - 1)}


def _similarity(left: str, right: str) -> float:
    a, b = _grams(left), _grams(right)
    if not a or not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _semantic_meta(post: Post) -> str:
    return " ".join((post.title, *post.categories, *post.tags, *post.headings))


def _post_similarity(source: Post, target: Post) -> float:
    meta = _similarity(_semantic_meta(source), _semantic_meta(target))
    body = _similarity(_visible_text(source.body)[:3000], _visible_text(target.body)[:3000])
    return round(meta * 0.7 + body * 0.3, 6)


def _placement_heading(source: Post, target: Post) -> str:
    if not source.headings:
        return "本文中の関連トピック段落（手動確認）"
    target_text = " ".join((target.title, *target.categories, *target.tags))
    scored = [(_similarity(heading, target_text), heading) for heading in source.headings]
    scored.sort(key=lambda item: (-item[0], item[1]))
    best_score, best_heading = scored[0]
    return best_heading if best_score > 0 else "本文中の関連トピック段落（手動確認）"


def load_posts(posts_dir: Path | str) -> list[Post]:
    root = Path(posts_dir)
    posts: list[Post] = []
    for path in sorted([*root.rglob("*.md"), *root.rglob("*.mdx")]):
        text = path.read_text(encoding="utf-8")
        metadata, body = _split_frontmatter(text)
        slug = _normalize_slug(metadata.get("slug") or path.stem)
        title = str(metadata.get("title") or slug).strip()
        categories = tuple(metadata.get("categories") or ())
        tags = tuple(metadata.get("tags") or ())
        related = tuple(_normalize_slug(item) for item in (metadata.get("relatedPosts") or ()))
        links = {
            _normalize_slug(match.group(1))
            for match in BLOG_LINK_RE.finditer(body)
            if _normalize_slug(match.group(1))
        }
        links.update(item for item in related if item)
        posts.append(
            Post(
                path=path,
                slug=slug,
                title=title,
                draft=bool(metadata.get("draft") is True),
                categories=categories,
                tags=tags,
                related_posts=related,
                body=body,
                headings=tuple(h.strip() for h in HEADING_RE.findall(body) if h.strip()),
                links=frozenset(links),
            )
        )
    return posts


def build_recommendations(
    posts: Iterable[Post],
    *,
    top_n: int = 3,
    min_similarity: float = 0.04,
    target_slug: str | None = None,
) -> dict[str, object]:
    published = [post for post in posts if not post.draft and post.slug]
    inbound: dict[str, set[str]] = {post.slug: set() for post in published}
    for source in published:
        for target in source.links:
            if target in inbound and target != source.slug:
                inbound[target].add(source.slug)

    if target_slug:
        targets = [post for post in published if post.slug == _normalize_slug(target_slug)]
    else:
        targets = [post for post in published if not inbound.get(post.slug)]

    recommendations: list[dict[str, object]] = []
    for target in targets:
        candidates: list[tuple[float, Post]] = []
        for source in published:
            if source.slug == target.slug or target.slug in source.links:
                continue
            score = _post_similarity(source, target)
            if score >= min_similarity:
                candidates.append((score, source))
        candidates.sort(key=lambda item: (-item[0], item[1].slug))
        for score, source in candidates[: max(1, top_n)]:
            recommendations.append(
                {
                    "source_slug": source.slug,
                    "source_title": source.title,
                    "target_slug": target.slug,
                    "target_title": target.title,
                    "similarity": score,
                    "suggested_anchor": target.title,
                    "placement_heading": _placement_heading(source, target),
                    "reason": "topic_similarity_for_orphan_or_requested_target",
                }
            )

    return {
        "schema_version": "internal-link-recommendations-v1",
        "published_posts": len(published),
        "targets_checked": len(targets),
        "orphan_slugs": sorted(slug for slug, sources in inbound.items() if not sources),
        "recommendation_count": len(recommendations),
        "recommendations": recommendations,
        "semantics": {
            "advisory_only": True,
            "auto_edit": False,
            "minimum_similarity": min_similarity,
            "top_n_per_target": top_n,
            "placement_heading_requires_human_confirmation": True,
        },
    }


def write_outputs(report: dict[str, object], *, csv_path: Path, md_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in report["recommendations"]:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})

    lines = [
        "# Internal Link Recommendations",
        "",
        f"- published_posts: {report['published_posts']}",
        f"- targets_checked: {report['targets_checked']}",
        f"- recommendation_count: {report['recommendation_count']}",
        "",
        "Recommendations are advisory. Confirm the source paragraph and reader relevance before editing.",
        "",
    ]
    for row in report["recommendations"]:
        lines.extend(
            [
                f"## {row['source_title']} → {row['target_title']}",
                "",
                f"- source: /blog/{row['source_slug']}",
                f"- target: /blog/{row['target_slug']}",
                f"- suggested_anchor: {row['suggested_anchor']}",
                f"- placement_heading: {row['placement_heading']}",
                f"- similarity: {row['similarity']:.4f}",
                "",
            ]
        )
    md_path.write_text("\\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Recommend contextual internal links without editing posts")
    parser.add_argument("--posts-dir", default="src/content/posts")
    parser.add_argument("--output-csv", default="output/internal_link_recommendations.csv")
    parser.add_argument("--output-md", default="output/internal_link_recommendations.md")
    parser.add_argument("--top-n", type=int, default=3)
    parser.add_argument("--min-similarity", type=float, default=0.04)
    parser.add_argument("--target-slug")
    args = parser.parse_args()

    report = build_recommendations(
        load_posts(args.posts_dir),
        top_n=args.top_n,
        min_similarity=args.min_similarity,
        target_slug=args.target_slug,
    )
    write_outputs(
        report,
        csv_path=Path(args.output_csv),
        md_path=Path(args.output_md),
    )
    print(json.dumps({
        "published_posts": report["published_posts"],
        "targets_checked": report["targets_checked"],
        "recommendation_count": report["recommendation_count"],
        "output_csv": args.output_csv,
        "output_md": args.output_md,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
