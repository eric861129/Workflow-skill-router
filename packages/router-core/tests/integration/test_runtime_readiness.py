import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


class RuntimeReadinessTests(unittest.TestCase):
    def test_matrix_classifies_all_public_tools_truthfully(self) -> None:
        spec = importlib.util.find_spec("workflow_skill_router.runtime_readiness")
        self.assertIsNotNone(spec, "runtime_readiness module must exist")
        from workflow_skill_router.runtime_readiness import RUNTIME_READINESS
        from workflow_skill_router.tool_dispatch import PUBLIC_TOOLS

        self.assertEqual(set(PUBLIC_TOOLS), set(RUNTIME_READINESS))
        self.assertEqual("local-ready", RUNTIME_READINESS["plan_work"].availability)
        self.assertEqual(
            "local-ready", RUNTIME_READINESS["get_router_status"].availability
        )
        self.assertEqual(
            "verified-host-required",
            RUNTIME_READINESS["get_next_work"].availability,
        )
        self.assertEqual(
            "configured-adapter-required",
            RUNTIME_READINESS["run_model_evaluation"].availability,
        )
        for entry in RUNTIME_READINESS.values():
            self.assertTrue(entry.required_capabilities)
            self.assertTrue(entry.fallback_action)
            self.assertRegex(entry.risk_class, r"^R[0-3]$")

    def test_local_dispatch_returns_typed_unavailable_error_for_host_tool(self) -> None:
        from workflow_skill_router.bridge import serve
        from workflow_skill_router.local_control import LocalControlPlaneService
        from workflow_skill_router.tool_dispatch import ToolDispatcher

        with tempfile.TemporaryDirectory() as temporary:
            service = LocalControlPlaneService(Path(temporary) / "router.db")
            source = io.StringIO(json.dumps({
                "request_id": "r1",
                "tool": "get_next_work",
                "arguments": {
                    "context": {
                        "session_id": "session-1",
                        "actor": "developer",
                        "runtime_policy_snapshot_id": "policy-1",
                    },
                    "workflow_run_id": "workflow-1",
                },
            }) + "\n")
            output = io.StringIO()
            serve(source, output, ToolDispatcher(service))

        response = json.loads(output.getvalue())
        self.assertFalse(response["ok"])
        self.assertEqual("capability-unavailable", response["error"]["code"])
        self.assertEqual(
            "verified-host-required", response["error"]["availability"]
        )
        self.assertNotIn("traceback", output.getvalue().lower())

    def test_doctor_exposes_the_same_readiness_matrix(self) -> None:
        from workflow_skill_router.cli import main

        previous = sys.stdout
        output = io.StringIO()
        try:
            sys.stdout = output
            self.assertEqual(0, main(["doctor"]))
        finally:
            sys.stdout = previous
        document = json.loads(output.getvalue())
        self.assertEqual("bundled-local-r0", document["runtime_profile"])
        self.assertEqual("local-ready", document["tools"]["plan_work"]["availability"])
        self.assertEqual(
            "verified-host-required",
            document["tools"]["validate_route"]["availability"],
        )


if __name__ == "__main__":
    unittest.main()
