import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
ACTION_PATTERN = re.compile(r"\buses:\s*([^@\s]+)@([^\s#]+)")
FULL_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")


def workflow_text(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


class GitHubWorkflowTests(unittest.TestCase):
    def test_every_action_is_pinned_to_an_immutable_commit(self) -> None:
        action_count = 0
        for path in sorted(WORKFLOWS.glob("*.y*ml")):
            for action, ref in ACTION_PATTERN.findall(path.read_text(encoding="utf-8")):
                action_count += 1
                with self.subTest(workflow=path.name, action=action):
                    self.assertRegex(ref, FULL_SHA_PATTERN)
        self.assertGreater(action_count, 0)

    def test_every_workflow_declares_explicit_token_permissions(self) -> None:
        for path in sorted(WORKFLOWS.glob("*.y*ml")):
            content = path.read_text(encoding="utf-8")
            with self.subTest(workflow=path.name):
                self.assertRegex(content, r"(?m)^permissions:\s*$")

    def test_ci_is_offline_and_does_not_execute_v1_public_proof_tools(self) -> None:
        content = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(WORKFLOWS.glob("*.y*ml"))
        ).lower()
        for forbidden in (
            "--confirm-live-run",
            "codex_api_key",
            "openai_api_key",
            "run-v2-benchmark.py",
            "evaluate-routing.py",
            "build-route-gallery.py",
            "render-routing-metrics-trend.py",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, content)

    def test_validate_and_plugin_smoke_run_local_v2_quality_gates(self) -> None:
        validate = workflow_text("validate.yml")
        plugin = workflow_text("v2-plugin-smoke.yml")

        for required in (
            "build-release-artifacts.py --check",
            "python -m unittest discover -s tests",
            "npm run test:site:smoke",
        ):
            self.assertIn(required, validate)
        for required in (
            "build-runtime.py --check",
            "packages/router-core/tests",
            "npm run check",
            "smoke-plugin.mjs",
        ):
            self.assertIn(required, plugin)

    def test_codeql_scans_python_and_javascript_typescript(self) -> None:
        content = workflow_text("codeql.yml")
        self.assertIn("python", content)
        self.assertIn("javascript-typescript", content)
        self.assertIn("security-events: write", content)
        self.assertIn("github/codeql-action/init@", content)
        self.assertIn("github/codeql-action/analyze@", content)

    def test_scorecard_uploads_sarif_with_bounded_permissions(self) -> None:
        content = workflow_text("scorecard.yml")
        for required in (
            "contents: read",
            "security-events: write",
            "id-token: write",
            "results_format: sarif",
            "github/codeql-action/upload-sarif@",
        ):
            self.assertIn(required, content)

    def test_release_only_accepts_v2_tags_and_attests_source_built_assets(self) -> None:
        content = workflow_text("release-v2.yml")
        for required in (
            "tags:",
            '"v2.*"',
            "--provenance-mode release",
            "--source-revision",
            "--require-clean",
            "--check-determinism",
            "sbom/",
            "actions/attest-build-provenance@",
            "attestations: write",
            "id-token: write",
        ):
            self.assertIn(required, content)
        self.assertIn(r"refs/tags/v2\.[0-9]+\.[0-9]+", content)
        self.assertNotIn("downloads/", content)

    def test_dependabot_covers_both_node_projects_and_actions(self) -> None:
        content = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
        for required in ('directory: "/site"', 'directory: "/plugins/workflow-skill-router"'):
            self.assertIn(required, content)
        self.assertIn('package-ecosystem: "github-actions"', content)


if __name__ == "__main__":
    unittest.main()
