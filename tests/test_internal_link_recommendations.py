from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.recommend_internal_links import build_recommendations, load_posts  # noqa: E402


def _write(root: Path, name: str, title: str, category: str, body: str) -> None:
    (root / name).write_text(
        f"""---
title: "{title}"
categories: ["{category}"]
tags: ["{category}"]
---
{body}
""",
        encoding="utf-8",
    )


class InternalLinkRecommendationTests(unittest.TestCase):
    def test_orphan_target_prefers_topically_related_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root,
                "small-mouse.md",
                "手が小さい人向けゲーミングマウスの選び方",
                "ゲーミングマウス",
                "## 手のサイズ\n小さい手では形状と幅を確認します。",
            )
            _write(
                root,
                "mouse-grip.md",
                "ゲーミングマウスの持ち方とサイズ",
                "ゲーミングマウス",
                "## 手のサイズと持ち方\nマウス幅と持ち方を比較します。",
            )
            _write(
                root,
                "coffee.md",
                "コーヒーメーカーの選び方",
                "家電",
                "## 抽出方式\nドリップ方式を比較します。",
            )
            report = build_recommendations(
                load_posts(root),
                target_slug="small-mouse",
                top_n=1,
                min_similarity=0.0,
            )
            self.assertEqual(report["recommendation_count"], 1)
            row = report["recommendations"][0]
            self.assertEqual(row["source_slug"], "mouse-grip")
            self.assertEqual(row["target_slug"], "small-mouse")
            self.assertIn("手のサイズ", row["placement_heading"])

    def test_existing_link_is_not_recommended_again(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root,
                "target.md",
                "SSDクローンの手順",
                "SSD",
                "## 手順\nクローン手順を説明します。",
            )
            _write(
                root,
                "source.md",
                "SSD交換ガイド",
                "SSD",
                "## SSD交換\n[クローン手順](/blog/target/)を確認します。",
            )
            report = build_recommendations(
                load_posts(root),
                target_slug="target",
                top_n=3,
                min_similarity=0.0,
            )
            self.assertEqual(report["recommendation_count"], 0)


if __name__ == "__main__":
    unittest.main()
