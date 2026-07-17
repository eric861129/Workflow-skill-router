import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE_SOURCE = ROOT / "packages" / "router-core" / "src"
if str(CORE_SOURCE) not in sys.path:
    sys.path.insert(0, str(CORE_SOURCE))
OUTPUT = ROOT / "site" / "src" / "data" / "mcp-tools.generated.json"
SCRIPT = ROOT / "scripts" / "build-mcp-reference-data.mjs"


class McpReferenceDataTests(unittest.TestCase):
    def test_generated_reference_matches_public_tools_and_runtime_readiness(self) -> None:
        from workflow_skill_router.runtime_readiness import RUNTIME_READINESS
        from workflow_skill_router.tool_dispatch import PUBLIC_TOOLS

        document = json.loads(OUTPUT.read_text(encoding="utf-8"))
        self.assertEqual("1.0", document["schema_version"])
        self.assertEqual(list(PUBLIC_TOOLS), [tool["name"] for tool in document["tools"]])
        self.assertEqual(set(PUBLIC_TOOLS), set(document["runtime_readiness"]))

        for tool in document["tools"]:
            readiness = RUNTIME_READINESS[tool["name"]]
            self.assertEqual(readiness.availability, tool["availability"])
            self.assertEqual(readiness.risk_class, tool["risk_class"])
            self.assertEqual(
                list(readiness.required_capabilities),
                tool["required_capabilities"],
            )
            self.assertEqual(readiness.fallback_action, tool["fallback_action"])
            self.assertGreaterEqual(len(tool["title"]), 8)
            self.assertGreaterEqual(len(tool["description"]), 80)
            self.assertIn("readOnlyHint", tool["annotations"])
            self.assertIn("idempotentHint", tool["annotations"])
            self.assertIsInstance(tool["inputSchema"], dict)
            self.assertIsInstance(tool["outputSchema"], dict)

        serialized = OUTPUT.read_text(encoding="utf-8")
        self.assertNotIn(str(ROOT), serialized)
        self.assertNotIn("WORKFLOW_SKILL_ROUTER_DATA_DIR", serialized)

    def test_reference_generator_reports_no_drift(self) -> None:
        result = subprocess.run(
            ["node", str(SCRIPT), "--check"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
