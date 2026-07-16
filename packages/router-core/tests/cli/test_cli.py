import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[4]


class CliTests(unittest.TestCase):
    def test_doctor_is_honest_and_has_no_telemetry(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = {**os.environ, "PYTHONPATH": str(ROOT / "packages/router-core/src")}
            result = subprocess.run([sys.executable, "-m", "workflow_skill_router", "doctor",
                                     "--database", str(Path(directory) / "router.db")],
                                    text=True, encoding="utf-8", capture_output=True, env=environment)
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("core-ready", payload["runtime_status"])
        self.assertIsNone(payload["conformance_profile"])
        self.assertEqual("skill-only-fallback", payload["fallback_mode"])
        self.assertFalse(payload["telemetry_enabled"])

    def test_v1_scripts_are_not_wrapped(self):
        sources = "\n".join(path.read_text(encoding="utf-8") for path in
                            (ROOT / "packages/router-core/src/workflow_skill_router/cli").glob("*.py"))
        for legacy in ("scan-skills.py", "evaluate-routing.py", "validate-router.py"):
            self.assertNotIn(legacy, sources)


if __name__ == "__main__": unittest.main()
