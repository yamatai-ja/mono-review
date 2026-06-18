from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.article_quality_checker import load_simple_yaml  # noqa: E402
from src.publication_risk_checker import (  # noqa: E402
    article_type_from_frontmatter,
    classify_publication_risk,
)


PROFILE = load_simple_yaml(ROOT / "src" / "article_profiles" / "problem_solution.yaml")


class PublicationRiskCheckerTests(unittest.TestCase):
    def test_felica_article_is_high(self) -> None:
        path = ROOT / "src" / "content" / "posts" / "felica-android-smartphone-selection.md"

        result = classify_publication_risk(path.read_text(encoding="utf-8"), PROFILE)

        self.assertEqual(result.level, "high")
        self.assertIn("FeliCa", result.high_matches)
        self.assertIn("公式情報確認メモまたはresearch_notes必須", result.required_tasks)

    def test_lightweight_selection_article_is_low(self) -> None:
        markdown = """---
article_type: problem_solution
title: ケーブルを整理する方法
---

## 選び方
長さと置き場所を先に決めます。

## 使い方
無理に曲げず、余った部分をまとめます。
"""

        result = classify_publication_risk(markdown, PROFILE)

        self.assertEqual(result.level, "low")
        self.assertEqual(result.high_matches, ())
        self.assertEqual(result.medium_matches, ())
        self.assertNotIn("商品公式ページ確認", result.required_tasks)

    def test_product_comparison_article_is_medium(self) -> None:
        markdown = """---
article_type: problem_solution
title: デスクライトの選び方
---

複数の商品を比較し、候補を絞るポイントを説明します。
"""

        result = classify_publication_risk(markdown, PROFILE)

        self.assertEqual(result.level, "medium")
        self.assertIn("比較", result.medium_matches)
        self.assertIn("商品公式ページ確認", result.required_tasks)
        self.assertNotIn("公式情報確認メモまたはresearch_notes必須", result.required_tasks)

    def test_high_terms_take_priority_over_medium_terms(self) -> None:
        result = classify_publication_risk("商品の価格を比較します。", PROFILE)

        self.assertEqual(result.level, "high")
        self.assertIn("価格", result.high_matches)
        self.assertIn("比較", result.medium_matches)

    def test_article_type_is_read_from_frontmatter(self) -> None:
        markdown = """---
article_type: "problem_solution"
draft: true
---
本文
"""

        self.assertEqual(article_type_from_frontmatter(markdown), "problem_solution")


if __name__ == "__main__":
    unittest.main()
