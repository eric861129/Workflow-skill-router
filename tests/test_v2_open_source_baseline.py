import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "release" / "v2-open-source-reset-baseline.json"

EXPECTED_INHERITED_PATHS = {
    "README.en.md",
    "README.md",
    "README.zh-TW.md",
    "demo/v2-scenarios/inputs.json",
    "docs/anti-over-routing.md",
    "docs/showcase.md",
    "docs/superpowers/plans/2026-07-16-workflow-skill-router-v2-open-source-reset.md",
    "docs/superpowers/specs/2026-07-15-workflow-skill-router-v2-design.md",
    "docs/v2-architecture.md",
    "docs/v2-architecture.zh-TW.md",
    "downloads/checksums.sha256",
    "downloads/release-manifest-v2.0.0-alpha.1.json",
    "downloads/workflow-skill-router-plugin-v2.0.0-alpha.1.zip",
    "downloads/workflow-skill-router-skill-v2.0.0-alpha.1.zip",
    "packages/router-core/src/workflow_skill_router/bridge.py",
    "packages/router-core/src/workflow_skill_router/cli/__init__.py",
    "packages/router-core/src/workflow_skill_router/demo_export.py",
    "packages/router-core/src/workflow_skill_router/local_control.py",
    "packages/router-core/src/workflow_skill_router/persistence/migrations/0003_local_control_plane.sql",
    "packages/router-core/src/workflow_skill_router/routing/consent.py",
    "packages/router-core/src/workflow_skill_router/routing/directives.py",
    "packages/router-core/src/workflow_skill_router/routing/models.py",
    "packages/router-core/src/workflow_skill_router/routing/validator.py",
    "packages/router-core/src/workflow_skill_router/service_models.py",
    "packages/router-core/tests/integration/test_local_control_plane.py",
    "packages/router-core/tests/routing/test_consent.py",
    "packages/router-core/tests/routing/test_profiler.py",
    "packages/router-core/tests/routing/test_route_validator.py",
    "plugins/workflow-skill-router/.codex-plugin/plugin.json",
    "plugins/workflow-skill-router/mcp/server.bundle.mjs",
    "plugins/workflow-skill-router/mcp/src/core-client.ts",
    "plugins/workflow-skill-router/mcp/test/bundled-runtime.test.ts",
    "plugins/workflow-skill-router/package.json",
    "plugins/workflow-skill-router/runtime/workflow_skill_router.pyz",
    "plugins/workflow-skill-router/scripts/build-mcp.mjs",
    "plugins/workflow-skill-router/scripts/build-runtime.py",
    "plugins/workflow-skill-router/skills/workflow-skill-router/SKILL.md",
    "plugins/workflow-skill-router/skills/workflow-skill-router/references/routing-protocol.md",
    "scripts/build-release-artifacts.py",
    "site/src/content/docs/guides/v2-routing.md",
    "site/src/content/docs/showcase.md",
    "site/src/content/docs/zh-tw/guides/v2-routing.md",
    "site/src/content/docs/zh-tw/showcase.md",
    "site/src/data/router-demo-v2.generated.json",
    "starter/v2/workflow-skill-router/SKILL.md",
    "starter/v2/workflow-skill-router/references/routing-protocol.md",
    "tests/test_build_runtime.py",
    "tests/test_release_artifacts.py",
    "tests/test_v2_demo_data.py",
}


class V2OpenSourceBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_manifest_identifies_the_frozen_worktree(self) -> None:
        self.assertEqual("2.0", self.manifest["schema_version"])
        self.assertEqual("codex/workflow-skill-router-v2", self.manifest["branch"])
        self.assertEqual("2.0.0-alpha.1", self.manifest["v2_version"])
        self.assertEqual("v2-first-1", self.manifest["public_tree_policy_revision"])
        self.assertEqual(
            "70f3456270b4395e8d473a3f8cc592391c92b335",
            self.manifest["starting_head"],
        )

    def test_manifest_records_required_suites(self) -> None:
        self.assertEqual(
            [
                "packages/router-core/tests",
                "tests",
                "plugins/workflow-skill-router/mcp/test",
                "site/tests",
            ],
            self.manifest["required_test_suites"],
        )

    def test_manifest_inventory_exactly_matches_the_pre_goal_snapshot(self) -> None:
        changes = self.manifest["inherited_changes"]
        paths = [item["path"] for item in changes]

        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(EXPECTED_INHERITED_PATHS, set(paths))
        self.assertGreater(len(changes), 0)

        for item in changes:
            self.assertIn(item["status"], {" M", "??"})
            self.assertTrue(3 <= item["owner_task"] <= 14)
            self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", item["sha256"]))


if __name__ == "__main__":
    unittest.main()
