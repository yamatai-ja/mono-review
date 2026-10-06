"""Run the optional SEOmator CLI without adding it as a project dependency.

Repository policy requires explicit confirmation before adding dependencies.
This wrapper therefore uses an already-installed `seomator` executable and
fails with setup instructions when it is absent.

No paid SEO service is required by this wrapper.
"""
from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
from pathlib import Path


def build_command(
    executable: str,
    site: str,
    output: Path,
    *,
    crawl: bool,
    max_pages: int,
    with_cwv: bool,
) -> list[str]:
    command = [
        executable,
        "audit",
        site,
        "--format",
        "llm",
        "--output",
        str(output),
    ]
    if crawl:
        command.extend(["--crawl", "--max-pages", str(max(1, max_pages))])
    if not with_cwv:
        command.append("--no-cwv")
    return command


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run dependency-optional SEOmator technical SEO audit"
    )
    parser.add_argument("--site", default="https://monoslog.com")
    parser.add_argument("--output", default="output/seo_audit.llm.txt")
    parser.add_argument("--crawl", action="store_true")
    parser.add_argument("--max-pages", type=int, default=50)
    parser.add_argument("--with-cwv", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    executable = shutil.which("seomator")
    if not executable:
        print(
            json.dumps(
                {
                    "status": "blocked_missing_optional_dependency",
                    "required_executable": "seomator",
                    "project_dependency_added": False,
                    "paid_service_required": False,
                    "install_if_approved": "npm install -g @seomator/seo-audit",
                    "reason": (
                        "AGENTS.md forbids adding dependencies without explicit confirmation. "
                        "Install SEOmator separately, then rerun this command."
                    ),
                },
                ensure_ascii=False,
            )
        )
        return 2

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = build_command(
        executable,
        args.site,
        output,
        crawl=args.crawl,
        max_pages=args.max_pages,
        with_cwv=args.with_cwv,
    )

    if args.dry_run:
        print(
            json.dumps(
                {
                    "status": "dry_run",
                    "command": shlex.join(command),
                    "output": str(output),
                },
                ensure_ascii=False,
            )
        )
        return 0

    completed = subprocess.run(command, check=False)
    print(
        json.dumps(
            {
                "status": "completed" if completed.returncode == 0 else "failed",
                "returncode": completed.returncode,
                "output": str(output),
                "site": args.site,
                "crawl": args.crawl,
                "max_pages": args.max_pages if args.crawl else 1,
                "with_cwv": args.with_cwv,
            },
            ensure_ascii=False,
        )
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
