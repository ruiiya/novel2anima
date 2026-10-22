"""PR-04 package boundaries and legacy CLI compatibility."""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PACKAGE_MODULES = (
    "novel2anima.catalog.build_service",
    "novel2anima.catalog.importers.analyze_posts",
    "novel2anima.catalog.importers.character_outfits",
    "novel2anima.catalog.importers.colour_sets",
    "novel2anima.catalog.importers.danbooru_dump",
    "novel2anima.catalog.importers.tags",
    "novel2anima.catalog.importers.unknown_tags",
    "novel2anima.catalog.importers.wiki_groups",
    "novel2anima.catalog.importers.wiki_links",
    "novel2anima.catalog.importers.wiki_pages",
    "novel2anima.catalog.maintenance.cleanup_db",
    "novel2anima.catalog.maintenance.prune_tags",
    "novel2anima.catalog.retrieval.suggest_tags",
    "novel2anima.catalog.tag_roles",
    "novel2anima.continuity.inference",
    "novel2anima.continuity.rules",
    "novel2anima.llm.adapters.review_adapter",
    "novel2anima.pipeline.plan_seeder",
    "novel2anima.quality.act_quality",
    "novel2anima.quality.prompt_rules",
    "novel2anima.quality.shot_rules",
    "novel2anima.quality.story_rules",
    "novel2anima.storage.story_repository",
    "novel2anima.story.action_planner",
    "novel2anima.story.beat_planner",
    "novel2anima.story.logic",
    "novel2anima.wardrobe.rules",
)

class PackageLayout(unittest.TestCase):
    def test_package_imports(self):
        import importlib

        for name in PACKAGE_MODULES:
            with self.subTest(name=name):
                importlib.import_module(name)

    def test_no_legacy_etl_tree(self):
        self.assertFalse((ROOT / "etl").exists())

    def test_no_src_path_hacks(self):
        offenders = []
        for path in (ROOT / "src").rglob("*.py"):
            if "sys.path.insert" in path.read_text(encoding="utf-8"):
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_package_cli_help(self):
        for module in (
            "novel2anima.continuity.inference",
            "novel2anima.pipeline.plan_seeder",
            "novel2anima.catalog.build_service",
        ):
            with self.subTest(module=module):
                result = subprocess.run(
                    [sys.executable, "-m", module, "--help"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_pyproject_exists(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('where = ["src"]', text)
        self.assertIn('name = "novel2anima"', text)

if __name__ == "__main__":
    unittest.main()
