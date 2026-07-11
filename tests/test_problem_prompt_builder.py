import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "problem_prompt_builder.py"
SPEC = importlib.util.spec_from_file_location("problem_prompt_builder", MODULE_PATH)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class ProblemPromptBuilderTests(unittest.TestCase):
    def build(self, keyword: str) -> tuple[str, str]:
        candidate = {
            "problem_keyword": keyword,
            "article_type": "problem_solution",
            "search_intent": keyword,
            "recommended_product_hint": "",
        }
        title, _path, prompt = builder.build_prompt(candidate, {}, {}, "")
        return title, prompt

    def assert_no_felica_contamination(self, text: str) -> None:
        for term in ("FeliCa", "おサイフケータイ", "Suica", "motorola edge 60"):
            self.assertNotIn(term, text)

    def test_felica_uses_felica_context(self) -> None:
        title, prompt = self.build("FeliCa対応 Androidスマホ 選び方")
        self.assertEqual(title, "FeliCa対応Androidスマホの選び方と購入前チェック")
        self.assertIn("おサイフケータイ", prompt)
        self.assertIn("Suica", prompt)
        self.assertIn("article_type: problem_solution", prompt)

    def test_external_ssd_uses_troubleshooting_context(self) -> None:
        title, prompt = self.build("外付けSSD 接続が切れる 対策")
        self.assertEqual(title, "外付けSSDの接続が切れる原因と対策")
        for term in ("ケーブル", "USBポート", "電力不足", "スリープ設定", "ファイルシステム"):
            self.assertIn(term, prompt)
        self.assertIn("記事本文Markdownのみ", prompt)
        self.assertNotIn("メタディスクリプション案", prompt)
        self.assert_no_felica_contamination(prompt)

    def test_usb_hub_uses_selection_context(self) -> None:
        title, prompt = self.build("USBハブ 選び方")
        self.assertEqual(title, "USBハブの選び方と確認ポイント")
        self.assertIn("給電方式", prompt)
        self.assertIn("転送速度", prompt)
        self.assertIn("article_type: problem_solution", prompt)
        self.assert_no_felica_contamination(prompt)

    def test_unregistered_keyword_can_be_synthetic_for_dry_run(self) -> None:
        with patch.object(builder, "read_csv", return_value=([], [])):
            candidate = builder.find_candidate("USBハブ 選び方", allow_synthetic=True)
        self.assertEqual(candidate["_candidate_source"], "synthetic")
        self.assertEqual(candidate["article_type"], "problem_solution")

    def test_unregistered_keyword_is_rejected_for_apply(self) -> None:
        with patch.object(builder, "read_csv", return_value=([], [])):
            with self.assertRaises(SystemExit):
                builder.find_candidate("USBハブ 選び方")

    def test_unverified_product_hint_is_not_presented_as_a_product(self) -> None:
        supplement = builder.product_supplement("外付けSSD 接続が切れる 対策", {})
        self.assertIn("特定商品の紹介は必須ではありません", supplement)
        self.assertNotIn("関連商品候補", supplement)

    def test_felica_prompt_filename_remains_stable(self) -> None:
        self.assertEqual(
            builder.prompt_filename("FeliCa対応 Androidスマホ 選び方"),
            "felica-android-smartphone-selection_prompt.md",
        )


if __name__ == "__main__":
    unittest.main()
