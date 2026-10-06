from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.article_quality_checker import check_article, load_simple_yaml  # noqa: E402


PROFILE = load_simple_yaml(ROOT / "src" / "article_profiles" / "problem_solution.yaml")
HOWTO_PROFILE = load_simple_yaml(ROOT / "src" / "article_profiles" / "howto.yaml")


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


    def test_howto_profile_requires_prerequisites_steps_checkpoints_and_troubleshooting(self) -> None:
        markdown = """---
description: "説明"
---
## 始める前の前提条件

対応環境を確認します。[関連記事](/blog/example/)

## 手順

1. 設定を開きます。

## 確認ポイント

完了状態を確認します。

## うまくいかないとき

公式ヘルプで確認します。

## FAQ

よくある質問です。

## まとめ

まとめです。
"""
        score, decision, failed, warnings, details = check_article(markdown, HOWTO_PROFILE)

        self.assertEqual(score, 100)
        self.assertEqual(decision, "ready_for_astro_candidate")
        self.assertEqual(failed, [])
        self.assertEqual(warnings, [])
        self.assertIn("required section ok: prerequisites", details)
        self.assertIn("required section ok: troubleshooting", details)

    def test_howto_profile_fails_when_procedure_structure_is_missing(self) -> None:
        markdown = """---
description: "説明"
---
## 概要

説明です。[関連記事](/blog/example/)

## FAQ

FAQです。

## まとめ

まとめです。
"""
        _, decision, failed, _, _ = check_article(markdown, HOWTO_PROFILE)

        self.assertEqual(decision, "needs_edit")
        self.assertIn("missing_required_section:prerequisites", failed)
        self.assertIn("missing_required_section:steps", failed)
        self.assertIn("missing_required_section:expected_result", failed)
        self.assertIn("missing_required_section:troubleshooting", failed)


if __name__ == "__main__":
    unittest.main()
