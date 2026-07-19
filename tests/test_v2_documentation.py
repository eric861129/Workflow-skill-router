from pathlib import Path
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

    def test_ga_evaluation_budget_matches_contract_2_1(self):
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


if __name__=="__main__":unittest.main()
