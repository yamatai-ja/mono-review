from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLUSTER_QUEUE = ROOT / "article_cluster_queue.csv"
PROMPT_DIR = ROOT / "output" / "cluster_body_prompts"


def run_step(label: str, command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"{label} failed: exit_code={result.returncode}")
    return result


def int_from_output(pattern: str, text: str) -> int:
    match = re.search(pattern, text)
    if not match:
        return 0
    return int(match.group(1))


def count_cluster_rows() -> int:
    if not CLUSTER_QUEUE.exists():
        return 0
    with CLUSTER_QUEUE.open("r", encoding="utf-8-sig") as f:
        return max(sum(1 for _ in f) - 1, 0)


def count_prompt_files() -> int:
    if not PROMPT_DIR.exists():
        return 0
    return sum(1 for path in PROMPT_DIR.glob("*.md") if path.is_file())


def run_dry_run() -> int:
    errors = 0
    try:
        cluster = run_step("cluster_generator", [sys.executable, "cluster_generator.py", "--dry-run"])
        cluster_output = f"{cluster.stdout}\n{cluster.stderr}"
        target_count = int_from_output(r"対象記事数:\s*(\d+)", cluster_output)
        planned_clusters = int_from_output(r"生成予定件数:\s*(\d+)", cluster_output)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        prompt = run_step("cluster_prompt_builder", [sys.executable, "cluster_prompt_builder.py", "--dry-run"])
        prompt_output = f"{prompt.stdout}\n{prompt.stderr}"
        planned_prompts = int_from_output(r"target_count=(\d+)", prompt_output)
    except RuntimeError as exc:
        errors += 1
        planned_prompts = 0
        print(str(exc), file=sys.stderr)

    print("pipeline summary:")
    print(f"対象記事数: {target_count}")
    print(f"クラスタ生成予定件数: {planned_clusters}")
    print(f"プロンプト生成予定件数: {planned_prompts}")
    print(f"エラー件数: {errors}")
    return 1 if errors else 0


def run_apply() -> int:
    try:
        run_step("cluster_generator", [sys.executable, "cluster_generator.py", "--apply"])
        before_prompts = count_prompt_files()
        run_step("cluster_prompt_builder", [sys.executable, "cluster_prompt_builder.py", "--apply"])
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    cluster_count = count_cluster_rows()
    prompt_count = count_prompt_files()
    written_prompt_count = max(prompt_count - before_prompts, 0)
    print("pipeline summary:")
    print(f"生成クラスタ件数: {cluster_count}")
    print(f"出力プロンプト件数: {written_prompt_count}")
    print(f"出力ディレクトリ: {PROMPT_DIR}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run cluster generation and GPTs prompt creation pipeline.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Run cluster and prompt steps without writing files.")
    group.add_argument("--apply", action="store_true", help="Generate cluster queue and GPTs prompt files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    exit_code = run_apply() if args.apply else run_dry_run()
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
