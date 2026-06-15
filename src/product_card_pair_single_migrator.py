from __future__ import annotations

import argparse
import hashlib
import re
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_REPORT = ROOT / "output" / "product_card_pair_single_migration_report.md"
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\((https?://[^)\s]+)\)")
MOJIBAKE_MARKERS = ("\ufffd", "\u00e3", "\u00c3")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dry-run single-post Rakuten+Amazon ProductCard pair migrator.",
    )
    parser.add_argument("--file", required=True, help="Target Markdown post file.")
    parser.add_argument("--product-name", help="Explicit product name for the pair candidate.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the migration. Without this flag, runs as dry-run.",
    )
    return parser.parse_args()


def resolve_target(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "".join(lines[1:index]), "".join(lines[index + 1 :])
    return "", text


def find_frontmatter_end_line(lines: list[str]) -> int | None:
    if not lines or lines[0].strip() != "---":
        return None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return index
    return None


def has_products_frontmatter(frontmatter_text: str) -> bool:
    return re.search(r"(?m)^products\s*:", frontmatter_text) is not None


def line_start_offsets(text: str) -> list[int]:
    starts = [0]
    for match in re.finditer(r"\n", text):
        starts.append(match.end())
    return starts


def offset_to_line(starts: list[int], offset: int) -> int:
    line = 1
    for index, start in enumerate(starts, start=1):
        if start > offset:
            break
        line = index
    return line


def detect_platform(link_text: str, url: str) -> str:
    lowered = f"{link_text} {url}".lower()
    if "amazon" in lowered or "amzn.to" in lowered:
        return "Amazon"
    if "rakuten" in lowered or "r10.to" in lowered:
        return "Rakuten"
    return "unknown"


def extract_markdown_links(body: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    starts = line_start_offsets(body)
    for match in MARKDOWN_LINK_RE.finditer(body):
        link_text = match.group(1).strip()
        url = match.group(2).strip()
        platform = detect_platform(link_text, url)
        if platform not in {"Amazon", "Rakuten"}:
            continue
        links.append(
            {
                "line": str(offset_to_line(starts, match.start())),
                "link_text": link_text,
                "url": url,
                "markdown": match.group(0),
                "platform": platform,
            },
        )
    return links


def yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_products_yaml(slug: str, product_name: str, amazon_url: str, rakuten_url: str) -> str:
    product_id = f"{slug}-product-001"
    lines = [
        "products:",
        f"  - id: {yaml_quote(product_id)}",
        f"    title: {yaml_quote(product_name)}",
        f"    productGroup: {yaml_quote(product_id)}",
        f"    amazon_url: {yaml_quote(amazon_url)}",
        f"    rakuten_url: {yaml_quote(rakuten_url)}",
        '    yahoo_url: ""',
        "    notes:",
        '      - "楽天+Amazon links grouped as one product candidate."',
    ]
    return "\n".join(lines)


def backup_path_for(target: Path) -> Path:
    plain_backup = target.with_name(target.name + ".bak")
    if not plain_backup.exists():
        return plain_backup
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return target.with_name(target.name + f".bak.{timestamp}")


def apply_migration(text: str, products_yaml: str, removal_links: list[dict[str, str]]) -> str:
    lines = text.splitlines(keepends=True)
    frontmatter_end = find_frontmatter_end_line(lines)
    if frontmatter_end is None:
        raise ValueError("frontmatter end not found")

    product_lines = [line + "\n" for line in products_yaml.splitlines()]
    if frontmatter_end > 0 and lines[frontmatter_end - 1].strip():
        product_lines.insert(0, "\n")

    removal_markdown = {link["markdown"] for link in removal_links}
    updated = lines[:frontmatter_end] + product_lines + lines[frontmatter_end:]
    result_lines = []
    for line in updated:
        if any(markdown in line for markdown in removal_markdown):
            continue
        result_lines.append(line)
    return "".join(result_lines)


def determine_status(
    *,
    text: str,
    frontmatter_text: str,
    links: list[dict[str, str]],
    product_name: str | None,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if has_products_frontmatter(frontmatter_text):
        reasons.append("products frontmatter already exists.")
    if not product_name or not product_name.strip():
        reasons.append("product name is required.")
    if any(marker in text for marker in MOJIBAKE_MARKERS):
        reasons.append("possible mojibake marker detected.")
    amazon_links = [link for link in links if link["platform"] == "Amazon"]
    rakuten_links = [link for link in links if link["platform"] == "Rakuten"]
    if len(amazon_links) != 1:
        reasons.append(f"Amazon link count is {len(amazon_links)}, expected 1.")
    if len(rakuten_links) != 1:
        reasons.append(f"Rakuten link count is {len(rakuten_links)}, expected 1.")
    if len(links) != 2:
        reasons.append(f"removal candidate line count is {len(links)}, expected 2.")
    if reasons:
        return "manual_review", reasons
    return "yes_pair", [
        "Amazon 1 + Rakuten 1 detected.",
        "Exactly two clear Markdown link lines can be removed.",
        "Explicit product name provided.",
    ]


def render_report(
    *,
    mode: str,
    target: Path,
    status: str,
    changed: bool,
    sha_before: str,
    sha_after: str,
    backup_exists: bool,
    backup_path: Path | None,
    products_yaml: str,
    removal_links: list[dict[str, str]],
    reasons: list[str],
) -> str:
    lines = [
        "# ProductCard Pair Single Migration Report",
        "",
        f"- mode: {mode}",
        f"- target_file: `{target}`",
        f"- status: {status}",
        f"- changed: {str(changed).lower()}",
        f"- sha256_before: `{sha_before}`",
        f"- sha256_after: `{sha_after}`",
        f"- sha256_unchanged: {str(sha_before == sha_after).lower()}",
        f"- bak_created: {str(backup_exists).lower()}",
        f"- backup_path: `{backup_path}`" if backup_path else "- backup_path: none",
        "- reasons:",
    ]
    for reason in reasons:
        lines.append(f"  - {reason}")
    lines.extend(["", "## Products Frontmatter Candidate", "", "```yaml", products_yaml, "```", ""])
    lines.extend(["## Body Link Removal Candidates", ""])
    if removal_links:
        for link in removal_links:
            lines.append(
                f"- line {link['line']}: remove `{link['markdown']}`",
            )
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    target = resolve_target(args.file)
    if not target.exists():
        raise SystemExit(f"Target file does not exist: {target}")

    backup_candidates_before = set(target.parent.glob(target.name + ".bak*"))
    sha_before = sha256(target)
    text = target.read_text(encoding="utf-8")
    frontmatter_text, body = split_frontmatter(text)
    links = extract_markdown_links(body)
    amazon_links = [link for link in links if link["platform"] == "Amazon"]
    rakuten_links = [link for link in links if link["platform"] == "Rakuten"]
    status, reasons = determine_status(
        text=text,
        frontmatter_text=frontmatter_text,
        links=links,
        product_name=args.product_name,
    )

    slug = target.stem
    products_yaml = "(none)"
    if args.product_name and len(amazon_links) == 1 and len(rakuten_links) == 1:
        products_yaml = build_products_yaml(
            slug,
            args.product_name.strip(),
            amazon_links[0]["url"],
            rakuten_links[0]["url"],
        )

    mode = "apply" if args.apply else "dry-run"
    backup_path: Path | None = None
    if args.apply:
        if status != "yes_pair":
            reasons.append("apply blocked: status is not yes_pair.")
            mode = "apply-blocked"
        else:
            backup_path = backup_path_for(target)
            shutil.copy2(target, backup_path)
            migrated_text = apply_migration(text, products_yaml, links)
            target.write_text(migrated_text, encoding="utf-8", newline="")

    sha_after = sha256(target)
    backup_candidates_after = set(target.parent.glob(target.name + ".bak*"))
    bak_created = bool(backup_candidates_after - backup_candidates_before)
    changed = sha_before != sha_after

    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text(
        render_report(
            mode=mode,
            target=target,
            status=status,
            changed=changed,
            sha_before=sha_before,
            sha_after=sha_after,
            backup_exists=bak_created,
            backup_path=backup_path,
            products_yaml=products_yaml,
            removal_links=links,
            reasons=reasons,
        ),
        encoding="utf-8",
    )

    print(f"mode={mode}")
    print(f"target={target}")
    print(f"status={status}")
    print(f"links={len(links)}")
    print(f"changed={str(changed).lower()}")
    print(f"sha256_unchanged={str(sha_before == sha_after).lower()}")
    print(f"bak_created={str(bak_created).lower()}")
    print(f"backup_path={backup_path if backup_path else 'none'}")
    print(f"report={OUTPUT_REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
