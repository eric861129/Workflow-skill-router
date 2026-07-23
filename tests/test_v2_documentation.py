from pathlib import Path
import re
import unittest


ROOT=Path(__file__).resolve().parents[1]
DOCS=(
    "README.md",
    "README.zh-TW.md",
    "site/src/content/docs/guides/v2-routing.md",
    "site/src/content/docs/zh-tw/guides/v2-routing.md",
    "site/src/content/docs/reference/model-evaluation.md",
    "site/src/content/docs/zh-tw/reference/model-evaluation.md",
)


class V2DocumentationTests(unittest.TestCase):
    def test_explainable_classification_and_runtime_mode_contract(self):
        published_beta3_tools = {
            "local-ready": (
                "plan_work",
                "propose_support_consent",
                "transition_support_consent",
                "get_router_status",
            ),
            "verified-host": (
                "sync_runtime_context",
                "get_next_work",
                "validate_route",
                "record_work_event",
                "evaluate_gate",
            ),
            "configured-adapter": (
                "run_model_evaluation",
                "compare_evaluations",
                "export_router_artifact",
            ),
        }
        def readiness_row(section, readiness, relative):
            matching_rows = tuple(
                line
                for line in section.splitlines()
                if line.startswith("|") and f"`{readiness}`" in line
            )
            self.assertEqual(1, len(matching_rows), (relative, readiness))
            row = matching_rows[0]
            tool_cell = row.split("|")[2]
            return tuple(re.findall(r"`([^`]+)`", tool_cell)), row

        documents = (
            "docs/adr/0004-explainable-classification-and-runtime-modes.md",
            "docs/architecture/v2-overview.md",
            "site/src/content/docs/concepts/routing-envelopes.md",
            "site/src/content/docs/zh-tw/concepts/routing-envelopes.md",
        )
        required_terms = (
            "deterministic-objective-v1",
            "classification_source",
            "classification_reason_codes",
            "conditional-local",
            "host_transition_authorized",
            "published-beta.3",
            "prepared-ga-candidate",
            "propose_support_consent",
            "transition_support_consent",
            "not included in published beta.3",
        )

        for relative in documents:
            path = ROOT / relative
            with self.subTest(relative=relative):
                self.assertTrue(path.is_file(), relative)
                text = path.read_text("utf-8")
                for term in required_terms:
                    self.assertIn(term, text, relative)

                published_section = text.split("published-beta.3", 1)[1].split(
                    "prepared-ga-candidate", 1
                )[0]
                source_section = text.split("prepared-ga-candidate", 1)[1]
                for readiness, expected_tools in published_beta3_tools.items():
                    documented_tools, _ = readiness_row(
                        published_section, readiness, relative
                    )
                    self.assertEqual(expected_tools, documented_tools, relative)
                self.assertNotIn("conditional-local", published_section, relative)
                conditional_tools, conditional_row = readiness_row(
                    source_section, "conditional-local", relative
                )
                self.assertEqual(
                    ("get_next_work", "record_work_event", "evaluate_gate"),
                    conditional_tools,
                    relative,
                )
                self.assertIn("authority_mode=router-local", conditional_row, relative)
                self.assertIn(
                    "host_transition_authorized=false", conditional_row, relative
                )
                self.assertIn(
                    "not included in published beta.3", source_section, relative
                )

        self.assertFalse(
            (ROOT / "docs/adr/0003-explainable-classification-and-runtime-modes.md").exists()
        )
        self.assertTrue(
            (ROOT / "docs/adr/0003-deterministic-support-consent-state-machine.md").is_file()
        )
        plan = (
            ROOT / "docs/superpowers/plans/2026-07-21-router-v2-intelligence-to-ga.md"
        ).read_text("utf-8")
        self.assertIn("**Step 2: Write ADR 0004**", plan)
        self.assertNotIn("**Step 2: Write ADR 0003**", plan)
        self.assertIn("0004-explainable-classification-and-runtime-modes.md", plan)
        self.assertNotIn("0003-explainable-classification-and-runtime-modes.md", plan)

    def test_required_claim_boundaries_exist(self):
        for relative in DOCS:
            text=(ROOT/relative).read_text("utf-8")
            self.assertIn("Tier 0 Contract",text,relative)
            self.assertIn("manual-required",text,relative)
            self.assertIn("skill-only-fallback",text,relative)
            self.assertIn("hybrid-full",text,relative)

    def test_bilingual_site_routes_are_paired(self):
        for relative in ("guides/v2-routing.md","reference/model-evaluation.md"):
            self.assertTrue((ROOT/"site/src/content/docs"/relative).is_file())
            self.assertTrue((ROOT/"site/src/content/docs/zh-tw"/relative).is_file())

    def test_personal_routing_profiles_are_first_class_and_honest_in_both_modes(self):
        pages = (
            "README.md",
            "README.zh-TW.md",
            "site/src/content/docs/concepts/personal-routing-profiles.md",
            "site/src/content/docs/zh-tw/concepts/personal-routing-profiles.md",
            "site/src/content/docs/reference/cli.md",
            "site/src/content/docs/zh-tw/reference/cli.md",
        )
        for relative in pages:
            text = (ROOT / relative).read_text("utf-8")
            with self.subTest(relative=relative):
                self.assertIn("Personal Routing Profile", text)
                self.assertIn("workspace", text)
                self.assertIn("personal", text)
                self.assertIn("Runtime Capability Discovery", text)
                self.assertIn("intended-unverified", text)
                self.assertIn("profile preview", text)

        navigation = (ROOT / "site/astro.config.mjs").read_text("utf-8")
        self.assertIn("concepts/personal-routing-profiles", navigation)

        english = (ROOT / pages[2]).read_text("utf-8")
        chinese = (ROOT / pages[3]).read_text("utf-8")
        for text in (english, chinese):
            self.assertIn('"scope": "workspace"', text)
            self.assertIn("workspace-routing-profile.example.json", text)
            self.assertIn("beta.1", text)
        self.assertIn("filesystem access", english)
        self.assertIn("does not cover", english)
        self.assertIn("Host 授權", chinese)
        self.assertIn("不涵蓋", chinese)

    def test_ga_evaluation_budget_matches_contract_2_3(self):
        pages = (
            "site/src/content/docs/concepts/evaluation-evidence.md",
            "site/src/content/docs/contributing/roadmap.md",
            "site/src/content/docs/zh-tw/concepts/evaluation-evidence.md",
            "site/src/content/docs/zh-tw/contributing/roadmap.md",
        )
        for relative in pages:
            text = (ROOT / relative).read_text("utf-8")
            self.assertIn("13", text, relative)
            self.assertIn("78", text, relative)
            self.assertIn("96", text, relative)
            self.assertNotIn("72", text, relative)

    def test_contract_2_3_docs_preserve_offline_and_real_model_evidence_boundaries(self):
        pages = (
            "evaluation/v2/README.md",
            "site/src/content/docs/reference/model-evaluation.md",
            "site/src/content/docs/zh-tw/reference/model-evaluation.md",
        )
        for relative in pages:
            text = (ROOT / relative).read_text("utf-8")
            with self.subTest(relative=relative):
                self.assertIn("2.3.0", text)
                self.assertIn("reference-driver", text)
                if "/zh-tw/" in relative:
                    self.assertNotIn("it does not prove real-model behavior", text)
                    self.assertIn("無法證明真實模型的行為", text)
                else:
                    self.assertIn("does not prove real-model behavior", text)
                self.assertIn("36 attempts", text)
                self.assertIn("42", text)
                self.assertIn("Delta Qualification", text)
                self.assertIn("3 attempts", text)
                if "/zh-tw/" in relative:
                    self.assertIn("單調", text)
                else:
                    self.assertIn("monotonic", text)

        roadmap_zh = (
            ROOT / "site/src/content/docs/zh-tw/contributing/roadmap.md"
        ).read_text("utf-8")
        self.assertNotIn("it does not prove real-model behavior", roadmap_zh)
        self.assertIn("無法證明真實模型的行為", roadmap_zh)


if __name__=="__main__":unittest.main()
