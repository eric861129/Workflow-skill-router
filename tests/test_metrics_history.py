from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class MetricsHistoryTests(unittest.TestCase):
    def test_metrics_trend_outputs_are_current(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/render-routing-metrics-trend.py", "--check"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
