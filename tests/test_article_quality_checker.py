from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.article_quality_checker import check_article, load_simple_yaml  # noqa: E402


PROFILE = load_simple_yaml(ROOT / "src" / "article_profiles" / "problem_solution.yaml")


VALID_BODY = """本記事には広告リンクを含みます。

## 結論

選び方を説明します。[関連記事](/blog/example/)

## 確認事項

確認事項です。

## FAQ

よくある質問です。

## まとめ

まとめです。
"""


class ArticleQualityCheckerTests(unittest.TestCase):
    def test_astro_frontmatter_is_excluded_from_body_checks(self) -> None:
        markdown = f'''---
title: "Example"
description: "frontmatter内の説明"
draft: true
pubDate: "2026-06-18"
categories: ["スマホ"]
tags: ["draft"]
source_url: "https://example.com/source"
---
{VALID_BODY}'''

        score, decision, failed, warnings, details = check_article(markdown, PROFILE)

        self.assertEqual(score, 100)
        self.assertEqual(decision, "ready_for_astro_candidate")
        self.assertEqual(failed, [])
        self.assertEqual(warnings, [])
        self.assertIn("meta description ok (frontmatter)", details)

    def test_body_checks_still_detect_prohibited_content(self) -> None:
        markdown = f'''---
description: "説明"
draft: true
---
# 本文H1

{VALID_BODY}

draft 今すぐ購入 https://example.com/item
'''

        _, decision, failed, warnings, _ = check_article(markdown, PROFILE)

        self.assertEqual(decision, "needs_edit")
        self.assertIn("h1_count=1", failed)
        self.assertIn("internal_terms:draft", failed)
        self.assertIn("strong_cta_terms:今すぐ購入", failed)
        self.assertTrue(any(item.startswith("bare_urls:") for item in warnings))

    def test_legacy_body_meta_description_remains_supported(self) -> None:
        markdown = f"""## メタディスクリプション案

説明文です。

{VALID_BODY}"""

        score, decision, failed, warnings, details = check_article(markdown, PROFILE)

        self.assertEqual(score, 100)
        self.assertEqual(decision, "ready_for_astro_candidate")
        self.assertEqual(failed, [])
        self.assertEqual(warnings, [])
        self.assertIn("meta description ok (body)", details)


if __name__ == "__main__":
    unittest.main()
