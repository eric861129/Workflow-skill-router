import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GA_VERSION = "2.0.2"


class V2ReleaseCandidateTests(unittest.TestCase):
    def test_product_version_surfaces_are_ga_candidates_without_promoting_latest(self) -> None:
        version = json.loads(
            (ROOT / "release" / "version.json").read_text(encoding="utf-8")
        )
        plugin = json.loads(
            (
                ROOT
                / "plugins"
                / "workflow-skill-router"
                / ".codex-plugin"
                / "plugin.json"
            ).read_text(encoding="utf-8")
        )
        package = json.loads(
            (
                ROOT / "plugins" / "workflow-skill-router" / "package.json"
            ).read_text(encoding="utf-8")
        )
        lock = json.loads(
            (
                ROOT / "plugins" / "workflow-skill-router" / "package-lock.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(GA_VERSION, version["v2_version"])
        self.assertNotIn("target_prerelease", version)
        expected_published_version = (
            GA_VERSION
            if version["release_lifecycle"] == "reviewed-attested-publishable"
            else "2.0.1"
        )
        self.assertEqual(expected_published_version, version["published_v2_version"])
        self.assertEqual("latest", version["stable_channel"])
        self.assertEqual("1.3.1", version["v1_pinned_version"])
        self.assertEqual("latest-v2", version["v2_channel"])
        self.assertEqual(GA_VERSION, plugin["version"])
        self.assertEqual(GA_VERSION, package["version"])
        self.assertEqual(GA_VERSION, lock["version"])
        self.assertEqual(GA_VERSION, lock["packages"][""]["version"])

    def test_mcp_and_readme_product_surfaces_report_the_current_release(self) -> None:
        server_source = (
            ROOT
            / "plugins"
            / "workflow-skill-router"
            / "mcp"
            / "src"
            / "server.ts"
        ).read_text(encoding="utf-8")
        server_bundle = (
            ROOT
            / "plugins"
            / "workflow-skill-router"
            / "mcp"
            / "server.bundle.mjs"
        ).read_text(encoding="utf-8")

        for text in (server_source, server_bundle):
            self.assertIn(f'MCP_SERVER_VERSION = "{GA_VERSION}"', text)
            self.assertIn("version: MCP_SERVER_VERSION", text)
            self.assertNotIn('MCP_SERVER_VERSION = "2.0.0-alpha.1"', text)

        for relative in ("README.md", "README.zh-TW.md"):
            with self.subTest(relative=relative):
                self.assertIn(GA_VERSION, (ROOT / relative).read_text(encoding="utf-8"))

    def test_current_release_copy_matches_the_metadata_lifecycle(self) -> None:
        version = json.loads(
            (ROOT / "release" / "version.json").read_text(encoding="utf-8")
        )
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        traditional_chinese = (ROOT / "README.zh-TW.md").read_text(encoding="utf-8")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

        if version["release_lifecycle"] == "reviewed-attested-publishable":
            self.assertIn("Current published V2 release: `2.0.2`", english)
            self.assertIn("目前已發布的 V2 正式版：`2.0.2`", traditional_chinese)
            self.assertIn("## 2.0.2", changelog)
            self.assertNotIn("## 2.0.2 (prepared", changelog)
            return

        self.assertEqual("prepared-local-candidate", version["release_lifecycle"])
        self.assertIn("Current published V2 release: `2.0.1`", english)
        self.assertIn("目前已發布的 V2 正式版：`2.0.1`", traditional_chinese)
        self.assertIn("## 2.0.2 (prepared", changelog)

    def test_release_version_does_not_silently_migrate_persisted_schema(self) -> None:
        codecs = (
            ROOT
            / "packages"
            / "router-core"
            / "src"
            / "workflow_skill_router"
            / "capabilities"
            / "codecs.py"
        ).read_text(encoding="utf-8")
        self.assertIn('SCHEMA_VERSION = "2.0.0-alpha.1"', codecs)

    def test_legacy_manifest_is_fully_applied_and_v2_surfaces_remain(self) -> None:
        removal = json.loads(
            (ROOT / "release" / "legacy-v1-removal-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(225, len(removal["files"]))
        self.assertEqual([], [path for path in removal["files"] if (ROOT / path).exists()])

        for relative in (
            "starter/v2/workflow-skill-router/SKILL.md",
            "plugins/workflow-skill-router/mcp/server.bundle.mjs",
            "site/src/content/docs/guides/v2-routing.md",
            "site/src/content/docs/zh-tw/guides/v2-routing.md",
            "site/src/content/docs/reference/model-evaluation.md",
            "site/src/content/docs/zh-tw/reference/model-evaluation.md",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_public_adrs_preserve_the_release_boundaries(self) -> None:
        overview = (ROOT / "docs" / "architecture" / "v2-overview.md").read_text(
            encoding="utf-8"
        )
        for relative in (
            "../adr/0001-v2-first-public-surface.md",
            "../adr/0002-release-assets-outside-git.md",
        ):
            self.assertIn(relative, overview)

        for name in (
            "0001-v2-first-public-surface.md",
            "0002-release-assets-outside-git.md",
        ):
            text = (ROOT / "docs" / "adr" / name).read_text(encoding="utf-8")
            for heading in ("## Status", "## Context", "## Decision", "## Consequences"):
                self.assertIn(heading, text, name)

        first = (ROOT / "docs" / "adr" / "0001-v2-first-public-surface.md").read_text(
            encoding="utf-8"
        )
        second = (
            ROOT / "docs" / "adr" / "0002-release-assets-outside-git.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Plugin/MCP", first)
        self.assertIn("SKILL-only", first)
        self.assertIn("latest", first)
        self.assertIn("GitHub Release Assets", second)
        self.assertIn("dist/release", second)
        self.assertIn("schema", second.lower())

    def test_changelog_has_a_distribution_governance_patch_entry(self) -> None:
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## {GA_VERSION}", changelog)
        self.assertIn("canonical", changelog.lower())
        self.assertIn("generated", changelog.lower())

    def test_ga_release_notes_document_distribution_governance(self) -> None:
        notes = (ROOT / "release" / "notes" / f"v{GA_VERSION}.md").read_text(encoding="utf-8")
        self.assertIn("canonical", notes.lower())
        self.assertIn("Scanner", notes)
        self.assertIn("generated target", notes)
        self.assertIn("Official release", notes)
        self.assertNotIn("prepared-local-candidate", notes)
        self.assertNotIn("not yet published", notes)
        self.assertIn("checksums.sha256", notes)
        self.assertIn("SBOM", notes)
        self.assertIn("maintainer-attestation", notes)

    def test_release_attestation_is_present_only_after_reviewed_promotion(self) -> None:
        release = json.loads(
            (ROOT / "release" / "version.json").read_text(encoding="utf-8")
        )
        path = ROOT / "release" / "attestations" / f"v{GA_VERSION}.json"

        if release["release_lifecycle"] == "prepared-local-candidate":
            self.assertFalse(path.exists())
            return

        self.assertEqual("reviewed-attested-publishable", release["release_lifecycle"])
        attestation = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(
            "workflow-skill-router/release-evidence-attestation/1.0",
            attestation["schema_version"],
        )
        self.assertEqual("reviewed", attestation["attestation_status"])
        self.assertEqual(GA_VERSION, attestation["release_version"])
        self.assertEqual(
            release["release_source_revision"],
            attestation["release_source_revision"],
        )
        deterministic = attestation["deterministic_evidence"]
        self.assertEqual("passed", deterministic["status"])
        self.assertTrue(deterministic["scope"])

        behavior = attestation["behavior_evidence"]
        self.assertIn(
            behavior["evidence_class"],
            {"behavior", "unchanged-routing-behavior"},
        )
        self.assertTrue(behavior["evaluation_contract"])
        self.assertTrue(behavior["basis"])
        self.assertTrue(attestation["known_limitations"])

    def test_declared_release_source_revision_is_reachable(self) -> None:
        release = json.loads(
            (ROOT / "release" / "version.json").read_text(encoding="utf-8")
        )
        completed = subprocess.run(
            (
                "git",
                "merge-base",
                "--is-ancestor",
                release["release_source_revision"],
                "HEAD",
            ),
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            0,
            completed.returncode,
            completed.stdout + completed.stderr,
        )


if __name__ == "__main__":
    unittest.main()
