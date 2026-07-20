import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PLUGIN = ROOT / "plugins" / "workflow-skill-router"
CANONICAL = ROOT / "starter" / "v2" / "workflow-skill-router"
VERSION = json.loads(
    (ROOT / "release" / "version.json").read_text(encoding="utf-8")
)["v2_version"]


class PluginLayoutTests(unittest.TestCase):
    def test_manifest_and_companions_are_consistent(self) -> None:
        manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual("workflow-skill-router", manifest["name"])
        self.assertEqual(VERSION, manifest["version"])
        self.assertEqual("./skills/", manifest["skills"])
        self.assertEqual("./.mcp.json", manifest["mcpServers"])
        self.assertNotIn("apps", manifest)
        self.assertNotIn("hooks", manifest)

    def test_generated_skill_is_byte_identical(self) -> None:
        source = {path.relative_to(CANONICAL): path.read_bytes() for path in CANONICAL.rglob("*") if path.is_file()}
        target_root = PLUGIN / "skills" / "workflow-skill-router"
        target = {path.relative_to(target_root): path.read_bytes() for path in target_root.rglob("*") if path.is_file()}
        self.assertEqual(source, target)

    def test_mcp_config_uses_bundled_relative_entrypoint(self) -> None:
        config = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))
        server = config["mcpServers"]["workflow-skill-router"]
        self.assertEqual("node", server["command"])
        self.assertEqual(["./mcp/server.bundle.mjs"], server["args"])
        self.assertEqual(".", server["cwd"])


if __name__ == "__main__":
    unittest.main()
