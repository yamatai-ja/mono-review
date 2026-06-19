# Article Rules

This repository separates article body creation from content operations.

## Common Rules

- Do not generate or rewrite article bodies unless the user provides the body.
- Do not publish automatically.
- Do not change `draft: true` to `draft: false` in article processing tools.
- Do not add unconfirmed specs, prices, stock status, warranty details, or sales claims.
- Do not add strong purchase CTAs.
- Do not expose internal management terms in article bodies.

## Article Types

### product/review articles

Use the existing workflow and `draft_quality_checker.py`.

### problem_solution articles

Use `src/article_quality_checker.py` with `src/article_profiles/problem_solution.yaml`.

Problem-solution articles should:

- Use frontmatter title, not an H1 in the body.
- Focus on the reader's problem and selection criteria.
- Treat products as optional candidates, not the main topic.
- Include FAQ.
- Avoid internal workflow terms.
- Avoid strong CTA and review-like experience claims.

## Publication Risk Rules

`quality_score` and `publication_risk` have different purposes. A high quality score does not reduce the required publication review.

- `low`: Run quality and Markdown checks, check/build, and visual review.
- `medium`: Complete all low-risk checks and verify the product official page.
- `high`: Complete all medium-risk checks and require an official-information memo or `research_notes`.

For `high` articles:

- Never auto-publish based only on `quality_score`.
- Do not assert unverified pricing, stock, warranty, supported bands, or campaigns.
- Keep `draft: true` until official information has been checked.
- Do not change to `draft: false`, push, or deploy without explicit instruction.

The FeliCa Android selection article is `high` because it involves FeliCa, Osaifu-Keitai, Suica, communications, payments, warranty, and contracts. It requires an official-information memo or `research_notes` before publication review can finish.

## Standard Decision

- `ready_for_astro_candidate`: article body is suitable for Astro draft conversion.
- `needs_edit`: article body should be edited before Astro draft conversion.
