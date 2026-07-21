from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class HostIntegrationKitDocumentationTests(unittest.TestCase):
    def test_reference_adapter_and_bilingual_guides_are_published(self):
        pages = (
            "examples/reference-host-adapter/README.md",
            "docs/integration/verified-host-adapter.md",
            "site/src/content/docs/guides/verified-host-integration.md",
            "site/src/content/docs/zh-tw/guides/verified-host-integration.md",
        )
        required_terms = (
            "reference-not-production-authority",
            "composition.open",
            "runtime authority",
            "scheduler",
            "snapshot",
            "policy",
            "activation",
            "receipt",
            "append-only",
            "evidence",
            "gate",
            "artifact",
            "evaluation",
            "freshness",
            "fail closed",
            "public-safe diagnostic",
            "production_authority_verified=false",
            "routercompositionports",
            "shadow ports",
            "hybrid-full",
        )

        for relative in pages:
            path = ROOT / relative
            with self.subTest(relative=relative):
                self.assertTrue(path.is_file(), relative)
                text = " ".join(path.read_text("utf-8").lower().split())
                for term in required_terms:
                    self.assertIn(term, text, (relative, term))
                self.assertIn("not production", text, relative)

    def test_reference_adapter_is_executable_without_exposing_authority_values(self):
        adapter = ROOT / "examples/reference-host-adapter/reference_host.py"
        self.assertTrue(adapter.is_file())
        text = adapter.read_text("utf-8")
        self.assertIn("REFERENCE_AUTHORITY_LABEL", text)
        self.assertIn("run_host_conformance", text)
        self.assertIn('if __name__ == "__main__":', text)

        forbidden_public_fields = (
            '"database"',
            '"artifact_root"',
            '"secret"',
            '"token"',
            '"executable"',
        )
        for field in forbidden_public_fields:
            self.assertNotIn(field, text)

    def test_verified_host_guide_is_in_site_navigation(self):
        navigation = (ROOT / "site/astro.config.mjs").read_text("utf-8")
        self.assertIn("guides/verified-host-integration", navigation)


if __name__ == "__main__":
    unittest.main()
