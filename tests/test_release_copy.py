import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = json.loads(
    (ROOT / "release" / "version.json").read_text(encoding="utf-8")
)["v2_version"]


class ReleaseCopyTests(unittest.TestCase):
    def test_homepage_proof_stats_match_the_runtime_and_beta_profile(self) -> None:
        homepage = (ROOT / "site/src/components/HomeLanding.astro").read_text(
            encoding="utf-8"
        )

        for required in (
            "['12', 'typed MCP tools']",
            "['4', 'local-ready tools']",
            "['36', 'beta attempts · 42 model turns']",
            "['12', '個型別化 MCP 工具']",
            "['4', '個本機可用工具']",
            "['36', '次 beta 嘗試 · 42 次模型呼叫']",
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
            "workflow-skill-router-plugin-v2.0.0-beta.1.zip",
            "workflow-skill-router-skill-v2.0.0-beta.1.zip",
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
            "eric861129/Workflow-skill-router --ref v2.0.0-beta.1"
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
            "eric861129/Workflow-skill-router --ref v2.0.0-beta.1"
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
        asset = "workflow-skill-router-skill-v2.0.0-beta.1.zip"

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


if __name__ == "__main__":
    unittest.main()
