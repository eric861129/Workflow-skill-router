from __future__ import annotations

import json
from pathlib import Path
import unittest

from legacy_cli_cases import CASES
from golden_runner import run_case


GOLDEN = Path(__file__).with_name("golden") / "legacy-cli-v1.json"


class LegacyCliGoldenTests(unittest.TestCase):
    def test_every_declared_cli_matches_frozen_contract(self) -> None:
        expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
        actual = {case.name: run_case(case) for case in CASES}
        self.assertEqual(expected, actual)

    def test_case_names_are_unique_and_sorted_in_golden(self) -> None:
        expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
        self.assertEqual(len(CASES), len({case.name for case in CASES}))
        self.assertEqual(list(expected), sorted(expected))


if __name__ == "__main__":
    unittest.main()
