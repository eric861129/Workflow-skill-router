import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build-release-artifacts.py"
SMOKE = ROOT / "plugins" / "workflow-skill-router" / "scripts" / "smoke-plugin.mjs"
REQUIRED_PLUGIN_HEADINGS = (
    "Requirements",
    "Install in Codex",
    "Verify the MCP server",
    "Skill-only fallback",
    "Local state and privacy",
    "Uninstall",
    "Troubleshooting",
)


class InstallationSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.output = cls.root / "release"
        result = subprocess.run(
            [
                sys.executable,
                str(BUILDER),
                "--output-dir",
                str(cls.output),
                "--provenance-mode",
                "test",
                "--check-determinism",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.version = json.loads(
            (ROOT / "release" / "version.json").read_text(encoding="utf-8")
        )["v2_version"]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_skill_and_plugin_archives_install_without_repo_paths(self) -> None:
        for name, required in (
            (
                f"workflow-skill-router-skill-v{self.version}.zip",
                "workflow-skill-router/SKILL.md",
            ),
            (
                f"workflow-skill-router-plugin-v{self.version}.zip",
                "workflow-skill-router/.codex-plugin/plugin.json",
            ),
        ):
            with ZipFile(self.output / name) as archive:
                self.assertIn(required, archive.namelist())
                self.assertTrue(
                    all(
                        not Path(item).is_absolute() and ".." not in Path(item).parts
                        for item in archive.namelist()
                    )
                )

    def test_extracted_plugin_is_self_documenting_and_smoke_tested(self) -> None:
        archive_path = (
            self.output / f"workflow-skill-router-plugin-v{self.version}.zip"
        )
        extract_root = self.root / "extracted"
        with ZipFile(archive_path) as archive:
            archive.extractall(extract_root)
            names = set(archive.namelist())

        plugin_root = extract_root / "workflow-skill-router"
        for relative in ("README.md", "LICENSE", "THIRD_PARTY_NOTICES.md"):
            self.assertTrue((plugin_root / relative).is_file(), relative)

        readme = (plugin_root / "README.md").read_text(encoding="utf-8")
        for heading in REQUIRED_PLUGIN_HEADINGS:
            self.assertIn(f"## {heading}", readme)

        self.assertTrue(all("/mcp/src/" not in name for name in names))
        self.assertTrue(all("/mcp/test/" not in name for name in names))
        self.assertTrue(all("/scripts/" not in name for name in names))
        self.assertNotIn("workflow-skill-router/package-lock.json", names)

        smoke = subprocess.run(
            ["node", str(SMOKE), str(plugin_root)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(0, smoke.returncode, smoke.stdout + smoke.stderr)
        result = json.loads(smoke.stdout.strip().splitlines()[-1])
        self.assertEqual(10, result["tool_count"])
        self.assertEqual("outside-plugin", result["state_boundary"])

    def test_missing_mcp_fallback_never_lowers_r2_r3(self) -> None:
        archive_path = self.output / f"workflow-skill-router-skill-v{self.version}.zip"
        with ZipFile(archive_path) as archive:
            skill = archive.read("workflow-skill-router/SKILL.md").decode("utf-8")
        self.assertIn("skill-only-fallback", skill)
        self.assertIn("R2/R3", skill)
        self.assertIn("host sandbox", skill)
        self.assertNotIn("durable resume 可用", skill)


if __name__ == "__main__":
    unittest.main()
