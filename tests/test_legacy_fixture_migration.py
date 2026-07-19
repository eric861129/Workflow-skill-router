from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "packages" / "router-core" / "tests" / "fixtures" / "legacy-v1"
EXPECTED_DIGESTS = {
    "scenarios.jsonl": "8927b90e946e532b3fddc2aec1a0e85015861faaf5326c1b7688888f565e500f",
    "predictions.jsonl": "136d23856a8bfe6e80ef6001421de58a0504cb9066fe0b14920081ef7c1cb7dc",
}


class LegacyFixtureMigrationTests(unittest.TestCase):
    def test_reviewed_v1_contract_fixtures_keep_the_persisted_git_blob_digests(self):
        for name, expected_digest in EXPECTED_DIGESTS.items():
            with self.subTest(name=name):
                migrated = FIXTURES / name
                self.assertEqual(expected_digest, sha256(migrated.read_bytes()).hexdigest())
                self.assertEqual(80, len([
                    line for line in migrated.read_text(encoding="utf-8").splitlines() if line.strip()
                ]))

    def test_fixture_metadata_keeps_tier_zero_contract_boundary(self):
        metadata = json.loads((FIXTURES / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual("T0", metadata["tier"])
        self.assertEqual("contract-only", metadata["evidence_class"])
        self.assertEqual(EXPECTED_DIGESTS, metadata["sha256"])


if __name__ == "__main__":
    unittest.main()
