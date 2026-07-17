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


if __name__=="__main__":unittest.main()
