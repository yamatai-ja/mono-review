from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.process_article import (  # noqa: E402
    evaluate_publication_risk,
    publication_risk_lines,
)


class ProcessArticlePublicationRiskTests(unittest.TestCase):
    def test_felica_risk_is_included_in_process_output(self) -> None:
        result = evaluate_publication_risk(
            "problem_solution",
            "src/content/posts/felica-android-smartphone-selection.md",
        )

        lines = publication_risk_lines(result)

        self.assertIn("publication_risk=high", lines)
        self.assertTrue(
            any(line.startswith("detected_terms=") and "FeliCa" in line for line in lines)
        )
        self.assertIn("research_notes_required=yes", lines)
        self.assertTrue(
            any(
                line.startswith("required_human_checks=")
                and "公式情報確認メモまたはresearch_notes必須" in line
                for line in lines
            )
        )

    def test_low_risk_output_does_not_require_research_notes(self) -> None:
        from src.article_quality_checker import load_simple_yaml
        from src.publication_risk_checker import classify_publication_risk

        profile = load_simple_yaml(ROOT / "src/article_profiles/problem_solution.yaml")
        result = classify_publication_risk("ケーブルを整理する方法を説明します。", profile)

        self.assertIn("publication_risk=low", publication_risk_lines(result))
        self.assertIn("research_notes_required=no", publication_risk_lines(result))

    def test_title_is_included_in_risk_classification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            draft_path = Path(temp_dir) / "draft.md"
            draft_path.write_text("収納方法を説明します。", encoding="utf-8")

            result = evaluate_publication_risk(
                "problem_solution",
                str(draft_path),
                "料金を確認する方法",
            )

        self.assertEqual(result.level, "high")
        self.assertIn("料金", result.detected_terms)


if __name__ == "__main__":
    unittest.main()
