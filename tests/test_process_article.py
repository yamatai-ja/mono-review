from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.process_article import (  # noqa: E402
    check_only_lines,
    evaluate_publication_risk,
    main,
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

    def test_check_only_felica_is_read_only_and_reports_all_fields(self) -> None:
        article_path = ROOT / "src/content/posts/felica-android-smartphone-selection.md"
        before = article_path.read_bytes()

        lines = check_only_lines(str(article_path))

        self.assertEqual(article_path.read_bytes(), before)
        self.assertIn("quality_score=100", lines)
        self.assertIn("quality_decision=ready_for_astro_candidate", lines)
        self.assertIn("publication_risk=high", lines)
        self.assertIn("research_notes_required=yes", lines)
        self.assertIn("markdown_audit_decision=draft_ok", lines)
        self.assertIn("draft=true", lines)
        self.assertTrue(any(line.startswith("detected_terms=") for line in lines))
        self.assertTrue(any(line.startswith("required_human_checks=") for line in lines))

    def test_check_only_main_does_not_run_subprocesses(self) -> None:
        argv = [
            "process_article.py",
            "--check-only",
            "src/content/posts/felica-android-smartphone-selection.md",
        ]
        output = StringIO()

        with (
            patch.object(sys, "argv", argv),
            patch("src.process_article.run_command") as run_command,
            redirect_stdout(output),
        ):
            exit_code = main()

        self.assertEqual(exit_code, 0)
        run_command.assert_not_called()
        self.assertIn("quality_score=100", output.getvalue())
        self.assertIn("publication_risk=high", output.getvalue())

    def test_check_only_supports_body_markdown_with_article_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            draft_path = Path(temp_dir) / "body.md"
            draft_path.write_text("## 選び方\n\n収納方法を説明します。\n", encoding="utf-8")

            lines = check_only_lines(str(draft_path), "problem_solution")

        self.assertIn("article_type=problem_solution", lines)
        self.assertIn("publication_risk=low", lines)
        self.assertIn("draft=unknown", lines)


if __name__ == "__main__":
    unittest.main()
