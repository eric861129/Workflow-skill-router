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

if __name__ == "__main__":
    unittest.main()
