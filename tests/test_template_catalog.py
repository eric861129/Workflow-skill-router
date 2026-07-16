import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1] / "examples/template-skill-catalog"


class TemplateCatalogTests(unittest.TestCase):
    def test_catalog_is_reproducible_and_documents_only_checked_in_ids(self):
        catalog = json.loads((ROOT / "references/capability-catalog.example.json").read_text("utf-8"))
        ids = {item["canonical_id"] for item in catalog["capabilities"]}
        text = "\n".join(path.read_text("utf-8") for path in ROOT.rglob("*.md"))
        referenced = set(re.findall(r"`([a-z][a-z0-9-]+)`", text))
        self.assertLessEqual(referenced, ids)
        self.assertNotRegex(json.dumps(catalog), r"[A-Za-z]:\\Users\\|/Users/|/home/")
        self.assertIn("not runtime discovery", (ROOT / "README.md").read_text("utf-8"))


if __name__ == "__main__": unittest.main()
