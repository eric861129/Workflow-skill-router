from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_doc_parity",
    ROOT / "scripts" / "check-doc-parity.py",
)
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class DocumentationParityTests(unittest.TestCase):
    def test_readmes_present_v2_contract_in_the_required_order(self) -> None:
        required = [
            "60-second outcome",
            "Plugin + MCP",
            "Skill-only",
            "Runtime Capability Discovery",
            "Single",
            "Phased",
            "Managed Goal",
            "Explicit Skill Lock",
            "Real Model Evaluation",
            "Security boundary",
            "Version channels",
            "V1 migration",
        ]
        for name in ("README.md", "README.zh-TW.md"):
            text = (ROOT / name).read_text("utf-8")
            with self.subTest(readme=name):
                positions = [text.casefold().find(token.casefold()) for token in required]
                self.assertNotIn(-1, positions)
                self.assertEqual(positions, sorted(positions))

    def test_primary_readme_does_not_promote_v1_or_overclaim_runtime(self) -> None:
        text = (ROOT / "README.md").read_text("utf-8")
        primary = text.split("## V1 migration", 1)[0]
        self.assertNotIn("workflow-skill-router-blank.zip", primary)
        self.assertNotIn("README.en.md", text)
        self.assertIsNone(re.search(r"all (?:ten|10) tools.{0,40}(?:local-ready|bundled-ready)", text, re.I | re.S))
        self.assertNotRegex(text, r"Skill-only.{0,40}(?:is|equals) `?hybrid-full`?")
        self.assertNotRegex(text, r"reference.driver.{0,60}real.model.(?:proof|evidence)")

    def test_primary_navigation_is_v2_first(self) -> None:
        config = (ROOT / "site" / "astro.config.mjs").read_text("utf-8")
        self.assertNotIn("examples/template-skill-catalog", config)
        for route in (
            "guides/install-plugin",
            "guides/install-skill",
            "concepts/runtime-capability-discovery",
            "concepts/routing-envelopes",
            "reference/mcp-tools",
            "contributing/release-process",
        ):
            self.assertIn(route, config)

    def test_primary_marketing_surface_uses_v2_install_paths(self) -> None:
        surface = "\n".join(
            (ROOT / path).read_text("utf-8")
            for path in (
                "site/src/components/HomeLanding.astro",
                "site/src/components/DocsPageSidebar.astro",
            )
        )
        for legacy_cta in (
            "Download Blank Router",
            "下載 Blank Router",
            "examples/template-skill-catalog",
            "guides/downloads",
        ):
            self.assertNotIn(legacy_cta, surface)
        for route in ("guides/install-plugin", "guides/install-skill"):
            self.assertIn(route, surface)

    def test_english_and_traditional_chinese_routes_are_paired(self) -> None:
        self.assertEqual([], module.check_parity())


if __name__ == "__main__":
    unittest.main()
