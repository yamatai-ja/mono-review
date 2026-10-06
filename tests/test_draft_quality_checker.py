from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.draft_quality_checker import check_quality  # noqa: E402


BASE = """## 結論

選び方を説明します。

## 確認事項

確認事項です。

## FAQ

よくある質問です。

## まとめ

まとめです。
"""


class DraftQualityCheckerTests(unittest.TestCase):
    def test_disclosure_before_affiliate_link_passes_placement_check(self) -> None:
        text = (
            "この記事には広告・アフィリエイトリンクを含みます。\n\n"
            + BASE
            + "\n[楽天市場で確認](https://hb.afl.rakuten.co.jp/example)\n"
        )
        _, _, failed, _, details = check_quality(text, "選び方")
        self.assertNotIn("late_pr_ad_disclosure", failed)
        self.assertIn("PR/ad disclosure placement ok", details)

    def test_disclosure_after_affiliate_link_fails(self) -> None:
        text = (
            BASE
            + "\n[楽天市場で確認](https://hb.afl.rakuten.co.jp/example)\n"
            + "\nこの記事には広告・アフィリエイトリンクを含みます。\n"
        )
        _, decision, failed, _, _ = check_quality(text, "選び方")
        self.assertEqual(decision, "fail")
        self.assertIn("late_pr_ad_disclosure", failed)


if __name__ == "__main__":
    unittest.main()
