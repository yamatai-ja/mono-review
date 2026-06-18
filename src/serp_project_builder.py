from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECTS_DIR = ROOT / "output" / "serp_projects"


def slugify(keyword: str) -> str:
    text = keyword.strip().lower()
    replacements = {
        "違い": " difference ",
        "比較": " comparison ",
        "選び方": " selection ",
        "注意点": " checklist ",
        "対策": " fix ",
        "原因": " cause ",
        "必要か": " need ",
        "どっち": " which ",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    parts = [part for part in text.strip("-").split("-") if part]

    # Keep common product comparison slugs compact: fire-tv-cube-fire-tv-stick -> fire-tv-cube-stick.
    compacted: list[str] = []
    i = 0
    while i < len(parts):
        if (
            i + 4 < len(parts)
            and parts[i : i + 2] == ["fire", "tv"]
            and parts[i + 3 : i + 5] == ["fire", "tv"]
        ):
            compacted.extend(parts[i : i + 3])
            i += 5
            continue
        compacted.append(parts[i])
        i += 1
    return "-".join(compacted) or "serp-project"


def write_urls_csv(path: Path, limit: int = 10) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["rank", "title", "url"])
        writer.writeheader()
        for rank in range(1, limit + 1):
            writer.writerow({"rank": rank, "title": "", "url": ""})


def notebook_sources(keyword: str) -> str:
    return "\n".join(
        [
            "# NotebookLM投入素材",
            "",
            f"keyword: {keyword}",
            "",
            "## 公式ページ",
            "",
            "- ",
            "",
            "## SERP上位記事",
            "",
            "- ",
            "",
            "## 自サイト記事",
            "",
            "- ",
            "",
            "## その他参考資料",
            "",
            "- ",
            "",
            "## 人間確認メモ",
            "",
            "- NotebookLM出力は事実として扱わない",
            "- 価格、在庫、仕様、保証、対応サービスは公式情報で確認する",
            "- 本文生成前に未確認情報を分ける",
            "",
        ]
    )


def notebook_notes() -> str:
    return "\n".join(
        [
            "# NotebookLM分析メモ",
            "",
            "## 共通見出し",
            "",
            "- ",
            "",
            "## FAQ候補",
            "",
            "- ",
            "",
            "## 読者の不安",
            "",
            "- ",
            "",
            "## 比較軸",
            "",
            "- ",
            "",
            "## 競合記事が弱い論点",
            "",
            "- ",
            "",
            "## 自サイト差別化ポイント",
            "",
            "- ",
            "",
            "## problem_prompt_builderへ渡す素材",
            "",
            "- target_keyword:",
            "- search_intent:",
            "- must_include_points:",
            "- avoid_claims:",
            "- related_internal_links:",
            "",
        ]
    )


def serp_analysis(keyword: str, slug: str) -> str:
    return "\n".join(
        [
            "# SERP Analysis",
            "",
            "## Basic Info",
            "",
            f"- keyword: {keyword}",
            f"- slug: {slug}",
            "- article_type: problem_solution",
            "- related_product:",
            "- related_parent_article:",
            "- analysis_status: draft",
            "",
            "## Search Intent Priority",
            "",
            "| Priority | Search Intent | Reader Situation | Must Answer |",
            "| --- | --- | --- | --- |",
            "| 1 |  |  |  |",
            "| 2 |  |  |  |",
            "| 3 |  |  |  |",
            "",
            "## Reader Concerns",
            "",
            "- ",
            "- ",
            "- ",
            "",
            "## FAQ Candidates",
            "",
            "| Question | Intent | Needs Official Check |",
            "| --- | --- | --- |",
            "|  |  | yes/no |",
            "|  |  | yes/no |",
            "|  |  | yes/no |",
            "",
            "## Purchase Checklist",
            "",
            "- ",
            "- ",
            "- ",
            "",
            "## Comparison Axes",
            "",
            "- ",
            "- ",
            "- ",
            "",
            "## Competitor Gaps",
            "",
            "- ",
            "- ",
            "- ",
            "",
            "## Differentiation Points",
            "",
            "- ",
            "- ",
            "- ",
            "",
            "## Official Check Required",
            "",
            "| Item | Source To Check | Status |",
            "| --- | --- | --- |",
            "|  |  | unchecked |",
            "|  |  | unchecked |",
            "|  |  | unchecked |",
            "",
            "## Human Verification Required",
            "",
            "- NotebookLM出力を事実として扱わない",
            "- 公式情報が必要な項目を分ける",
            "- 未確認情報を本文で断定しない",
            "- 商品押し売りではなく悩み解決記事にする",
            "- FAQ候補が検索意図に沿っているか確認する",
            "",
            "## Input For problem_prompt_builder",
            "",
            "- target_keyword:",
            "- search_intent:",
            "- primary_reader_concern:",
            "- must_include_points:",
            "- faq_candidates:",
            "- comparison_axes:",
            "- avoid_claims:",
            "- related_internal_links:",
            "- related_product_hint:",
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a SERP/NotebookLM project folder for one keyword.")
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--slug", default="")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    keyword = args.keyword.strip()
    slug = args.slug.strip() or slugify(keyword)
    project_dir = PROJECTS_DIR / slug

    if project_dir.exists() and not args.overwrite:
        print("project_created=false")
        print(f"slug={slug}")
        print(f"project_dir={project_dir}")
        print("error=project_dir_already_exists")
        print("hint=use --overwrite only after confirming existing files")
        return 1

    project_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "urls.csv": lambda path: write_urls_csv(path),
        "notebook_sources.md": lambda path: path.write_text(notebook_sources(keyword), encoding="utf-8"),
        "notebook_notes.md": lambda path: path.write_text(notebook_notes(), encoding="utf-8"),
        "serp_analysis.md": lambda path: path.write_text(serp_analysis(keyword, slug), encoding="utf-8"),
    }

    generated_files: list[Path] = []
    for filename, writer in files.items():
        output_path = project_dir / filename
        writer(output_path)
        generated_files.append(output_path)

    print("project_created=true")
    print(f"slug={slug}")
    print(f"project_dir={project_dir}")
    print("generated_files=" + ",".join(str(path) for path in generated_files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
