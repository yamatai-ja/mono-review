# Blog SEO Operations v1

Status: additive, draft-safe

This document adds three no-paid-service operating modules to the existing Astro blog workflow. They do not auto-publish or auto-edit reader-facing content.

## 1. Internal link audit and recommendation

Existing structural audit:

```bash
npm run audit:links
```

Recommendation report:

```bash
npm run audit:links:recommend
```

Outputs:

- `output/internal_link_recommendations.csv`
- `output/internal_link_recommendations.md`

The recommender:
- targets orphan pages by default;
- proposes up to three source pages per target;
- suggests target-title anchor text and a likely source heading;
- omits weak matches rather than forcing links;
- never edits Markdown automatically.

For a newly published page:

```bash
python scripts/recommend_internal_links.py --target-slug <slug>
```

Human review remains required because topical similarity does not prove that a link belongs in a specific paragraph.

## 2. How-To article quality profile

Run the existing checker with the new profile:

```bash
python src/article_quality_checker.py \
  --article-type howto \
  --draft-file <path-to-markdown> \
  --slug <slug>
```

The How-To profile requires:
- prerequisites / supported environment;
- a numbered procedure section;
- expected-result or checkpoint section;
- troubleshooting section;
- FAQ, summary, meta description, and an internal link.

Exact product UI wording still needs current official Evidence. The checker verifies structure, not factual truth.

## 3. Technical SEO audit with SEOmator

The repository does **not** add SEOmator as a dependency because `AGENTS.md` requires explicit approval before adding dependencies.

After the user approves and installs the optional open-source CLI:

```bash
npm install -g @seomator/seo-audit
npm run audit:seo
```

The wrapper writes an LLM-oriented audit report to:

```text
output/seo_audit.llm.txt
```

Default command audits `https://monoslog.com`, crawls up to 50 pages, and skips Core Web Vitals for a faster baseline. To include CWV/JS rendering:

```bash
python scripts/run_seo_audit.py \
  --site https://monoslog.com \
  --crawl \
  --max-pages 20 \
  --with-cwv
```

If SEOmator is not installed, the wrapper exits with a blocked status and installation instructions. It never silently installs packages.

## Publication safety

These modules remain advisory or validation-only:

```text
article draft
  -> article quality checks
  -> internal link audit/recommendations
  -> Astro check/build
  -> optional technical SEO audit
  -> human review
  -> publication
```

No module in this document grants publication authority.
