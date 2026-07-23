import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_METADATA = json.loads(
    (ROOT / "release" / "version.json").read_text(encoding="utf-8")
)
VERSION = VERSION_METADATA["v2_version"]
PUBLISHED_VERSION = VERSION_METADATA["published_v2_version"]


class ReleaseCopyTests(unittest.TestCase):
    def test_public_plugin_metadata_uses_the_canonical_documentation_url(self) -> None:
        canonical = "https://huangchiyu.com/Workflow-skill-router/"
        manifest = json.loads(
            (
                ROOT
                / "plugins/workflow-skill-router/.codex-plugin/plugin.json"
            ).read_text(encoding="utf-8")
        )
        package = json.loads(
            (ROOT / "plugins/workflow-skill-router/package.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(canonical, manifest["homepage"])
        self.assertEqual(canonical, manifest["interface"]["websiteURL"])
        self.assertEqual(canonical, package["homepage"])
        self.assertIn("Runtime-aware Skill routing", manifest["description"])
        self.assertIn("Route Codex work", manifest["interface"]["shortDescription"])
        self.assertIn(
            "Discovers runtime capabilities",
            manifest["interface"]["longDescription"],
        )
        self.assertTrue(
            manifest["interface"]["defaultPrompt"][0].startswith("Classify")
        )

    def test_roadmap_separates_completed_beta_work_from_remaining_work(self) -> None:
        pages = (
            "site/src/content/docs/contributing/roadmap.md",
            "site/src/content/docs/zh-tw/contributing/roadmap.md",
        )

        for relative in pages:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("## Beta 2.0.0-beta.1", text)
                self.assertGreaterEqual(text.count("- [x]"), 4)
                self.assertIn("- [ ]", text)
                self.assertLess(
                    text.index("- [x]"),
                    text.index("- [ ]"),
                )

    def test_changelog_records_post_beta_launch_copy(self) -> None:
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        unreleased = changelog.split("## 2.0.0-beta.1", maxsplit=1)[0]

        self.assertNotIn("No unreleased changes", unreleased)
        self.assertIn("immutable release installs", unreleased)
        self.assertIn("canonical documentation URL", unreleased)

    def test_homepage_proof_stats_match_the_runtime_and_beta_profile(self) -> None:
        homepage = (ROOT / "site/src/components/HomeLanding.astro").read_text(
            encoding="utf-8"
        )

        for required in (
            "['12', 'typed MCP tools']",
            "['4', 'local-ready tools']",
            "['36', 'beta.1 attempts · 42 model turns']",
            "['12', '個型別化 MCP 工具']",
            "['4', '個本機可用工具']",
            "['36', '次 beta.1 嘗試 · 42 次模型呼叫']",
        ):
            with self.subTest(required=required):
                self.assertIn(required, homepage)

        for stale in (
            "['10', 'typed MCP tools']",
            "['2', 'local-ready tools']",
            "['72', 'GA behavior attempts']",
        ):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, homepage)

        self.assertIn(
            "plan_work, propose_support_consent, transition_support_consent, get_router_status",
            homepage,
        )
        self.assertIn("historical beta.1 evidence", homepage)
        self.assertIn("Personal Routing Profiles and beta.2", homepage)

    def test_public_guides_list_all_four_local_ready_tools(self) -> None:
        pages = (
            "site/src/content/docs/guides/downloads.md",
            "site/src/content/docs/guides/install-plugin.md",
            "site/src/content/docs/guides/quickstart.md",
            "site/src/content/docs/zh-tw/guides/downloads.md",
            "site/src/content/docs/zh-tw/guides/install-plugin.md",
            "site/src/content/docs/zh-tw/guides/quickstart.md",
        )
        for relative in pages:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("plan_work", text)
                self.assertIn("propose_support_consent", text)
                self.assertIn("transition_support_consent", text)
                self.assertIn("get_router_status", text)

    def test_local_state_docs_do_not_claim_unverified_plugin_uninstall_continuity(self) -> None:
        pages = (
            "plugins/workflow-skill-router/README.md",
            "site/src/content/docs/guides/install-plugin.md",
            "site/src/content/docs/reference/local-state.md",
            "site/src/content/docs/zh-tw/reference/local-state.md",
            "site/src/content/docs/zh-tw/guides/install-plugin.md",
        )
        unsupported_claims = (
            "Uninstalling the Plugin does not silently delete Router state.",
            "Uninstalling does not delete external Router state.",
            "`codex plugin remove` also leaves state intact.",
            "`codex plugin remove` 也會保留它。",
            "移除 Plugin 不會刪除外部 Router state。",
            "remove/reinstall preserves state",
            "移除後重新安裝仍會保留 state。",
        )
        required_boundaries = {
            "plugins/workflow-skill-router/README.md": (
                "outside the Plugin installation/cache boundary",
                "local-root replacement",
                "`codex plugin remove` followed by reinstall",
                "Windows/macOS/Linux",
                "has not yet been completed",
            ),
            "site/src/content/docs/guides/install-plugin.md": (
                "outside the Plugin installation/cache boundary",
                "local-root replacement",
                "`codex plugin remove` followed by reinstall",
                "Windows/macOS/Linux",
                "has not yet been completed",
            ),
            "site/src/content/docs/reference/local-state.md": (
                "outside the Plugin installation/cache boundary",
                "local-root replacement",
                "`codex plugin remove` followed by reinstall",
                "Windows/macOS/Linux",
                "has not yet been completed",
            ),
            "site/src/content/docs/zh-tw/reference/local-state.md": (
                "Plugin 安裝／快取邊界之外",
                "local-root replacement",
                "`codex plugin remove` 後再重新安裝",
                "Windows/macOS/Linux",
                "尚未完成",
            ),
            "site/src/content/docs/zh-tw/guides/install-plugin.md": (
                "Plugin 安裝／快取邊界之外",
                "local-root replacement",
                "`codex plugin remove` 後再重新安裝",
                "Windows/macOS/Linux",
                "尚未完成",
            ),
        }

        for relative in pages:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("Plugin", text)
                self.assertIn("state", text.lower())
                for boundary in required_boundaries[relative]:
                    self.assertIn(boundary, text)
                for claim in unsupported_claims:
                    self.assertNotIn(claim, text)

    def test_public_contract_distinguishes_always_local_from_conditional_local(self) -> None:
        pages = (
            "README.md",
            "README.zh-TW.md",
            "site/src/content/docs/reference/mcp-tools.mdx",
            "site/src/content/docs/zh-tw/reference/mcp-tools.mdx",
            "site/src/content/docs/concepts/managed-goals.md",
            "site/src/content/docs/zh-tw/concepts/managed-goals.md",
        )
        for relative in pages:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("4 always local-ready", text)
                self.assertIn("3 Router-owned conditional-local", text)
                self.assertIn("Explicit Skill Lock", text)
                self.assertIn("consent", text)
                self.assertIn("Native Goal", text)
                self.assertIn("fail closed", text)
                self.assertIn("local gate", text.lower())
                self.assertNotIn("all 7/12 tools are local-ready", text)

        for relative in ("README.md", "README.zh-TW.md"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("latest", text)
                self.assertIn("V1.3.1", text)

    def test_beta3_quickstart_and_prepared_ga_candidate_are_not_conflated(self) -> None:
        for relative, contributor_marker, candidate_phrase, unpublished_phrase in (
            ("README.md", "For contributors", "prepared GA candidate", "not yet released"),
            ("README.zh-TW.md", "需要修改 Router", "已準備的 GA candidate", "尚未發布"),
        ):
            text = (ROOT / relative).read_text(encoding="utf-8")
            quickstart = text.split(
                f"--ref v{PUBLISHED_VERSION}", 1
            )[1].split(contributor_marker, 1)[0]
            with self.subTest(relative=relative):
                self.assertIn("4 always local-ready", quickstart)
                self.assertIn("5 verified-Host-required", quickstart)
                self.assertNotIn("3 Router-owned conditional-local", quickstart)
                self.assertIn(candidate_phrase, text)
                self.assertIn("not included in published beta.3", text)
                self.assertIn("2.0.0", text)
                self.assertIn(unpublished_phrase, text)
                self.assertNotIn("prepared beta.5 candidate", text)

    def test_conditional_local_failure_contract_is_tool_specific_and_public_safe(self) -> None:
        pages = (
            "README.md",
            "README.zh-TW.md",
            "site/src/content/docs/concepts/routing-envelopes.md",
            "site/src/content/docs/zh-tw/concepts/routing-envelopes.md",
            "docs/adr/0004-explainable-classification-and-runtime-modes.md",
        )
        required = (
            "router-owned-work-graph",
            "verified-host-scheduler",
            "verified-event-store",
            "activation-receipt-verifier",
            "verified-evidence-store",
            "gate-authority",
            "internal-error",
        )
        stale = (
            "missing or corrupt graph fail closed to the verified Host path",
            "缺少 graph 或 graph 損毀時一律 fail closed 到 verified Host 路徑",
        )
        for relative in pages:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                for term in required:
                    self.assertIn(term, text)
                for phrase in stale:
                    self.assertNotIn(phrase, text)

    def test_published_beta_is_described_in_the_present_tense(self) -> None:
        public_pages = (
            "README.md",
            "README.zh-TW.md",
            "plugins/workflow-skill-router/README.md",
            "site/src/content/docs/guides/downloads.md",
            "site/src/content/docs/guides/install-plugin.md",
            "site/src/content/docs/guides/install-skill.md",
            "site/src/content/docs/guides/troubleshooting.md",
            "site/src/content/docs/zh-tw/guides/downloads.md",
            "site/src/content/docs/zh-tw/guides/install-plugin.md",
            "site/src/content/docs/zh-tw/guides/install-skill.md",
            "site/src/content/docs/zh-tw/guides/troubleshooting.md",
        )
        stale_phrases = (
            "After the immutable `v2.0.0-beta.1` tag is published",
            "After the `v2.0.0-beta.1` tag is published",
            "until the immutable beta tag is published",
            "before the immutable beta tag exists",
            "until that tag exists",
            "After beta publication",
            "become available only after the GitHub prerelease is published",
            "immutable `v2.0.0-beta.1` tag 發布後",
            "不可變 beta tag 尚未發布前",
            "不可變的 beta tag 尚未發布前",
            "Beta 發布後",
            "只有在 GitHub prerelease 發布後才會存在",
            "在對應 tag 存在前",
        )

        for relative in public_pages:
            text = (ROOT / relative).read_text(encoding="utf-8")
            for stale in stale_phrases:
                with self.subTest(relative=relative, stale=stale):
                    self.assertNotIn(stale, text)

    def test_current_readmes_describe_the_sealed_contract_2_3_run_boundary(self) -> None:
        pages = (
            ("README.md", "source and adapter"),
            ("README.zh-TW.md", "來源與 adapter"),
        )
        for relative, binding_phrase in pages:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("Evaluation contract `2.3.0`", text)
                self.assertIn(binding_phrase, text)
                self.assertNotIn("Before a fresh authorized `2.2.0` run", text)

    def test_troubleshooting_distinguishes_conditional_local_from_verified_host_paths(self) -> None:
        pages = (
            "site/src/content/docs/guides/troubleshooting.md",
            "site/src/content/docs/zh-tw/guides/troubleshooting.md",
        )
        for relative in pages:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("conditional-local", text)
                self.assertIn("get_next_work", text)
                self.assertIn("record_work_event", text)
                self.assertIn("evaluate_gate", text)
                self.assertIn("validate_route", text)
                self.assertIn("router-owned-work-graph", text)
                self.assertIn("verified-host", text)

    def test_release_process_documents_the_trusted_manual_tag_boundary(self) -> None:
        pages = (
            (
                "site/src/content/docs/contributing/release-process.md",
                "trusted default branch",
                "Do not",
            ),
            (
                "site/src/content/docs/zh-tw/contributing/release-process.md",
                "受信任的預設分支",
                "不得",
            ),
        )
        for relative, trusted_branch_phrase, denial_phrase in pages:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("CREATE_V2_RELEASE", text)
                self.assertIn("release_source_revision", text)
                self.assertIn(trusted_branch_phrase, text)
                self.assertIn("Release GitHub App", text)
                self.assertIn(denial_phrase, text)

    def test_public_docs_explain_the_prepared_candidate_publication_guard(self) -> None:
        pages = (
            "README.md",
            "README.zh-TW.md",
            "release/notes/v2.0.0.md",
            "site/src/content/docs/contributing/release-process.md",
            "site/src/content/docs/zh-tw/contributing/release-process.md",
        )
        for relative in pages:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("release_lifecycle", text)
                self.assertIn("prepared-local-candidate", text)
                self.assertIn("reviewed-attested-publishable", text)
                self.assertIn("release_source_revision", text)
                self.assertIn("CREATE_V2_RELEASE", text)

        for relative, ordered_steps, unchanged_candidate in (
            (
                "site/src/content/docs/contributing/release-process.md",
                (
                    "Build and freeze a candidate SHA",
                    "Run required evidence and review against that exact SHA",
                    "Create a trusted metadata-only promotion commit",
                    "Dispatch `Release V2`",
                ),
                "already-reviewed unchanged candidate",
            ),
            (
                "site/src/content/docs/zh-tw/contributing/release-process.md",
                (
                    "建置並凍結 candidate SHA",
                    "針對該 exact SHA 執行必要 evidence 與 review",
                    "建立受信任的 metadata-only promotion commit",
                    "Dispatch `Release V2`",
                ),
                "已審查且未變更的 candidate",
            ),
        ):
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                positions = [text.find(step) for step in ordered_steps]
                for step, position in zip(ordered_steps, positions, strict=True):
                    with self.subTest(step=step):
                        self.assertGreaterEqual(position, 0)
                if all(position >= 0 for position in positions):
                    self.assertEqual(sorted(positions), positions)
                self.assertIn(unchanged_candidate, text)
                self.assertNotIn("update lifecycle and source revision", text)

    def test_release_process_requires_fresh_ga_behavior_evidence(
        self,
    ) -> None:
        pages = (
            (
                "site/src/content/docs/contributing/release-process.md",
                "A formal GA release requires fresh final behavior-model evidence",
                "Contract fixtures, the reference driver, and Pilot preparation cannot satisfy this requirement",
                "Corrected Behavior evidence is complete, paired, and reviewed.",
            ),
            (
                "site/src/content/docs/zh-tw/contributing/release-process.md",
                "正式 GA release 必須具備新的最終 behavior-model evidence",
                "Contract fixtures、reference driver 與 Pilot preparation 都不能滿足此要求",
                "修正後的 Behavior evidence 已完成、成對且經過審查。",
            ),
        )
        for relative, conditional_gate, non_evidence, false_completion in pages:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn(conditional_gate, text)
                self.assertIn(non_evidence, text)
                self.assertNotIn(false_completion, text)

    def test_skill_only_docs_match_the_release_allowlist(self) -> None:
        allowlist = json.loads(
            (ROOT / "release/allowlists/skill-package.json").read_text(
                encoding="utf-8"
            )
        )["files"]
        pages = (
            "site/src/content/docs/guides/downloads.md",
            "site/src/content/docs/guides/install-skill.md",
            "site/src/content/docs/zh-tw/guides/downloads.md",
            "site/src/content/docs/zh-tw/guides/install-skill.md",
        )

        for relative in pages:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertNotIn("agents/", text)
                self.assertNotIn("agent metadata", text.lower())
                for packaged_file in allowlist:
                    self.assertIn(packaged_file, text)

    def test_release_notes_explain_value_installation_and_beta_boundaries(self) -> None:
        notes_path = ROOT / "release" / "notes" / f"v{VERSION}.md"
        self.assertTrue(notes_path.is_file(), notes_path)
        notes = notes_path.read_text(encoding="utf-8")

        for required in (
            "## Why V2",
            "## Choose your install mode",
            f"workflow-skill-router-plugin-v{VERSION}.zip",
            f"workflow-skill-router-skill-v{VERSION}.zip",
            "36 attempts",
            "42 model turns",
            "checksums.sha256",
            "maintainer-attestation",
        ):
            with self.subTest(required=required):
                self.assertIn(required, notes)

        workflow = (ROOT / ".github/workflows/release-v2.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('--notes-file "release/notes/${RELEASE_TAG}.md"', workflow)
        self.assertNotIn("--generate-notes", workflow)

    def test_general_installation_precedes_contributor_checkout(self) -> None:
        pages = (
            "README.md",
            "README.zh-TW.md",
            "plugins/workflow-skill-router/README.md",
            "site/src/content/docs/guides/install-plugin.md",
            "site/src/content/docs/zh-tw/guides/install-plugin.md",
        )
        tagged_command = (
            "codex plugin marketplace add "
            f"eric861129/Workflow-skill-router --ref v{PUBLISHED_VERSION}"
        )

        for relative in pages:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn(tagged_command, text)
                self.assertIn("codex plugin marketplace add .", text)
                self.assertLess(
                    text.index(tagged_command),
                    text.index("codex plugin marketplace add ."),
                )

    def test_tagged_install_has_a_checkout_free_verification_path(self) -> None:
        pages = (
            ("README.md", "new Codex task", "For contributors"),
            ("README.zh-TW.md", "新的 Codex 任務", "需要修改 Router"),
            (
                "plugins/workflow-skill-router/README.md",
                "new Codex task",
                "For a contributor checkout",
            ),
            (
                "site/src/content/docs/guides/install-plugin.md",
                "new task",
                "## Contributor checkout",
            ),
            (
                "site/src/content/docs/zh-tw/guides/install-plugin.md",
                "新任務",
                "## 從開發 checkout 安裝",
            ),
        )
        tagged_command = (
            "codex plugin marketplace add "
            f"eric861129/Workflow-skill-router --ref v{PUBLISHED_VERSION}"
        )

        for relative, task_phrase, contributor_marker in pages:
            text = (ROOT / relative).read_text(encoding="utf-8")
            tagged_start = text.index(tagged_command)
            contributor_start = text.find(contributor_marker, tagged_start)
            if contributor_start == -1:
                contributor_start = len(text)
            normal_install = text[tagged_start:contributor_start]
            with self.subTest(relative=relative):
                self.assertIn("codex plugin list", normal_install)
                self.assertIn(task_phrase, normal_install)
                self.assertNotIn("workflow_skill_router.pyz doctor", normal_install)
                self.assertNotIn("smoke-plugin.mjs", normal_install)

    def test_skill_only_release_asset_precedes_checkout_instructions(self) -> None:
        pages = (
            "README.md",
            "README.zh-TW.md",
            "site/src/content/docs/guides/install-skill.md",
            "site/src/content/docs/zh-tw/guides/install-skill.md",
        )
        asset = f"workflow-skill-router-skill-v{PUBLISHED_VERSION}.zip"

        for relative in pages:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertLess(
                    text.index(asset),
                    text.index("starter/v2/workflow-skill-router")
                    if "starter/v2/workflow-skill-router" in text
                    else text.index('"starter\\v2\\workflow-skill-router"'),
                )

    def test_zh_entry_copy_explains_the_choice_before_runtime_jargon(self) -> None:
        readme = (ROOT / "README.zh-TW.md").read_text(encoding="utf-8")
        downloads = (
            ROOT / "site/src/content/docs/zh-tw/guides/downloads.md"
        ).read_text(encoding="utf-8")
        skill_only = (
            ROOT / "site/src/content/docs/zh-tw/guides/install-skill.md"
        ).read_text(encoding="utf-8")

        self.assertIn("開始工作前先判斷任務大小", readme)
        self.assertIn("一般使用者若要完整功能，直接選 Plugin + MCP", downloads)
        self.assertIn("只想讓 Codex 在工作前選擇合適的 SKILL", skill_only)
        self.assertLess(
            readme.index("開始工作前先判斷任務大小"),
            readme.index("runtime-aware"),
        )
        self.assertLess(
            downloads.index("一般使用者若要完整功能，直接選 Plugin + MCP"),
            downloads.index("policy core"),
        )
        self.assertLess(
            skill_only.index("只想讓 Codex 在工作前選擇合適的 SKILL"),
            skill_only.index("durable resume"),
        )

    def test_ga_candidate_public_surfaces_preserve_routing_and_authority_boundaries(self) -> None:
        pages = (
            "README.md",
            "README.zh-TW.md",
            "site/src/content/docs/guides/v2-routing.md",
            "site/src/content/docs/zh-tw/guides/v2-routing.md",
            "site/src/content/docs/reference/mcp-tools.mdx",
            "site/src/content/docs/zh-tw/reference/mcp-tools.mdx",
        )
        required = (
            "deterministic automatic classification",
            "optional deterministic Profile",
            "unverified",
            "Explicit Skill Lock",
            "consent",
            "native Codex Goal",
            "deployment/production authority",
        )
        for relative in pages:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                for phrase in required:
                    self.assertIn(phrase, text)

    def test_generated_plugin_runtime_executes_profile_explain_and_lint(self) -> None:
        runtime = (
            ROOT
            / "plugins/workflow-skill-router/runtime/workflow_skill_router.pyz"
        )
        profile = (
            ROOT
            / "starter/v2/workflow-skill-router/assets/"
            "personal-routing-profile.example.json"
        )
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"

            def run(*arguments: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [sys.executable, str(runtime), "profile", *arguments],
                    cwd=ROOT,
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    timeout=30,
                )

            installed = run("install", str(profile), "--data-dir", str(state))
            self.assertEqual(0, installed.returncode, installed.stderr)

            explained = run(
                "preview",
                "--data-dir",
                str(state),
                "--objective",
                "Deliver the API",
                "--work-mode",
                "phased",
                "--domain",
                "api",
                "--explain",
            )
            self.assertEqual(0, explained.returncode, explained.stderr)
            self.assertTrue(json.loads(explained.stdout)["rule_traces"])

            linted = run("lint", str(profile), "--current-phase", "contract")
            self.assertEqual(0, linted.returncode, linted.stderr)
            self.assertEqual("valid", json.loads(linted.stdout)["status"])

    def test_demo_labels_planned_support_without_claiming_activation(self) -> None:
        source = (
            ROOT / "site/src/scripts/adaptive-router-demo.ts"
        ).read_text(encoding="utf-8")
        self.assertIn("planned-unverified", source)
        self.assertNotIn("router-approved", source)

    def test_demo_renderer_uses_selected_branch_evidence_and_truthful_labels(self) -> None:
        source = (
            ROOT / "site/src/scripts/adaptive-router-demo.ts"
        ).read_text(encoding="utf-8")
        component = (
            ROOT / "site/src/components/AdaptiveRouterDemo.astro"
        ).read_text(encoding="utf-8")
        self.assertIn("const branchRouting = branch.routing_evidence", source)
        self.assertIn('data-testid="demo-planned-skills"', source)
        self.assertIn("branchRouting.planned_skill_ids", source)
        self.assertIn("PLANNED NON-SKILL SELECTIONS", source)
        self.assertIn('data-testid="demo-planned-non-skill-selections"', source)
        self.assertIn("branchRouting.planned_non_skill_selection_ids", source)
        self.assertIn('data-testid="demo-explicit-lock"', source)
        self.assertIn("branchRouting.explicit_skill_lock", source)
        self.assertIn("routing.profile_match", source)
        self.assertNotIn("PROFILE MATCH SOURCE", source)
        self.assertNotIn("explicit coverage", source)
        self.assertNotIn("demo-explicit-coverage", component)


if __name__ == "__main__":
    unittest.main()
