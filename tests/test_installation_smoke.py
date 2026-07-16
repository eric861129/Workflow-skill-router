import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]


class InstallationSmokeTests(unittest.TestCase):
    def test_skill_and_plugin_archives_install_without_repo_paths(self):
        for name, required in (
            ("workflow-skill-router-skill-v2.0.0-alpha.1.zip", "workflow-skill-router/SKILL.md"),
            ("workflow-skill-router-plugin-v2.0.0-alpha.1.zip", "workflow-skill-router/.codex-plugin/plugin.json"),
        ):
            with ZipFile(ROOT / "downloads" / name) as archive:
                self.assertIn(required, archive.namelist())
                self.assertTrue(all(not Path(item).is_absolute() and ".." not in Path(item).parts for item in archive.namelist()))

    def test_missing_mcp_fallback_never_lowers_r2_r3(self):
        with ZipFile(ROOT / "downloads/workflow-skill-router-skill-v2.0.0-alpha.1.zip") as archive:
            skill = archive.read("workflow-skill-router/SKILL.md").decode("utf-8")
        self.assertIn("skill-only-fallback", skill)
        self.assertIn("R2/R3", skill)
        self.assertIn("host sandbox", skill)
        self.assertNotIn("durable resume 可用", skill)


if __name__ == "__main__": unittest.main()
