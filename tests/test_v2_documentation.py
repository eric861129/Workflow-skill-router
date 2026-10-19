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
        import json
        reference = json.loads((ROOT / "site/src/data/mcp-tools.generated.json").read_text("utf-8"))
        groups = {}
        for tool in reference["tools"]:
            groups.setdefault(tool["availability"], set()).add(tool["name"])
        documents = (
            "README.md", "README.zh-TW.md",
            "docs/architecture/v2-overview.md",
            "site/src/content/docs/concepts/routing-envelopes.md",
            "site/src/content/docs/zh-tw/concepts/routing-envelopes.md",
        )
        for relative in documents:
            text = (ROOT / relative).read_text("utf-8")
            with self.subTest(relative=relative):
                self.assertIn("published-v2.0.2", text)
                self.assertIn("development-main", text)
                source = text.split("development-main", 1)[1]
                for availability, expected in groups.items():
                    rows = [line for line in source.splitlines() if line.startswith("|") and f"`{availability}`" in line]
                    self.assertEqual(1, len(rows), (relative, availability))
                    self.assertEqual(expected, set(re.findall(r"`([^`]+)`", rows[0].split("|")[2])))
                self.assertIn("authority_mode=router-local", source)
                self.assertIn("host_transition_authorized=false", source)
        for relative in documents[2:]:
            text = (ROOT / relative).read_text("utf-8")
            self.assertIn("deterministic-objective-v2", text)
            self.assertIn("classification_source", text)
            self.assertIn("classification_reason_codes", text)
        historical = (ROOT / "docs/adr/0004-explainable-classification-and-runtime-modes.md").read_text("utf-8")
        self.assertIn("Historical decision", historical)
        self.assertIn("deterministic-objective-v1", historical)
        self.assertIn("published-beta.3", historical)
        self.assertFalse((ROOT / "docs/adr/0003-explainable-classification-and-runtime-modes.md").exists())
        self.assertTrue((ROOT / "docs/adr/0003-deterministic-support-consent-state-machine.md").is_file())

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
                self.assertIn("2.3.1", text)
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

    def test_adaptive_workflow_memory_is_default_off_bilingual_and_non_elevating(self):
        pages = (
            "site/src/content/docs/concepts/adaptive-workflow-memory.md",
            "site/src/content/docs/zh-tw/concepts/adaptive-workflow-memory.md",
            "site/src/content/docs/guides/configure-workflow-memory.md",
            "site/src/content/docs/zh-tw/guides/configure-workflow-memory.md",
            "site/src/content/docs/guides/migrate-to-workflow-memory.md",
            "site/src/content/docs/zh-tw/guides/migrate-to-workflow-memory.md",
        )
        for relative in pages:
            text = (ROOT / relative).read_text("utf-8")
            with self.subTest(relative=relative):
                self.assertIn("default-off", text)
                self.assertIn("disabled < observe < reviewed < automatic", text)
                self.assertIn("Workspace cannot elevate Personal", text)
                self.assertIn("automatic-managed", text)
                self.assertIn("intended-unverified", text)
                self.assertIn("no telemetry", text)
                self.assertIn("no background learning", text)
                self.assertIn("User-owned Profile", text)



if __name__=="__main__":unittest.main()
