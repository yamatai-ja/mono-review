from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path

try:
    from .article_quality_checker import check_article, load_simple_yaml
    from .markdown_post_auditor import audit_post
    from .publication_risk_checker import (
        PublicationRiskResult,
        article_type_from_frontmatter,
        classify_publication_risk,
    )
except ImportError:  # Support direct CLI execution from src/.
    from article_quality_checker import check_article, load_simple_yaml
    from markdown_post_auditor import audit_post
    from publication_risk_checker import (
        PublicationRiskResult,
        article_type_from_frontmatter,
        classify_publication_risk,
    )


ROOT = Path(__file__).resolve().parents[1]
QUALITY_REPORT_CSV = ROOT / "output" / "article_quality_report.csv"
POSTS_DIR = ROOT / "src" / "content" / "posts"
PROFILE_DIR = ROOT / "src" / "article_profiles"


def run_command(command: list[str]) -> tuple[int, str]:
    env = os.environ.copy()
    if command and command[0] == "npm":
        env.setdefault("ASTRO_TELEMETRY_DISABLED", "1")
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except FileNotFoundError:
        if command and command[0] == "npm":
            result = subprocess.run(
                ["npm.cmd", *command[1:]],
                cwd=ROOT,
                env=env,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        else:
            raise
    return result.returncode, result.stdout


def read_quality_row(slug: str, article_type: str, draft_file: str) -> dict[str, str]:
    if not QUALITY_REPORT_CSV.exists():
        return {}
    normalized_draft = draft_file.replace("\\", "/")
    with QUALITY_REPORT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if (
                row.get("slug", "").strip() == slug
                and row.get("article_type", "").strip() == article_type
                and row.get("draft_file", "").replace("\\", "/").strip() == normalized_draft
            ):
                return {key: (value or "") for key, value in row.items()}
    return {}


def evaluate_publication_risk(
    article_type: str,
    draft_file: str,
    title: str = "",
) -> PublicationRiskResult:
    draft_path = Path(draft_file)
    if not draft_path.is_absolute():
        draft_path = ROOT / draft_path
    if not draft_path.exists():
        raise ValueError(f"draft file not found: {draft_file}")

    profile_path = PROFILE_DIR / f"{article_type}.yaml"
    if not profile_path.exists():
        raise ValueError(f"article profile not found: {profile_path}")

    markdown = draft_path.read_text(encoding="utf-8")
    classification_text = f"{title}\n{markdown}" if title else markdown
    return classify_publication_risk(classification_text, load_simple_yaml(profile_path))


def publication_risk_lines(result: PublicationRiskResult) -> list[str]:
    return [
        f"publication_risk={result.level}",
        f"detected_terms={','.join(result.detected_terms) or 'none'}",
        f"required_human_checks={';'.join(result.required_tasks)}",
        f"research_notes_required={'yes' if result.research_notes_required else 'no'}",
    ]


def print_publication_risk(result: PublicationRiskResult) -> None:
    for line in publication_risk_lines(result):
        print(line)


def resolve_article_path(article_file: str) -> Path:
    path = Path(article_file)
    return path if path.is_absolute() else ROOT / path


def check_only_lines(
    article_file: str,
    article_type_override: str | None = None,
    title: str = "",
) -> list[str]:
    article_path = resolve_article_path(article_file)
    if not article_path.exists():
        raise ValueError(f"article file not found: {article_file}")

    markdown = article_path.read_text(encoding="utf-8")
    article_type = article_type_override or article_type_from_frontmatter(markdown)
    if not article_type:
        raise ValueError("article_type is missing; pass --article-type")

    profile_path = PROFILE_DIR / f"{article_type}.yaml"
    if not profile_path.exists():
        raise ValueError(f"article profile not found: {profile_path}")
    profile = load_simple_yaml(profile_path)

    quality_score, quality_decision, failed, warnings, _ = check_article(markdown, profile)
    classification_text = f"{title}\n{markdown}" if title else markdown
    risk_result = classify_publication_risk(classification_text, profile)
    audit_row = audit_post(article_path, "check-only")
    draft = audit_row.get("draft", "") or "unknown"

    return [
        "check_only=true",
        f"article_file={article_path}",
        f"article_type={article_type}",
        f"quality_score={quality_score}",
        f"quality_decision={quality_decision}",
        f"quality_failed_checks={';'.join(failed) or 'none'}",
        f"quality_warnings={';'.join(warnings) or 'none'}",
        *publication_risk_lines(risk_result),
        f"markdown_audit_decision={audit_row.get('decision', 'unknown')}",
        f"markdown_failed_checks={audit_row.get('failed_checks', 'none')}",
        f"markdown_warnings={audit_row.get('warnings', 'none')}",
        f"draft={draft}",
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run quality check, Astro draft generation, npm check, and npm build for one article."
    )
    parser.add_argument(
        "--check-only",
        metavar="ARTICLE_FILE",
        help="Check an existing Markdown file without writing files or running npm.",
    )
    parser.add_argument("--article-type")
    parser.add_argument("--slug")
    parser.add_argument("--title")
    parser.add_argument("--draft-file")
    parser.add_argument("--category")
    parser.add_argument("--tags")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Pass --overwrite to astro_markdown_builder.py when the target Markdown already exists.",
    )
    args = parser.parse_args()
    if not args.check_only:
        required = ["article_type", "slug", "title", "draft_file", "category", "tags"]
        missing = [f"--{name.replace('_', '-')}" for name in required if not getattr(args, name)]
        if missing:
            parser.error("the following arguments are required: " + ", ".join(missing))
    return args


def main() -> int:
    args = parse_args()
    if args.check_only:
        try:
            lines = check_only_lines(args.check_only, args.article_type, args.title or "")
        except (OSError, ValueError) as exc:
            print(f"check_only_error={exc}")
            return 1
        for line in lines:
            print(line)
        return 0

    generated_file = POSTS_DIR / f"{args.slug}.md"

    try:
        risk_result = evaluate_publication_risk(args.article_type, args.draft_file, args.title)
    except (OSError, ValueError) as exc:
        print("publication_risk=error")
        print("detected_terms=none")
        print("required_human_checks=unavailable")
        print("research_notes_required=unknown")
        print(f"publication_risk_error={exc}")
        print("final_status=risk_check_failed")
        return 1
    print_publication_risk(risk_result)

    quality_command = [
        sys.executable,
        "src/article_quality_checker.py",
        "--article-type",
        args.article_type,
        "--draft-file",
        args.draft_file,
        "--slug",
        args.slug,
    ]
    quality_code, quality_output = run_command(quality_command)
    quality_row = read_quality_row(args.slug, args.article_type, args.draft_file)
    quality_score = quality_row.get("quality_score", "")
    decision = quality_row.get("decision", "")

    if quality_code != 0 or decision != "ready_for_astro_candidate":
        print(f"quality_score={quality_score or '0'}")
        print(f"decision={decision or 'error'}")
        print(f"generated_file={generated_file}")
        print("npm_check_result=skipped")
        print("npm_build_result=skipped")
        print("final_status=needs_edit")
        if quality_output.strip():
            print("quality_output:")
            print(quality_output.strip())
        return 1

    builder_command = [
        sys.executable,
        "src/astro_markdown_builder.py",
        "--article-type",
        args.article_type,
        "--slug",
        args.slug,
        "--title",
        args.title,
        "--draft-file",
        args.draft_file,
        "--category",
        args.category,
        "--tags",
        args.tags,
        "--apply",
    ]
    if args.overwrite:
        builder_command.append("--overwrite")

    builder_code, builder_output = run_command(builder_command)
    if builder_code != 0:
        print(f"quality_score={quality_score}")
        print(f"decision={decision}")
        print(f"generated_file={generated_file}")
        print("npm_check_result=skipped")
        print("npm_build_result=skipped")
        print("final_status=build_failed")
        print("astro_builder_output:")
        print(builder_output.strip())
        return 1

    check_code, check_output = run_command(["npm", "run", "check"])
    if check_code != 0:
        print(f"quality_score={quality_score}")
        print(f"decision={decision}")
        print(f"generated_file={generated_file}")
        print("npm_check_result=failed")
        print("npm_build_result=skipped")
        print("final_status=build_failed")
        print("npm_check_output:")
        print(check_output.strip())
        return 1

    build_code, build_output = run_command(["npm", "run", "build"])
    if build_code != 0:
        print(f"quality_score={quality_score}")
        print(f"decision={decision}")
        print(f"generated_file={generated_file}")
        print("npm_check_result=success")
        print("npm_build_result=failed")
        print("final_status=build_failed")
        print("npm_build_output:")
        print(build_output.strip())
        return 1

    print(f"quality_score={quality_score}")
    print(f"decision={decision}")
    print(f"generated_file={generated_file}")
    print("npm_check_result=success")
    print("npm_build_result=success")
    print("final_status=ready_for_publish_review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
