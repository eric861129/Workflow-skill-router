from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "starter" / "v2" / "workflow-skill-router"


class V2StarterSurfaceTests(unittest.TestCase):
    def test_retired_template_catalog_is_absent_and_v2_starter_is_public_safe(self):
        retired = ROOT / "examples" / "template-skill-catalog"
        self.assertFalse(any(path.is_file() for path in retired.rglob("*")))

        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in STARTER.rglob("*.md")
        )
        self.assertNotRegex(text, r"[A-Za-z]:\\Users\\|/Users/|/home/")
        self.assertIn("capability snapshot", text)
        self.assertIn("skill-only-fallback", text)
        self.assertIn("explicit-locked", text)
        self.assertIn("Personal Routing Profile", text)
        self.assertTrue(
            (STARTER / "assets/personal-routing-profile.example.json").is_file()
        )
        self.assertTrue(
            (STARTER / "assets/workspace-routing-profile.example.json").is_file()
        )


if __name__ == "__main__":
    unittest.main()
