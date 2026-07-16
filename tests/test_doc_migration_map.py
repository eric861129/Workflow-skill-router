from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_REPLACEMENTS = {
    "README.en.md": "README.md",
    "docs/adoption-guide.md": "site/src/content/docs/guides/adoption.md",
    "docs/adoption-guide.zh-TW.md": "site/src/content/docs/zh-tw/guides/adoption.md",
    "docs/anti-over-routing.md": "site/src/content/docs/concepts/routing-envelopes.md",
    "docs/case-studies.md": "site/src/content/docs/examples/case-studies.md",
    "docs/contributor-guide-route-examples.md": "site/src/content/docs/contributing/release-process.md",
    "docs/dependency-governance.md": "site/src/content/docs/reference/security-boundaries.md",
    "docs/evaluation-guide.md": "site/src/content/docs/concepts/evaluation-evidence.md",
    "docs/release-cadence.md": "site/src/content/docs/contributing/release-process.md",
    "docs/roadmap.md": "site/src/content/docs/contributing/roadmap.md",
    "docs/routing-metrics-trends.md": "site/src/content/docs/concepts/evaluation-evidence.md",
    "docs/routing-metrics.md": "site/src/content/docs/concepts/evaluation-evidence.md",
    "docs/showcase.md": "site/src/content/docs/showcase.md",
    "docs/skill-inventory-scanner.md": "site/src/content/docs/concepts/runtime-capability-discovery.md",
    "docs/system-theory.en.md": "site/src/content/docs/concepts/routing-envelopes.md",
    "docs/system-theory.md": "site/src/content/docs/concepts/routing-envelopes.md",
    "docs/system-theory.zh-TW.md": "site/src/content/docs/zh-tw/concepts/routing-envelopes.md",
    "docs/v1-to-v2-upgrade.md": "site/src/content/docs/guides/migrate-v1-to-v2.md",
    "docs/v1-to-v2-upgrade.zh-TW.md": "site/src/content/docs/zh-tw/guides/migrate-v1-to-v2.md",
    "docs/v2-architecture.md": "docs/architecture/v2-overview.md",
    "docs/v2-architecture.zh-TW.md": "docs/architecture/v2-overview.md",
    "docs/validation-checklist.en.md": "site/src/content/docs/guides/troubleshooting.md",
    "docs/validation-checklist.md": "site/src/content/docs/guides/troubleshooting.md",
    "docs/validation-checklist.zh-TW.md": "site/src/content/docs/zh-tw/guides/troubleshooting.md",
}


class DocumentationMigrationMapTests(unittest.TestCase):
    def test_durable_legacy_documents_name_a_concrete_v2_replacement(self) -> None:
        manifest = json.loads(
            (ROOT / "release" / "legacy-v1-removal-manifest.json").read_text("utf-8")
        )
        entries = {entry["path"]: entry for entry in manifest["entries"]}
        for legacy_path, replacement in EXPECTED_REPLACEMENTS.items():
            with self.subTest(path=legacy_path):
                self.assertIn(legacy_path, entries)
                self.assertIn(replacement, entries[legacy_path]["replacement_or_recovery"])
                self.assertTrue((ROOT / replacement).is_file())

    def test_v1_release_history_remains_recoverable_from_immutable_tag(self) -> None:
        manifest = json.loads(
            (ROOT / "release" / "legacy-v1-removal-manifest.json").read_text("utf-8")
        )
        historical = [
            entry for entry in manifest["entries"]
            if entry["path"].startswith("docs/release-notes-v1")
            or entry["path"].startswith("docs/launch/v1.3.1-")
        ]
        self.assertTrue(historical)
        for entry in historical:
            self.assertEqual("v1.3.1", entry["historical_source"])
            self.assertIn("v1.3.1", entry["replacement_or_recovery"])


if __name__ == "__main__":
    unittest.main()
