import json
import re
import subprocess
import sys
import tempfile
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


def workflow_job_body(name: str, job: str) -> str:
    for match in JOB_BLOCK_PATTERN.finditer(workflow_text(name)):
        if match.group("job") == job:
            return match.group("body")
    raise AssertionError(f"workflow {name!r} does not define job {job!r}")


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

    def test_validate_requires_one_fail_closed_cross_platform_v2_gate(self) -> None:
        validate = workflow_text("validate.yml")
        artifact_job = workflow_job_body("validate.yml", "release-artifacts")
        required_job = workflow_job_body("validate.yml", "required-v2")
        pages_job = workflow_job_body("validate.yml", "build-pages")

        self.assertEqual(
            "Required cross-platform V2 gate",
            workflow_job_names("validate.yml")["required-v2"],
        )
        self.assertIn(
            "os: [ubuntu-latest, macos-latest, windows-latest]",
            artifact_job,
        )
        for required in (
            "build-release-artifacts.py --check",
            "test_release_artifacts.py tests/test_installation_smoke.py",
            "build-runtime.py --check",
            "PYTHONPATH: packages/router-core/src",
            'discover -s packages/router-core/tests -p "test_*.py" -v',
            "working-directory: plugins/workflow-skill-router",
            "npm ci",
            "npm run check",
        ):
            with self.subTest(required=required):
                self.assertIn(required, artifact_job)

        self.assertIn(
            "needs: [release-artifacts, validate, site-visual]",
            required_job,
        )
        self.assertIn("if: ${{ always() }}", required_job)
        for dependency in ("release-artifacts", "validate", "site-visual"):
            with self.subTest(dependency=dependency):
                self.assertIn(f"needs.{dependency}.result", required_job)
        self.assertIn("'success'", required_job)
        self.assertIn("needs: required-v2", pages_job)
        self.assertNotIn(
            "needs: [release-artifacts, validate, site-visual]",
            pages_job,
        )

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
        pages_job = workflow_job_body("validate.yml", "build-pages")
        self.assertIn("needs: required-v2", pages_job)
        self.assertIn(
            "github.event_name == 'push' && github.ref == 'refs/heads/main'",
            validate,
        )
        self.assertIn("pages: write", validate)
        self.assertIn("id-token: write", validate)
        self.assertIn("actions/deploy-pages@", validate)
        self.assertIn("Smoke test public HTTPS URL", validate)

    def test_release_runs_only_from_a_confirmed_trusted_branch_dispatch(self) -> None:
        content = workflow_text("release-v2.yml")
        for required in (
            "workflow_dispatch:",
            "confirm_release:",
            "CREATE_V2_RELEASE",
            "github.event.repository.default_branch",
            "Verify trusted release dispatch",
            "Dispatch must run from the default branch with explicit confirmation.",
            "release/version.json",
            "release-publication-gate.py",
            '["git", "cat-file", "-e",',
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
        self.assertNotIn("  push:\n", content)
        self.assertNotIn("tags:\n", content)
        self.assertLess(
            content.index("- name: Install Plugin/MCP dependencies"),
            content.index("- name: Test repository contracts"),
        )
        self.assertNotIn("downloads/", content)

    def test_release_requires_exact_tag_revision_on_three_platforms(self) -> None:
        names = workflow_job_names("release-v2.yml")
        source_job = workflow_job_body("release-v2.yml", "resolve-source")
        preflight_job = workflow_job_body("release-v2.yml", "preflight")
        release_job = workflow_job_body("release-v2.yml", "release")

        self.assertEqual("Resolve frozen V2 release source", names["resolve-source"])
        self.assertEqual("V2 preflight (${{ matrix.os }})", names["preflight"])
        self.assertIn("source_revision:", source_job)
        self.assertNotIn("source-revision:", source_job)
        self.assertIn('["git", "cat-file", "-e",', source_job)
        self.assertIn('["git", "merge-base", "--is-ancestor",', source_job)
        self.assertIn("github.event.repository.default_branch", source_job)
        self.assertIn("ref: ${{ github.sha }}", source_job)
        self.assertIn("GITHUB_REF", source_job)
        self.assertIn("CONFIRM_RELEASE", source_job)
        self.assertNotIn("    if:", source_job)

        self.assertIn("needs: resolve-source", preflight_job)
        self.assertIn(
            "os: [ubuntu-latest, macos-latest, windows-latest]",
            preflight_job,
        )
        self.assertIn("ref: ${{ needs.resolve-source.outputs.source_revision }}", preflight_job)
        self.assertIn(
            "needs.resolve-source.outputs.source_revision",
            preflight_job,
        )
        self.assertIn('["git", "rev-parse", "HEAD"]', preflight_job)
        for required in (
            "build-release-artifacts.py --check",
            "test_release_artifacts.py tests/test_installation_smoke.py",
            "build-runtime.py --check",
            "PYTHONPATH: packages/router-core/src",
            'discover -s packages/router-core/tests -p "test_*.py" -v',
            "working-directory: plugins/workflow-skill-router",
            "npm ci",
            "npm run check",
        ):
            with self.subTest(required=required):
                self.assertIn(required, preflight_job)

        self.assertIn("needs: [resolve-source, preflight]", release_job)
        self.assertIn("ref: ${{ needs.resolve-source.outputs.source_revision }}", release_job)
        self.assertIn(
            "needs.resolve-source.outputs.source_revision",
            release_job,
        )

    def test_beta4_release_lane_is_bound_to_its_declared_source_revision(self) -> None:
        metadata = json.loads(
            (ROOT / "release" / "version.json").read_text(encoding="utf-8")
        )
        source_job = workflow_job_body("release-v2.yml", "resolve-source")
        release_job = workflow_job_body("release-v2.yml", "release")
        declared_revision = metadata["release_source_revision"]

        self.assertRegex(declared_revision, r"^[0-9a-f]{40}$")
        self.assertEqual("2.0.0-beta.4", metadata["v2_version"])
        self.assertEqual("prepared-local-candidate", metadata["release_lifecycle"])
        publication_gate = (ROOT / "scripts/release-publication-gate.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('metadata, "release_source_revision"', publication_gate)
        self.assertIn("source_revision={source_revision}", publication_gate)
        self.assertIn("DECLARED_REVISION", source_job)
        self.assertIn("Declared release source is not a reachable trusted revision", source_job)
        self.assertIn("release_tag={release_tag}", publication_gate)
        self.assertIn("Release metadata V2 version is invalid", publication_gate)
        self.assertIn('"git", "ls-remote", "origin"', source_job)
        self.assertIn("Existing release tag does not match declared release source revision", source_job)
        self.assertNotIn('metadata["release_source_revision"]', release_job)
        self.assertLess(
            release_job.index("[\"git\", \"rev-parse\", \"HEAD\"]"),
            release_job.index("- name: Install Plugin/MCP dependencies"),
        )

    def test_prepared_beta4_metadata_fails_the_executable_publication_gate(self) -> None:
        metadata_path = ROOT / "release" / "version.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        trusted_revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()

        self.assertEqual(
            "prepared-local-candidate", metadata.get("release_lifecycle")
        )
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "github-output.txt"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "release-publication-gate.py"),
                    "--metadata",
                    str(metadata_path),
                    "--trusted-revision",
                    trusted_revision,
                    "--github-output",
                    str(output_path),
                ],
                cwd=ROOT,
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=30,
            )

            self.assertFalse(output_path.exists())

        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn("prepared-local-candidate", result.stderr)
        self.assertIn("reviewed-attested-publishable", result.stderr)

    def test_only_reviewed_attested_metadata_emits_the_frozen_release_binding(
        self,
    ) -> None:
        trusted_revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        metadata = {
            "release_lifecycle": "reviewed-attested-publishable",
            "release_source_revision": trusted_revision,
            "v2_version": "2.0.0-beta.4",
        }

        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            metadata_path = directory_path / "version.json"
            output_path = directory_path / "github-output.txt"
            metadata_path.write_text(
                json.dumps(metadata), encoding="utf-8", newline="\n"
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "release-publication-gate.py"),
                    "--metadata",
                    str(metadata_path),
                    "--trusted-revision",
                    trusted_revision,
                    "--github-output",
                    str(output_path),
                ],
                cwd=ROOT,
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(
                f"source_revision={trusted_revision}\nrelease_tag=v2.0.0-beta.4\n",
                output_path.read_text(encoding="utf-8"),
            )

    def test_release_enforces_trusted_lifecycle_before_resolving_frozen_source(
        self,
    ) -> None:
        source_job = workflow_job_body("release-v2.yml", "resolve-source")
        gate_marker = "- name: Enforce trusted publication lifecycle"
        resolve_marker = "- name: Verify declared frozen release source"

        for required in (
            gate_marker,
            "python scripts/release-publication-gate.py",
            "--metadata release/version.json",
            "TRUSTED_METADATA_REVISION: ${{ github.sha }}",
            '--trusted-revision "$TRUSTED_METADATA_REVISION"',
        ):
            with self.subTest(required=required):
                self.assertIn(required, source_job)
        gate_index = source_job.find(gate_marker)
        resolve_index = source_job.find(resolve_marker)
        self.assertGreaterEqual(gate_index, 0)
        self.assertGreaterEqual(resolve_index, 0)
        self.assertLess(gate_index, resolve_index)
        if gate_index >= 0:
            self.assertNotIn("CONFIRM_RELEASE", source_job[gate_index:])

    def test_release_rechecks_remote_tag_before_any_publish_side_effect(self) -> None:
        release_job = workflow_job_body("release-v2.yml", "release")
        guard_name = "Create or verify immutable release tag"
        guard_marker = f"      - name: {guard_name}"
        self.assertIn(guard_marker, release_job)

        for required in (
            'git tag -a "$RELEASE_TAG" "$SOURCE_REVISION"',
            'git push origin "refs/tags/$RELEASE_TAG"',
            "GITHUB_TOKEN",
            'git ls-remote origin "refs/tags/$RELEASE_TAG" "refs/tags/$RELEASE_TAG^{}"',
            '"refs/tags/$RELEASE_TAG")',
            '"refs/tags/$RELEASE_TAG^{}")',
            'remote_source_revision="${peeled_revision:-$direct_revision}"',
            '"$remote_source_revision" != "$SOURCE_REVISION"',
        ):
            with self.subTest(required=required):
                self.assertIn(required, release_job)

        guard_index = release_job.index(guard_marker)
        attestation_index = release_job.index(
            "- name: Attest release assets from checksums"
        )
        artifact_upload_index = release_job.index(
            "- name: Upload release bundle for workflow review"
        )
        release_create_index = release_job.index("gh release create")
        self.assertLess(guard_index, attestation_index)
        self.assertLess(attestation_index, artifact_upload_index)
        self.assertLess(artifact_upload_index, release_create_index)

        publish_tail_steps = re.findall(
            r"(?m)^      - name:\s*(.+?)\s*$",
            release_job[guard_index:],
        )
        self.assertEqual(
            [guard_name, "Attest release assets from checksums"],
            publish_tail_steps[:2],
        )

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
        self.assertEqual(
            {"validate", "site-visual", "required-v2"},
            {check["job"] for check in required_checks},
        )
        for check in required_checks:
            with self.subTest(job=check["job"]):
                names = workflow_job_names(Path(check["workflow"]).name)
                self.assertEqual(names[check["job"]], check["context"])
                self.assertEqual(15368, check["app_id"])

    def test_release_template_lists_every_versioned_required_check_context(self) -> None:
        contract = json.loads(
            (ROOT / ".github" / "branch-protection.json").read_text(encoding="utf-8")
        )
        template = (ROOT / ".github" / "RELEASE_TEMPLATE.md").read_text(
            encoding="utf-8"
        )

        for check in contract["required_status_checks"]["checks"]:
            context = check["context"]
            with self.subTest(context=context):
                self.assertIn(f"`{context}`", template)

    def test_release_template_requires_remote_governance_verifier(self) -> None:
        template = (ROOT / ".github" / "RELEASE_TEMPLATE.md").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "python scripts/verify-remote-governance.py "
            "--repo eric861129/Workflow-skill-router",
            template,
        )
        self.assertIn("does not change GitHub configuration", template)
        self.assertIn(
            "does not prove a release workflow has successfully exercised the "
            "GitHub Actions bypass",
            " ".join(template.split()),
        )

    def test_bilingual_release_processes_define_remote_governance_boundary(self) -> None:
        command = (
            "python scripts/verify-remote-governance.py "
            "--repo eric861129/Workflow-skill-router"
        )
        for path, required_boundaries in (
            (
                ROOT
                / "site"
                / "src"
                / "content"
                / "docs"
                / "contributing"
                / "release-process.md",
                (
                    "This command is read-only and does not change GitHub configuration",
                    "pass confirms the captured configuration meets the checked-in contract",
                    "blocks the release checklist",
                    "privileged external work",
                    "not a live release-workflow rehearsal",
                ),
            ),
            (
                ROOT
                / "site"
                / "src"
                / "content"
                / "docs"
                / "zh-tw"
                / "contributing"
                / "release-process.md",
                (
                    "此命令為唯讀，不會變更 GitHub 設定",
                    "通過僅確認擷取到的設定符合已納入版控的契約",
                    "必須阻擋本次發行清單",
                    "需要權限的外部作業",
                    "不是實際發行工作流程的演練",
                ),
            ),
        ):
            content = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn(command, content)
                for boundary in required_boundaries:
                    with self.subTest(boundary=boundary):
                        self.assertIn(boundary, content)

    def test_remote_release_governance_guide_defines_targets_and_apply_boundaries(
        self,
    ) -> None:
        guide = (ROOT / "docs" / "governance" / "remote-release-governance.md").read_text(
            encoding="utf-8"
        )

        for required in (
            "The protected branch is `main`.",
            "targets `refs/tags/v2.*`",
            "## Apply through the GitHub UI",
            "## Apply through the GitHub API",
            "Applying these settings is privileged external work.",
            "API application is also privileged external work.",
        ):
            with self.subTest(required=required):
                self.assertIn(required, guide)


if __name__ == "__main__":
    unittest.main()
