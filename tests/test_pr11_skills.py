"""PR-11 skill alignment: preserved identifiers, V4.1 boundaries, no stale authority."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from novel2anima.llm.contracts import STAGES  # noqa: E402

SKILLS = ROOT / "skills"
NAMES = (
    "novel2anima-catalog",
    "novel2anima-shot-pipeline",
    "novel2anima-natural-language-prompt",
)


class SkillAlignment(unittest.TestCase):
    def test_three_skill_identifiers_preserved(self):
        for name in NAMES:
            skill = SKILLS / name / "SKILL.md"
            self.assertTrue(skill.is_file(), name)
            text = skill.read_text(encoding="utf-8")
            self.assertIn(f"name: {name}", text)
            self.assertIn("V4.1", text)

    def test_runtime_contract_is_present_and_real(self):
        contract = ROOT / "docs/contracts/SKILL_RUNTIME_CONTRACTS.md"
        architecture = ROOT / "docs/architecture/PIPELINE_EXECUTION_CONTROL.md"
        self.assertTrue(contract.is_file())
        self.assertTrue(architecture.is_file())
        text = contract.read_text(encoding="utf-8")
        self.assertIn("start_story", architecture.read_text(encoding="utf-8"))
        self.assertIn("BLOCKED_CONFIG", text)
        self.assertIn("stage 08", text)
        self.assertIn("013_execution_control", architecture.read_text(encoding="utf-8"))

    def test_architecture_references_are_redirects(self):
        for name in ("novel2anima-catalog", "novel2anima-shot-pipeline"):
            path = SKILLS / name / "references/v4-architecture.md"
            self.assertLess(len(path.read_text(encoding="utf-8")), 1200)
            self.assertIn("PIPELINE_EXECUTION_CONTROL.md", path.read_text(encoding="utf-8"))

    def test_prompt_scaffolds_remain_zero_byte(self):
        files = sorted((ROOT / "llm/prompts").rglob("*.txt"))
        self.assertEqual(len(files), len(STAGES) * 3)
        self.assertEqual([path for path in files if path.stat().st_size], [])

    def test_no_stale_runtime_authority_claims(self):
        forbidden = (
            "shot_spec_json",
            "check_prompts.py",
            "Images belong on disk",
            "Image bytes stay on disk - the DB stores paths",
        )
        offenders = []
        for path in SKILLS.rglob("*"):
            if path.is_file() and path.suffix in {".md", ".yaml"}:
                text = path.read_text(encoding="utf-8")
                for phrase in forbidden:
                    if phrase in text:
                        offenders.append(f"{path}: {phrase}")
        self.assertEqual(offenders, [])

    def test_agents_metadata_keeps_display_names(self):
        for name, display in (
            ("novel2anima-catalog", "N2A Catalog"),
            ("novel2anima-shot-pipeline", "N2A Shot Pipeline"),
        ):
            text = (SKILLS / name / "agents/openai.yaml").read_text(encoding="utf-8")
            self.assertIn(display, text)
            self.assertIn("V4.1", text)


if __name__ == "__main__":
    unittest.main()
