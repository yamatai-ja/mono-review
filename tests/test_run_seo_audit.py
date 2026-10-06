from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_seo_audit import build_command  # noqa: E402


class SeoAuditWrapperTests(unittest.TestCase):
    def test_build_command_defaults_to_llm_and_no_cwv(self) -> None:
        command = build_command(
            "/usr/local/bin/seomator",
            "https://monoslog.com",
            Path("output/report.txt"),
            crawl=True,
            max_pages=50,
            with_cwv=False,
        )
        self.assertEqual(command[:3], ["/usr/local/bin/seomator", "audit", "https://monoslog.com"])
        self.assertIn("--format", command)
        self.assertIn("llm", command)
        self.assertIn("--crawl", command)
        self.assertIn("--max-pages", command)
        self.assertIn("--no-cwv", command)

    def test_build_command_can_enable_cwv(self) -> None:
        command = build_command(
            "seomator",
            "https://monoslog.com",
            Path("output/report.txt"),
            crawl=False,
            max_pages=10,
            with_cwv=True,
        )
        self.assertNotIn("--no-cwv", command)
        self.assertNotIn("--crawl", command)


if __name__ == "__main__":
    unittest.main()
