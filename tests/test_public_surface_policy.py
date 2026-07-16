import json
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "release" / "public-surface-policy.json"
REMOVAL_PATH = ROOT / "release" / "legacy-v1-removal-manifest.json"
VERSION_PATH = ROOT / "release" / "version.json"


class PublicSurfacePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.removal = json.loads(REMOVAL_PATH.read_text(encoding="utf-8"))
        cls.version = json.loads(VERSION_PATH.read_text(encoding="utf-8"))

    def test_v2_is_the_public_default_without_promoting_latest(self) -> None:
        self.assertEqual("1.0", self.policy["schema_version"])
        self.assertEqual("v2-first", self.policy["default_product"])
        self.assertEqual(
            ["plugin-mcp", "skill-only"],
            self.policy["primary_install_modes"],
        )
        self.assertEqual(
            "codex-git-marketplace",
            self.policy["distribution"]["plugin_primary"],
        )
        self.assertEqual(
            "github-release-assets",
            self.policy["distribution"]["release_assets"],
        )
        self.assertEqual("v1.3.1", self.policy["legacy"]["source_tag"])
        self.assertFalse(self.policy["legacy"]["visible_in_primary_navigation"])

        self.assertEqual("v2-first", self.version["public_surface"])
        self.assertEqual("2.0.0-beta.1", self.version["target_prerelease"])
        self.assertEqual("latest", self.version["stable_channel"])
        self.assertEqual("1.3.1", self.version["v1_pinned_version"])

    def test_removal_manifest_is_exact_and_recoverable(self) -> None:
        self.assertEqual("1.0", self.removal["schema_version"])
        self.assertIn("sample-skills", self.removal["directories"])
        self.assertIn(
            "downloads/workflow-skill-router-template.zip",
            self.removal["files"],
        )
        self.assertEqual(231, self.removal["selection_count"])
        self.assertEqual(231, len(self.removal["files"]))
        self.assertTrue(all("*" not in path for path in self.removal["files"]))
        self.assertEqual(
            sorted(self.removal["files"]),
            [entry["path"] for entry in self.removal["entries"]],
        )
        self.assertTrue(
            all(entry["replacement_or_recovery"] for entry in self.removal["entries"])
        )
        self.assertTrue(
            all(
                entry["historical_source"] in self.removal["recovery_sources"]
                for entry in self.removal["entries"]
            )
        )
        self.assertTrue(all(entry["reason"] for entry in self.removal["entries"]))

        self.assertEqual(
            Counter(
                {
                    "v1.3.1": 208,
                    "generated-from-source": 11,
                    "starting-head:70f3456270b4395e8d473a3f8cc592391c92b335": 11,
                    "github-release:v1.3.1": 1,
                }
            ),
            Counter(entry["historical_source"] for entry in self.removal["entries"]),
        )

        entries = {entry["path"]: entry for entry in self.removal["entries"]}
        self.assertEqual("v1.3.1", entries["README.en.md"]["historical_source"])
        self.assertEqual(
            "generated-from-source",
            entries["downloads/workflow-skill-router-plugin-v2.0.0-alpha.1.zip"][
                "historical_source"
            ],
        )

    def test_marketplace_runtime_outputs_are_retained(self) -> None:
        retained = {
            "plugins/workflow-skill-router/mcp/server.bundle.mjs",
            "plugins/workflow-skill-router/runtime/workflow_skill_router.pyz",
        }
        self.assertTrue(retained.isdisjoint(self.removal["files"]))


if __name__ == "__main__":
    unittest.main()
