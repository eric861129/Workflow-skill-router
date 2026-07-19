import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
PLUGIN_MANIFEST = (
    ROOT / "plugins" / "workflow-skill-router" / ".codex-plugin" / "plugin.json"
)


class MarketplaceManifestTests(unittest.TestCase):
    def test_repo_marketplace_exposes_the_v2_plugin_without_a_pinned_version(self) -> None:
        marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
        self.assertEqual("workflow-skill-router", marketplace["name"])
        self.assertEqual(
            "Workflow Skill Router", marketplace["interface"]["displayName"]
        )
        self.assertEqual(1, len(marketplace["plugins"]))

        entry = marketplace["plugins"][0]
        self.assertEqual("workflow-skill-router", entry["name"])
        self.assertEqual(
            {"source": "local", "path": "./plugins/workflow-skill-router"},
            entry["source"],
        )
        self.assertEqual("AVAILABLE", entry["policy"]["installation"])
        self.assertEqual("ON_INSTALL", entry["policy"]["authentication"])
        self.assertNotIn("products", entry["policy"])
        self.assertNotIn("version", entry)
        self.assertEqual("Productivity", entry["category"])

    def test_plugin_manifest_matches_its_folder_and_companion_files(self) -> None:
        manifest = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(PLUGIN_MANIFEST.parents[1].name, manifest["name"])
        self.assertEqual("./skills/", manifest["skills"])
        self.assertEqual("./.mcp.json", manifest["mcpServers"])
        self.assertTrue(manifest["homepage"].startswith("https://"))
        self.assertTrue(manifest["repository"].startswith("https://"))


if __name__ == "__main__":
    unittest.main()
