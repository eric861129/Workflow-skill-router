import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "starter" / "v2" / "workflow-skill-router"
TARGET = ROOT / "plugins" / "workflow-skill-router" / "skills" / "workflow-skill-router"
SKILL_FILES = (
    Path("SKILL.md"),
    Path("references/evaluation-boundary.md"),
    Path("references/goal-protocol.md"),
    Path("references/routing-protocol.md"),
)


class SkillSourceSyncTests(unittest.TestCase):
    def test_plugin_skill_is_byte_identical_to_the_canonical_starter(self) -> None:
        actual = tuple(
            sorted(path.relative_to(TARGET) for path in TARGET.rglob("*") if path.is_file())
        )
        self.assertEqual(tuple(sorted(SKILL_FILES)), actual)
        for relative in SKILL_FILES:
            self.assertEqual(
                (SOURCE / relative).read_bytes(),
                (TARGET / relative).read_bytes(),
                relative.as_posix(),
            )

    def test_canonical_skill_states_the_consent_and_reporting_contract(self) -> None:
        skill = (SOURCE / "SKILL.md").read_text(encoding="utf-8")
        protocol = (SOURCE / "references/routing-protocol.md").read_text(
            encoding="utf-8"
        )
        combined = skill + "\n" + protocol
        self.assertIn("未指定 SKILL", combined)
        self.assertIn("不為 Router 自己推薦的輔助 SKILL 額外詢問同意", combined)
        self.assertIn("使用者指定 SKILL", combined)
        self.assertIn("新增推薦支援前必須取得 scoped consent", combined)
        self.assertIn("執行前宣告預計使用的 SKILL", combined)
        self.assertIn("完成後列出實際使用的 SKILL", combined)

if __name__ == "__main__":
    unittest.main()
