# AGENTS.md

## Project
This is a semi-automated SEO blog operation system.
The goal is not mass auto-publishing, but draft generation, SEO checks, affiliate link insertion, Search Console based rewrite suggestions, and human review.

## Important rules
- Do not implement the whole system at once.
- Work on one small module per task.
- Do not scan the entire repository unless explicitly requested.
- Before editing, list the files you need to inspect.
- Keep changes minimal.
- Do not rename existing CSV columns unless requested.
- Do not add new dependencies without confirmation.
- Do not auto-publish articles.
- All generated articles must remain draft/review status.
- Prioritize CSV/SQLite based MVP over complex frameworks.

## Affiliate link placement
- For product review or buying-guide articles, place affiliate links in three natural locations by default:
  1. the top product card,
  2. a purchase-decision section in the body,
  3. near the final summary.
- Do not paste bare affiliate URLs into article body text.
- Prefer existing ProductCard or CTA/button UI so links can include `rel="sponsored nofollow noopener noreferrer"`.
- Do not invent prices, stock status, campaign details, rankings, specs, or review scores.
- Run the relevant validator, `npm run check`, and `npm run build` before creating a PR.

## Current MVP
Use these files as the source of truth:
- data/keywords.csv
- data/products.csv
- data/articles.csv
- data/offers.csv
- data/article_queue.csv

## Coding style
- Python first.
- Prefer small pure functions.
- Keep modules independent.
- Add simple CLI entry points.
- Output reports to output/.
- Use logs for errors.

## Done means
- The target module runs from command line.
- Sample input works.
- Output CSV or markdown report is generated.
- Existing files are not broken.
- Report changed files and test command.
