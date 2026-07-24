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
FULL_SHA_PATTERN = re.compile(r"\A[0-9a-f]{40}\Z")
PUBLISHABLE_LIFECYCLE = "reviewed-attested-publishable"
PREPARED_LIFECYCLE = "prepared-local-candidate"
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
    def _create_release_fixture(
        self,
        directory: Path,
        *,
        frozen_version: str,
        trusted_version: str,
        frozen_v1_pinned_version: object = "1.3.1",
        trusted_v1_pinned_version: object = "1.3.1",
        include_frozen_v1_pinned_version: bool = True,
        include_trusted_v1_pinned_version: bool = True,
        notes_match: bool = True,
        trusted_notes_change: bool = False,
        trusted_notes_newline: str | None = None,
        trusted_plugin_runtime_allowlist_change: bool = False,
        frozen_plugin_runtime_allowlist_files: list[str] | None = None,
        frozen_release_path_safety_source: str | None = None,
        frozen_release_path_safety_exists: bool = True,
        trusted_release_path_safety_source: str | None = None,
        trusted_release_path_safety_newline: str = "\n",
    ) -> tuple[str, str]:
        subprocess.run(["git", "init", "--quiet"], cwd=directory, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Release Test"],
            cwd=directory,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "release-test@example.invalid"],
            cwd=directory,
            check=True,
        )
        subprocess.run(
            ["git", "config", "core.autocrlf", "false"],
            cwd=directory,
            check=True,
        )

        release = directory / "release"
        notes = release / "notes"
        allowlists = release / "allowlists"
        scripts = directory / "scripts"
        notes.mkdir(parents=True)
        allowlists.mkdir(parents=True)
        scripts.mkdir(parents=True)
        frozen_metadata: dict[str, object] = {"v2_version": frozen_version}
        if include_frozen_v1_pinned_version:
            frozen_metadata["v1_pinned_version"] = frozen_v1_pinned_version
        (release / "version.json").write_text(
            json.dumps(frozen_metadata),
            encoding="utf-8",
            newline="\n",
        )
        notes_version = frozen_version if notes_match else "2.0.0-beta.3"
        (notes / f"v{frozen_version}.md").write_text(
            "\n".join(
                (
                    f"# Workflow Skill Router v{frozen_version}",
                    f"workflow-skill-router-plugin-v{notes_version}.zip",
                    f"workflow-skill-router-skill-v{notes_version}.zip",
                    "checksums.sha256",
                    "maintainer-attestation",
                )
            ),
            encoding="utf-8",
            newline="\n",
        )
        (allowlists / "plugin-runtime-files.json").write_text(
            json.dumps(
                {
                    "files": frozen_plugin_runtime_allowlist_files
                    or ["runtime/workflow_skill_router.pyz"]
                }
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        (allowlists / "plugin-package.json").write_text(
            '{"files": []}\n', encoding="utf-8", newline="\n"
        )
        (allowlists / "skill-package.json").write_text(
            '{"files": []}\n', encoding="utf-8", newline="\n"
        )
        (scripts / "build-release-artifacts.py").write_text(
            "\n".join(
                (
                    'RELEASE / "allowlists" / "plugin-runtime-files.json"',
                    'RELEASE / "allowlists" / "skill-package.json"',
                    'plugin_name = f"workflow-skill-router-plugin-v{version}.zip"',
                    'skill_name = f"workflow-skill-router-skill-v{version}.zip"',
                    'files[output_dir / "checksums.sha256"] = checksums',
                )
            ),
            encoding="utf-8",
            newline="\n",
        )
        if frozen_release_path_safety_exists:
            (scripts / "release_path_safety.py").write_text(
                frozen_release_path_safety_source
                or "def parse_safe_relative_posix_path(value):\n    return value\n",
                encoding="utf-8",
                newline="\n",
            )
        subprocess.run(["git", "add", "."], cwd=directory, check=True)
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "candidate"],
            cwd=directory,
            check=True,
        )
        frozen_revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=directory, text=True
        ).strip()

        trusted_metadata: dict[str, object] = {
            "release_lifecycle": "reviewed-attested-publishable",
            "release_source_revision": frozen_revision,
            "v2_version": trusted_version,
        }
        if include_trusted_v1_pinned_version:
            trusted_metadata["v1_pinned_version"] = trusted_v1_pinned_version
        (release / "version.json").write_text(
            json.dumps(trusted_metadata),
            encoding="utf-8",
            newline="\n",
        )
        if trusted_notes_change:
            notes_path = notes / f"v{frozen_version}.md"
            notes_path.write_text(
                notes_path.read_text(encoding="utf-8") + "trusted note change\n",
                encoding="utf-8",
                newline="\n",
            )
        if trusted_notes_newline is not None:
            notes_path = notes / f"v{frozen_version}.md"
            notes_path.write_text(
                notes_path.read_text(encoding="utf-8"),
                encoding="utf-8",
                newline=trusted_notes_newline,
            )
        if trusted_plugin_runtime_allowlist_change:
            (allowlists / "plugin-runtime-files.json").write_text(
                '{"files": ["runtime/tampered.pyz", "runtime/workflow_skill_router.pyz"]}\n',
                encoding="utf-8",
                newline="\n",
            )
        promotion_paths = [
            "release/version.json",
            "release/notes",
            "release/allowlists",
        ]
        if trusted_release_path_safety_source is not None:
            (scripts / "release_path_safety.py").write_text(
                trusted_release_path_safety_source,
                encoding="utf-8",
                newline=trusted_release_path_safety_newline,
            )
            promotion_paths.append("scripts/release_path_safety.py")
        subprocess.run(
            ["git", "add", *promotion_paths],
            cwd=directory,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "promote"],
            cwd=directory,
            check=True,
        )
        trusted_revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=directory, text=True
        ).strip()
        return frozen_revision, trusted_revision

    def _run_publication_gate(
        self, repository: Path, trusted_revision: str
    ) -> tuple[subprocess.CompletedProcess[str], Path]:
        output_path = repository / "github-output.txt"
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "release-publication-gate.py"),
                "--metadata",
                str(repository / "release" / "version.json"),
                "--trusted-revision",
                trusted_revision,
                "--github-output",
                str(output_path),
            ],
            cwd=repository,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=30,
        )
        return result, output_path

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

    def test_every_workflow_release_builder_launch_is_isolated(self) -> None:
        isolated_launch = "python -I -S -B scripts/build-release-artifacts.py"
        for workflow_name in ("validate.yml", "release-v2.yml"):
            content = workflow_text(workflow_name)
            invocation_count = content.count("scripts/build-release-artifacts.py")
            with self.subTest(workflow=workflow_name):
                self.assertGreater(invocation_count, 0)
                self.assertEqual(invocation_count, content.count(isolated_launch))

    def test_release_builder_documentation_uses_the_isolated_launch(self) -> None:
        isolated_launch = "python -I -S -B scripts/build-release-artifacts.py"
        for path in (
            ROOT / "README.md",
            ROOT / "README.zh-TW.md",
            ROOT / "CONTRIBUTING.md",
            ROOT / "scripts" / "README.md",
            ROOT
            / "site"
            / "src"
            / "content"
            / "docs"
            / "contributing"
            / "release-process.md",
            ROOT
            / "site"
            / "src"
            / "content"
            / "docs"
            / "zh-tw"
            / "contributing"
            / "release-process.md",
            ROOT
            / "docs"
            / "superpowers"
            / "plans"
            / "2026-07-21-router-v2-intelligence-to-ga.md",
        ):
            with self.subTest(path=path):
                content = path.read_text(encoding="utf-8")
                invocation_count = content.count("scripts/build-release-artifacts.py")
                self.assertGreater(invocation_count, 0)
                self.assertEqual(invocation_count, content.count(isolated_launch))

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

    def test_release_uses_a_scoped_github_app_token_for_tag_and_release(self) -> None:
        release_job = workflow_job_body("release-v2.yml", "release")

        self.assertIn("permissions:\n      contents: read", release_job)
        self.assertNotIn("permissions:\n      contents: write", release_job)
        self.assertIn(
            "actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1",
            release_job,
        )
        self.assertIn("client-id: ${{ vars.WSR_RELEASE_APP_CLIENT_ID }}", release_job)
        self.assertIn(
            "private-key: ${{ secrets.WSR_RELEASE_APP_PRIVATE_KEY }}", release_job
        )
        self.assertIn("owner: ${{ github.repository_owner }}", release_job)
        self.assertIn("permission-contents: write", release_job)
        self.assertIn(
            "GITHUB_TOKEN: ${{ steps.release-app-token.outputs.token }}", release_job
        )
        self.assertIn(
            "GH_TOKEN: ${{ steps.release-app-token.outputs.token }}", release_job
        )

    def test_ga_release_lane_is_bound_to_its_declared_source_revision(self) -> None:
        metadata = json.loads(
            (ROOT / "release" / "version.json").read_text(encoding="utf-8")
        )
        source_job = workflow_job_body("release-v2.yml", "resolve-source")
        release_job = workflow_job_body("release-v2.yml", "release")
        declared_revision = metadata["release_source_revision"]

        self.assertRegex(declared_revision, r"^[0-9a-f]{40}$")
        self.assertRegex(metadata["v2_version"], r"^2\.\d+\.\d+$")
        self.assertNotIn("target_prerelease", metadata)
        self.assertIn(
            metadata["release_lifecycle"],
            {PREPARED_LIFECYCLE, PUBLISHABLE_LIFECYCLE},
        )
        publication_gate = (ROOT / "scripts/release-publication-gate.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('metadata, "release_source_revision"', publication_gate)
        self.assertIn("source_revision={source_revision}", publication_gate)
        self.assertIn("DECLARED_REVISION", source_job)
        self.assertIn("Declared release source is not a reachable trusted revision", source_job)
        self.assertIn("release_tag={release_tag}", publication_gate)
        self.assertIn("Release metadata V2 version is invalid", publication_gate)
        self.assertNotIn("target_prerelease", publication_gate)
        self.assertIn('"git", "ls-remote", "origin"', source_job)
        self.assertIn("Existing release tag does not match declared release source revision", source_job)
        self.assertNotIn('metadata["release_source_revision"]', release_job)
        self.assertLess(
            release_job.index("[\"git\", \"rev-parse\", \"HEAD\"]"),
            release_job.index("- name: Install Plugin/MCP dependencies"),
        )

    def test_current_release_metadata_declares_a_valid_lifecycle(self) -> None:
        metadata_path = ROOT / "release" / "version.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        lifecycle = metadata.get("release_lifecycle")
        self.assertIn(lifecycle, {PREPARED_LIFECYCLE, PUBLISHABLE_LIFECYCLE})
        self.assertRegex(metadata["release_source_revision"], r"^[0-9a-f]{40}$")
        self.assertRegex(metadata["v2_version"], r"^2\.\d+\.\d+$")

        source_job = workflow_job_body("release-v2.yml", "resolve-source")
        self.assertIn("fetch-depth: 0", source_job)
        self.assertIn("python scripts/release-publication-gate.py", source_job)

    def test_reviewed_ga_metadata_is_bound_to_the_frozen_candidate_source(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            frozen_revision, trusted_revision = self._create_release_fixture(
                repository,
                frozen_version="2.0.0",
                trusted_version="2.0.0",
            )
            result, output_path = self._run_publication_gate(
                repository, trusted_revision
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(
                f"source_revision={frozen_revision}\nrelease_tag=v2.0.0\n",
                output_path.read_text(encoding="utf-8"),
            )

    def test_publishable_ga_metadata_without_target_prerelease_emits_ga_tag(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            frozen_revision, trusted_revision = self._create_release_fixture(
                repository,
                frozen_version="2.0.0",
                trusted_version="2.0.0",
            )

            result, output_path = self._run_publication_gate(
                repository, trusted_revision
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(
                f"source_revision={frozen_revision}\nrelease_tag=v2.0.0\n",
                output_path.read_text(encoding="utf-8"),
            )

    def test_release_enforces_trusted_lifecycle_before_resolving_frozen_source(
        self,
    ) -> None:
        source_job = workflow_job_body("release-v2.yml", "resolve-source")
        publication_gate = (ROOT / "scripts/release-publication-gate.py").read_text(
            encoding="utf-8"
        )
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
        for required in (
            '["git", "show",',
            '["git", "cat-file", "-e",',
            "release/notes/{release_tag}.md",
            "release/allowlists/plugin-runtime-files.json",
            "release/allowlists/skill-package.json",
        ):
            with self.subTest(required=required):
                self.assertIn(required, publication_gate)
        main_block = publication_gate.split("def main() -> int:", maxsplit=1)[1]
        contract_index = main_block.find("_verify_frozen_source_contract")
        output_index = main_block.find("arguments.github_output.write_text")
        self.assertGreaterEqual(contract_index, 0)
        self.assertGreaterEqual(output_index, 0)
        if contract_index >= 0 and output_index >= 0:
            self.assertLess(contract_index, output_index)

    def test_publishable_metadata_rejects_a_mismatched_frozen_source_version(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            _, trusted_revision = self._create_release_fixture(
                repository,
                frozen_version="2.0.0-beta.3",
                trusted_version="2.0.0-beta.4",
            )
            result, output_path = self._run_publication_gate(
                repository, trusted_revision
            )

            self.assertEqual(1, result.returncode, result.stderr)
            self.assertIn(
                "Frozen release metadata does not match trusted release version",
                result.stderr,
            )
            self.assertFalse(output_path.exists())

    def test_publishable_metadata_rejects_a_rebound_frozen_v1_channel(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            _, trusted_revision = self._create_release_fixture(
                repository,
                frozen_version="2.0.0-beta.4",
                trusted_version="2.0.0-beta.4",
                frozen_v1_pinned_version="1.3.2",
            )
            result, output_path = self._run_publication_gate(
                repository, trusted_revision
            )

            self.assertEqual(1, result.returncode, result.stderr)
            self.assertIn(
                "Frozen release metadata does not match trusted V1 channel contract",
                result.stderr,
            )
            self.assertFalse(output_path.exists())

    def test_publishable_metadata_enforces_the_v1_hard_ceiling_when_contracts_match(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            _, trusted_revision = self._create_release_fixture(
                repository,
                frozen_version="2.0.0-beta.4",
                trusted_version="2.0.0-beta.4",
                frozen_v1_pinned_version="1.3.2",
                trusted_v1_pinned_version="1.3.2",
            )
            result, output_path = self._run_publication_gate(
                repository, trusted_revision
            )

            self.assertEqual(1, result.returncode, result.stderr)
            self.assertIn(
                "Release metadata V1 pinned version is invalid.",
                result.stderr,
            )
            self.assertFalse(output_path.exists())

    def test_publishable_metadata_rejects_missing_or_non_string_trusted_v1_pin(
        self,
    ) -> None:
        cases = (
            ("missing", False, "1.3.1"),
            ("non-string", True, 1),
        )
        for case, include_v1_pin, v1_pin in cases:
            with self.subTest(case=case):
                with tempfile.TemporaryDirectory() as directory:
                    repository = Path(directory)
                    _, trusted_revision = self._create_release_fixture(
                        repository,
                        frozen_version="2.0.0-beta.4",
                        trusted_version="2.0.0-beta.4",
                        trusted_v1_pinned_version=v1_pin,
                        include_trusted_v1_pinned_version=include_v1_pin,
                    )
                    result, output_path = self._run_publication_gate(
                        repository, trusted_revision
                    )

                    self.assertEqual(1, result.returncode, result.stderr)
                    self.assertIn(
                        "Release metadata 'v1_pinned_version' is missing or invalid.",
                        result.stderr,
                    )
                    self.assertFalse(output_path.exists())

    def test_publishable_metadata_rejects_missing_or_non_string_frozen_v1_pin(
        self,
    ) -> None:
        cases = (
            ("missing", False, "1.3.1"),
            ("non-string", True, 1),
        )
        for case, include_v1_pin, v1_pin in cases:
            with self.subTest(case=case):
                with tempfile.TemporaryDirectory() as directory:
                    repository = Path(directory)
                    _, trusted_revision = self._create_release_fixture(
                        repository,
                        frozen_version="2.0.0-beta.4",
                        trusted_version="2.0.0-beta.4",
                        frozen_v1_pinned_version=v1_pin,
                        include_frozen_v1_pinned_version=include_v1_pin,
                    )
                    result, output_path = self._run_publication_gate(
                        repository, trusted_revision
                    )

                    self.assertEqual(1, result.returncode, result.stderr)
                    self.assertIn(
                        "Frozen release metadata does not match trusted V1 channel contract",
                        result.stderr,
                    )
                    self.assertFalse(output_path.exists())

    def test_publishable_metadata_accepts_the_pinned_frozen_v1_channel_contract(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            frozen_revision, trusted_revision = self._create_release_fixture(
                repository,
                frozen_version="2.0.0-beta.4",
                trusted_version="2.0.0-beta.4",
            )
            result, output_path = self._run_publication_gate(
                repository, trusted_revision
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(
                f"source_revision={frozen_revision}\nrelease_tag=v2.0.0-beta.4\n",
                output_path.read_text(encoding="utf-8"),
            )

    def test_publishable_metadata_rejects_a_mismatched_frozen_artifact_contract(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            _, trusted_revision = self._create_release_fixture(
                repository,
                frozen_version="2.0.0-beta.4",
                trusted_version="2.0.0-beta.4",
                notes_match=False,
            )
            result, output_path = self._run_publication_gate(
                repository, trusted_revision
            )

            self.assertEqual(1, result.returncode, result.stderr)
            self.assertIn(
                "Frozen release notes do not match the trusted artifact contract",
                result.stderr,
            )
            self.assertFalse(output_path.exists())

    def test_publishable_metadata_rejects_release_notes_changed_after_freeze(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            _, trusted_revision = self._create_release_fixture(
                repository,
                frozen_version="2.0.0-beta.4",
                trusted_version="2.0.0-beta.4",
                trusted_notes_change=True,
            )
            result, output_path = self._run_publication_gate(
                repository, trusted_revision
            )

            self.assertEqual(1, result.returncode, result.stderr)
            self.assertIn(
                "Frozen release notes differ from trusted release contract",
                result.stderr,
            )
            self.assertFalse(output_path.exists())

    def test_publishable_metadata_rejects_release_notes_crlf_tamper_after_freeze(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            _, trusted_revision = self._create_release_fixture(
                repository,
                frozen_version="2.0.0-beta.4",
                trusted_version="2.0.0-beta.4",
                trusted_notes_newline="\r\n",
            )
            result, output_path = self._run_publication_gate(
                repository, trusted_revision
            )

            self.assertEqual(1, result.returncode, result.stderr)
            self.assertIn(
                "Frozen release notes differ from trusted release contract",
                result.stderr,
            )
            self.assertFalse(output_path.exists())

    def test_publishable_metadata_rejects_plugin_runtime_allowlist_changed_after_freeze(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            _, trusted_revision = self._create_release_fixture(
                repository,
                frozen_version="2.0.0-beta.4",
                trusted_version="2.0.0-beta.4",
                trusted_plugin_runtime_allowlist_change=True,
            )
            result, output_path = self._run_publication_gate(
                repository, trusted_revision
            )

            self.assertEqual(1, result.returncode, result.stderr)
            self.assertIn("plugin-runtime-files.json", result.stderr)
            self.assertFalse(output_path.exists())

    def test_publishable_metadata_rejects_frozen_builder_helper_changed_after_freeze(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            _, trusted_revision = self._create_release_fixture(
                repository,
                frozen_version="2.0.0-beta.4",
                trusted_version="2.0.0-beta.4",
                frozen_release_path_safety_source=(
                    "def parse_safe_relative_posix_path(value):\n    return 'tampered'\n"
                ),
                trusted_release_path_safety_source=(
                    "def parse_safe_relative_posix_path(value):\n    return value\n"
                ),
            )
            result, output_path = self._run_publication_gate(
                repository, trusted_revision
            )

            self.assertEqual(1, result.returncode, result.stderr)
            self.assertIn(
                "Frozen release artifact builder dependency differs from trusted release contract",
                result.stderr,
            )
            self.assertFalse(output_path.exists())

    def test_publishable_metadata_rejects_builder_helper_crlf_tamper_after_freeze(
        self,
    ) -> None:
        helper_source = "def parse_safe_relative_posix_path(value):\n    return value\n"
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            _, trusted_revision = self._create_release_fixture(
                repository,
                frozen_version="2.0.0-beta.4",
                trusted_version="2.0.0-beta.4",
                trusted_release_path_safety_source=helper_source,
                trusted_release_path_safety_newline="\r\n",
            )
            result, output_path = self._run_publication_gate(
                repository, trusted_revision
            )

            self.assertEqual(1, result.returncode, result.stderr)
            self.assertIn(
                "Frozen release artifact builder dependency differs from trusted release contract",
                result.stderr,
            )
            self.assertFalse(output_path.exists())

    def test_publishable_metadata_accepts_unchanged_frozen_builder_dependency_closure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            frozen_revision, trusted_revision = self._create_release_fixture(
                repository,
                frozen_version="2.0.0-beta.4",
                trusted_version="2.0.0-beta.4",
            )
            result, output_path = self._run_publication_gate(
                repository, trusted_revision
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(
                f"source_revision={frozen_revision}\nrelease_tag=v2.0.0-beta.4\n",
                output_path.read_text(encoding="utf-8"),
            )

    def test_publishable_metadata_rejects_malformed_frozen_builder_helper(
        self,
    ) -> None:
        malformed_helper = "def parse_safe_relative_posix_path(:\n    pass\n"
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            _, trusted_revision = self._create_release_fixture(
                repository,
                frozen_version="2.0.0-beta.4",
                trusted_version="2.0.0-beta.4",
                frozen_release_path_safety_source=malformed_helper,
                trusted_release_path_safety_source=malformed_helper,
            )
            result, output_path = self._run_publication_gate(
                repository, trusted_revision
            )

            self.assertEqual(1, result.returncode, result.stderr)
            self.assertIn("Frozen release artifact builder dependency is invalid", result.stderr)
            self.assertFalse(output_path.exists())

    def test_publishable_metadata_rejects_missing_frozen_builder_helper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            _, trusted_revision = self._create_release_fixture(
                repository,
                frozen_version="2.0.0-beta.4",
                trusted_version="2.0.0-beta.4",
                frozen_release_path_safety_exists=False,
            )
            result, output_path = self._run_publication_gate(
                repository, trusted_revision
            )

            self.assertEqual(1, result.returncode, result.stderr)
            self.assertIn("release_path_safety.py", result.stderr)
            self.assertFalse(output_path.exists())

    def test_publishable_metadata_rejects_windows_unsafe_frozen_allowlist_paths(
        self,
    ) -> None:
        unsafe_paths = (
            r"..\escape.txt",
            r"C:\escape.txt",
            "C:/escape.txt",
            r"\\server\share\escape.txt",
            r"\rooted\escape.txt",
            "/rooted/escape.txt",
            "//server/share/escape.txt",
            "nested/.. /.. /escape.txt",
            "nested/... /... /... ",
            ". /escape.txt",
            "nested/.. ./escape.txt",
            "nested/..../escape.txt",
            "nested./escape.txt",
            "nested /escape.txt",
            "nested/CON.txt",
            "nested/name?.txt",
            "nested/AUX.txt",
            "nested/NUL.tar.gz",
            "nested/PRN.json",
            "nested/CONIN$.txt",
            "nested/CONOUT$.json",
            "nested/COM0.txt",
            "nested/com9.tar.gz",
            "nested/LPT0.txt",
            "nested/lpt9.json",
            "nested/COM\u00b9.txt",
            "nested/com\u00b2.tar.gz",
            "nested/LPT\u00b2.txt",
            "nested/LPT\u00b3.json",
        )

        for unsafe_path in unsafe_paths:
            with self.subTest(unsafe_path=unsafe_path), tempfile.TemporaryDirectory() as directory:
                repository = Path(directory)
                _, trusted_revision = self._create_release_fixture(
                    repository,
                    frozen_version="2.0.0-beta.4",
                    trusted_version="2.0.0-beta.4",
                    frozen_plugin_runtime_allowlist_files=[unsafe_path],
                )
                result, output_path = self._run_publication_gate(
                    repository, trusted_revision
                )

                self.assertEqual(1, result.returncode, result.stderr)
                self.assertIn("unsafe file path", result.stderr)
                self.assertFalse(output_path.exists())

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

    def test_plugin_distribution_publication_contract_is_explicit(self) -> None:
        contract = json.loads(
            (ROOT / "release" / "plugin-distribution.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(
            {
                "app_client_id_variable": "WSR_RELEASE_APP_CLIENT_ID",
                "app_private_key_secret": "WSR_RELEASE_APP_PRIVATE_KEY",
                "branch": "main",
                "repository": "eric861129/workflow-skill-router-plugin",
                "scanner_workflow": "HOL Plugin Scanner",
                "tag_pattern": "v*",
            },
            contract["publication"],
        )

    def test_release_publishes_plugin_distribution_only_after_source_release(
        self,
    ) -> None:
        publication_job = workflow_job_body(
            "release-v2.yml", "publish-plugin-distribution"
        )

        for required in (
            "needs: [resolve-source, preflight, release]",
            "group: plugin-distribution-release",
            "cancel-in-progress: false",
            "contents: read",
            "ref: ${{ needs.resolve-source.outputs.source_revision }}",
            "client-id: ${{ vars.WSR_RELEASE_APP_CLIENT_ID }}",
            "private-key: ${{ secrets.WSR_RELEASE_APP_PRIVATE_KEY }}",
            "permission-administration: read",
            "permission-actions: read",
            "permission-contents: write",
            "permission-workflows: write",
            "scripts/verify-plugin-distribution-governance.py",
            '$RUNNER_TEMP/plugin-distribution',
            '$RUNNER_TEMP/plugin-target',
            "scripts/build-plugin-distribution-repo.py",
            "scripts/sync-plugin-distribution-repo.py",
            "git diff --cached --quiet",
            "git push origin HEAD:main",
            'gh release create "$RELEASE_TAG"',
            '--repo "$TARGET_REPOSITORY"',
        ):
            with self.subTest(required=required):
                self.assertIn(required, publication_job)

        self.assertNotIn("--force", publication_job)
        self.assertNotIn("git clean", publication_job)

        governance_index = publication_job.index(
            "scripts/verify-plugin-distribution-governance.py"
        )
        publish_index = publication_job.index("git push origin HEAD:main")
        self.assertLess(governance_index, publish_index)

        action_refs = ACTION_PATTERN.findall(publication_job)
        self.assertGreater(len(action_refs), 0)
        for action, ref in action_refs:
            with self.subTest(action=action):
                self.assertRegex(ref, FULL_SHA_PATTERN)

    def test_plugin_distribution_sync_receives_target_repository_identity(
        self,
    ) -> None:
        publication_job = workflow_job_body(
            "release-v2.yml", "publish-plugin-distribution"
        )

        self.assertIn(
            '--expected-remote "$TARGET_REPOSITORY"',
            publication_job,
        )
        self.assertNotIn(
            '--expected-remote "https://github.com/${TARGET_REPOSITORY}.git"',
            publication_job,
        )

    def test_plugin_distribution_tag_waits_for_exact_target_scanner_success(
        self,
    ) -> None:
        publication_job = workflow_job_body(
            "release-v2.yml", "publish-plugin-distribution"
        )

        for required in (
            'TARGET_SCANNER_WORKFLOW: "HOL Plugin Scanner"',
            'TARGET_TAG_PATTERN: "v*"',
            '--workflow "$TARGET_SCANNER_WORKFLOW"',
            '--commit "$TARGET_REVISION"',
            "gh run watch",
            "--exit-status",
            "gh run view",
            "--json headSha",
            '"$SCANNER_HEAD_SHA" != "$TARGET_REVISION"',
            'git tag -a "$RELEASE_TAG" "$TARGET_REVISION"',
            'git push origin "refs/tags/$RELEASE_TAG"',
            '"refs/tags/$RELEASE_TAG^{}"',
            '"$REMOTE_TARGET_REVISION" != "$TARGET_REVISION"',
        ):
            with self.subTest(required=required):
                self.assertIn(required, publication_job)

        scanner_index = publication_job.index("gh run watch")
        scanner_head_index = publication_job.index('"$SCANNER_HEAD_SHA" != "$TARGET_REVISION"')
        tag_index = publication_job.index('git tag -a "$RELEASE_TAG" "$TARGET_REVISION"')
        self.assertLess(scanner_index, scanner_head_index)
        self.assertLess(scanner_head_index, tag_index)

    def test_plugin_distribution_creates_or_verifies_target_release_after_tag(
        self,
    ) -> None:
        publication_job = workflow_job_body(
            "release-v2.yml", "publish-plugin-distribution"
        )

        tag_index = publication_job.index('git tag -a "$RELEASE_TAG" "$TARGET_REVISION"')
        release_index = publication_job.index('gh release create "$RELEASE_TAG"')
        self.assertLess(tag_index, release_index)
        self.assertIn(
            'gh api --include --method GET '
            '"repos/$TARGET_REPOSITORY/releases/tags/$RELEASE_TAG"',
            publication_job,
        )
        self.assertIn(
            "grep -Eq '^HTTP/[0-9.]+ 404[[:space:]]'",
            publication_job,
        )
        self.assertNotIn('gh release view "$RELEASE_TAG"', publication_job)
        self.assertIn("verify_target_release", publication_job)
        self.assertIn('Workflow Skill Router Plugin $RELEASE_TAG', publication_job)

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
            "Release GitHub App bypass",
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

    def test_release_processes_name_the_scoped_release_app_token(self) -> None:
        english = (
            ROOT
            / "site"
            / "src"
            / "content"
            / "docs"
            / "contributing"
            / "release-process.md"
        ).read_text(encoding="utf-8")
        traditional_chinese = (
            ROOT
            / "site"
            / "src"
            / "content"
            / "docs"
            / "zh-tw"
            / "contributing"
            / "release-process.md"
        ).read_text(encoding="utf-8")

        self.assertIn("scoped Release GitHub App token", english)
        self.assertNotIn("release workflow's `GITHUB_TOKEN`", english)
        self.assertIn("受範圍限制的 Release GitHub App token", traditional_chinese)
        self.assertNotIn("release workflow 的 `GITHUB_TOKEN`", traditional_chinese)

    def test_remote_release_governance_guide_defines_targets_and_apply_boundaries(
        self,
    ) -> None:
        guide = (ROOT / "docs" / "governance" / "remote-release-governance.md").read_text(
            encoding="utf-8"
        )

        for required in (
            "The protected branch is `main`.",
            "targets `refs/tags/v2.*`",
            "Workflow Skill Router Release GitHub App",
            "`4361147`",
            "## Apply through the GitHub UI",
            "## Apply through the GitHub API",
            "Applying these settings is privileged external work.",
            "API application is also privileged external work.",
        ):
            with self.subTest(required=required):
                self.assertIn(required, guide)


if __name__ == "__main__":
    unittest.main()
