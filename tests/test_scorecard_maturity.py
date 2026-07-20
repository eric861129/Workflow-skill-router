import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "workflow-skill-router"
PRIVATE_REPORT_URL = (
    "https://github.com/eric861129/Workflow-skill-router/security/advisories/new"
)


class ScorecardMaturityTests(unittest.TestCase):
    def test_security_policy_links_the_private_vulnerability_report_form(self) -> None:
        policy = (ROOT / "SECURITY.md").read_text(encoding="utf-8")

        self.assertIn(PRIVATE_REPORT_URL, policy)

    def test_plugin_runs_scorecard_recognized_property_tests(self) -> None:
        package = json.loads(
            (PLUGIN_ROOT / "package.json").read_text(encoding="utf-8")
        )
        fast_check_version = package.get("devDependencies", {}).get("fast-check", "")
        build_script = (PLUGIN_ROOT / "scripts" / "build-mcp.mjs").read_text(
            encoding="utf-8"
        )
        property_test_path = (
            PLUGIN_ROOT / "mcp" / "test" / "workspace-roots.property.test.ts"
        )

        self.assertRegex(fast_check_version, re.compile(r"^\d+\.\d+\.\d+$"))
        self.assertIn('"workspace-roots.property"', build_script)
        self.assertTrue(property_test_path.is_file())

        property_test = property_test_path.read_text(encoding="utf-8")
        for required in (
            "fc.assert",
            "collectTrustedWorkspaceRoots",
            "bindPlanWorkWorkspaceRoot",
            "WorkspaceRootTrustError",
        ):
            with self.subTest(required=required):
                self.assertIn(required, property_test)


if __name__ == "__main__":
    unittest.main()
