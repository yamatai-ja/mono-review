from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .article_quality_checker import load_simple_yaml, split_frontmatter
except ImportError:  # Support direct CLI execution from src/.
    from article_quality_checker import load_simple_yaml, split_frontmatter


ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = Path(__file__).resolve().parent / "article_profiles"


@dataclass(frozen=True)
class PublicationRiskResult:
    level: str
    high_matches: tuple[str, ...]
    medium_matches: tuple[str, ...]
    required_tasks: tuple[str, ...]


def find_terms(text: str, terms: list[str]) -> tuple[str, ...]:
    normalized = text.casefold()
    return tuple(term for term in terms if term and term.casefold() in normalized)


def require_string_list(config: dict[str, Any], key: str) -> list[str]:
    value = config.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"publication_risk.{key} must be a string list")
    return value


def classify_publication_risk(
    markdown: str,
    profile: dict[str, Any],
) -> PublicationRiskResult:
    config = profile.get("publication_risk")
    if not isinstance(config, dict):
        raise ValueError("publication_risk configuration is missing")

    high_matches = find_terms(markdown, require_string_list(config, "high_terms"))
    medium_matches = find_terms(markdown, require_string_list(config, "medium_terms"))

    if high_matches:
        level = "high"
    elif medium_matches:
        level = "medium"
    else:
        level = "low"

    required_tasks = list(require_string_list(config, "base_tasks"))
    if level in {"medium", "high"}:
        required_tasks.extend(require_string_list(config, "medium_extra_tasks"))
    if level == "high":
        required_tasks.extend(require_string_list(config, "high_extra_tasks"))

    return PublicationRiskResult(
        level=level,
        high_matches=high_matches,
        medium_matches=medium_matches,
        required_tasks=tuple(required_tasks),
    )


def article_type_from_frontmatter(markdown: str) -> str | None:
    frontmatter, _ = split_frontmatter(markdown)
    if frontmatter is None:
        return None
    match = re.search(r"(?m)^article_type\s*:\s*['\"]?([^'\"\s]+)", frontmatter)
    return match.group(1) if match else None


def resolve_article_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify the human publication-check intensity for an article."
    )
    parser.add_argument("article_file", help="Markdown article to classify.")
    parser.add_argument(
        "--article-type",
        help="Profile name. Defaults to article_type in frontmatter.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    article_path = resolve_article_path(args.article_file)
    if not article_path.exists():
        raise SystemExit(f"article file not found: {args.article_file}")

    markdown = article_path.read_text(encoding="utf-8")
    article_type = args.article_type or article_type_from_frontmatter(markdown)
    if not article_type:
        raise SystemExit("article_type is missing; pass --article-type")

    profile_path = PROFILE_DIR / f"{article_type}.yaml"
    if not profile_path.exists():
        raise SystemExit(f"article profile not found: {profile_path}")

    try:
        result = classify_publication_risk(markdown, load_simple_yaml(profile_path))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    print(f"article_type={article_type}")
    print(f"publication_risk={result.level}")
    print(f"high_matches={','.join(result.high_matches) or 'none'}")
    print(f"medium_matches={','.join(result.medium_matches) or 'none'}")
    print("required_tasks=" + ";".join(result.required_tasks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
