import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
ACTION_PATTERN = re.compile(r"\buses:\s*([^@\s]+)@([^\s#]+)")
FULL_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
JOB_BLOCK_PATTERN = re.compile(
    r"(?ms)^  (?P<job>[A-Za-z0-9_-]+):\s*\n"
    r"(?P<body>.*?)(?=^  [A-Za-z0-9_-]+:\s*\n|\Z)"
)


def workflow_text(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def workflow_job_names(name: str) -> dict[str, str]:
    jobs: dict[str, str] = {}
    for match in JOB_BLOCK_PATTERN.finditer(workflow_text(name)):
        job_name = re.search(r"(?m)^    name:\s*(.+?)\s*$", match.group("body"))
        if job_name:
            jobs[match.group("job")] = job_name.group(1)
    return jobs


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

        plugin_install = validate.index("Install plugin build dependencies")
        repository_tests = validate.index("Run repository unit tests")
        self.assertLess(plugin_install, repository_tests)

    def test_digest_bound_text_is_checked_out_with_stable_lf_bytes(self) -> None:
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("* text=auto eol=lf", attributes.splitlines())

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

    def test_pages_deploys_only_after_validating_the_trusted_main_revision(self) -> None:
        validate = workflow_text("validate.yml")
        all_workflows = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(WORKFLOWS.glob("*.y*ml"))
        )

        self.assertFalse((WORKFLOWS / "deploy-site.yml").exists())
        self.assertNotIn("workflow_run:", all_workflows)
        self.assertNotIn("github.event.workflow_run.head_sha", all_workflows)
        self.assertIn("needs: [release-artifacts, validate, site-visual]", validate)
        self.assertIn(
            "github.event_name == 'push' && github.ref == 'refs/heads/main'",
            validate,
        )
        self.assertIn("pages: write", validate)
        self.assertIn("id-token: write", validate)
        self.assertIn("actions/deploy-pages@", validate)
        self.assertIn("Smoke test public HTTPS URL", validate)

    def test_release_only_accepts_v2_tags_and_supports_safe_tag_retries(self) -> None:
        content = workflow_text("release-v2.yml")
        for required in (
            "tags:",
            '"v2.*"',
            "workflow_dispatch:",
            "release_tag:",
            "RELEASE_TAG:",
            "ref: ${{ env.RELEASE_TAG }}",
            'git rev-list -n 1 "$RELEASE_TAG"',
            "--provenance-mode release",
            '--source-revision "$SOURCE_REVISION"',
            "--require-clean",
            "--check-determinism",
            "sbom/",
            "actions/attest-build-provenance@",
            "attestations: write",
            "id-token: write",
        ):
            self.assertIn(required, content)
        self.assertIn(r"^v2\.[0-9]+\.[0-9]+", content)
        self.assertLess(
            content.index("- name: Install Plugin/MCP dependencies"),
            content.index("- name: Test repository contracts"),
        )
        self.assertNotIn("downloads/", content)

    def test_dependabot_covers_both_node_projects_and_actions(self) -> None:
        content = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
        for required in ('directory: "/site"', 'directory: "/plugins/workflow-skill-router"'):
            self.assertIn(required, content)
        self.assertIn('package-ecosystem: "github-actions"', content)

    def test_branch_protection_contract_tracks_actual_check_run_names(self) -> None:
        contract = json.loads(
            (ROOT / ".github" / "branch-protection.json").read_text(encoding="utf-8")
        )
        self.assertEqual("main", contract["branch"])
        self.assertTrue(contract["required_status_checks"]["strict"])

        required_checks = contract["required_status_checks"]["checks"]
        self.assertEqual(2, len(required_checks))
        for check in required_checks:
            with self.subTest(job=check["job"]):
                names = workflow_job_names(Path(check["workflow"]).name)
                self.assertEqual(names[check["job"]], check["context"])
                self.assertEqual(15368, check["app_id"])


if __name__ == "__main__":
    unittest.main()
