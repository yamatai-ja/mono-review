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
- Do not auto-publish articles or programmatically change a draft to a live post without a separate human action.
- All generated articles must remain draft/review status. A production promotion is human-initiated after preflight and documented approval.
- Prioritize CSV/SQLite based MVP over complex frameworks.

## Workspace shortcut
When the user says "integrate側", use:
`C:\Users\shiga\OneDrive\ドキュメント\antigravity\astro-management\mono-review-fresh-integrate`

Do not modify:
`C:\Users\shiga\OneDrive\ドキュメント\antigravity\astro-management\mono-review-fresh`
unless explicitly requested.

## Affiliate link placement
- Do not force three affiliate placements. Add a link only where a verified offer helps the reader make a decision; zero, one, or several contextual links may be appropriate.
- Affiliate placements must follow the article's intent and approved offer evidence. Never invent a product, sale, price, stock status, ranking, spec, review score, or campaign.
- Do not paste bare affiliate URLs into article body text.
- Prefer existing ProductCard or CTA/button UI so links can include `rel="sponsored nofollow noopener noreferrer"` and a visible affiliate disclosure.
- The canonical KRS decision/Article Package rules govern KRS-generated drafts; this repository must not introduce a second score or bypass the human publication gate.
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
