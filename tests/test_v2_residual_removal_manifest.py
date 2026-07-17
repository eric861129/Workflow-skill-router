import json
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "release" / "v2-residual-removal-manifest.json"


class V2ResidualRemovalManifestTests(unittest.TestCase):
    def test_approved_manifest_is_exact_and_fully_applied(self) -> None:
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))
        files = document["files"]

        self.assertEqual("1.0", document["schema_version"])
        self.assertEqual(27, document["selection_count"])
        self.assertEqual(27, len(files))
        self.assertEqual(sorted(set(files)), files)
        self.assertTrue(all("*" not in path for path in files))
        self.assertTrue(all(not (ROOT / path).exists() for path in files))
        self.assertFalse(document["approval_required"])
        self.assertEqual("approved-and-applied", document["approval_status"])
        self.assertEqual(
            {"files_still_present": 0, "unexpected_tracked_deletions": 0},
            document["verification"],
        )

        self.assertEqual(
            Counter(
                {
                    "superseded-community-forms": 4,
                    "migrated-internal-plans": 10,
                    "retired-v1-cli-goldens": 6,
                    "retired-v1-generators": 6,
                    "orphaned-v1-site-component": 1,
                }
            ),
            Counter(
                {
                    name: group["count"]
                    for name, group in document["groups"].items()
                }
            ),
        )
        self.assertTrue(
            all(group["replacement"] for group in document["groups"].values())
        )


if __name__ == "__main__":
    unittest.main()
