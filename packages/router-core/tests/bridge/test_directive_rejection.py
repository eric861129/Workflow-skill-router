import io
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.bridge import serve  # noqa: E402
from workflow_skill_router.routing.directives import DirectiveAmbiguityError  # noqa: E402


class RejectingDispatcher:
    def __init__(self, reason: str | None) -> None:
        self.reason = reason

    def dispatch(self, tool, arguments):
        raise DirectiveAmbiguityError("explicit SKILL 識別碼必須是 skill:<name>", reason=self.reason)


class DirectiveRejectionBridgeTests(unittest.TestCase):
    def serve(self, reason: str | None) -> tuple[dict, str]:
        output = io.StringIO()
        diagnostics = io.StringIO()
        request = {"request_id": "r1", "tool": "plan_work", "arguments": {"explicit_skill_ids": ["Bad Name"]}}
        serve(io.StringIO(json.dumps(request) + "\n"), output, RejectingDispatcher(reason), diagnostics)
        return json.loads(output.getvalue()), diagnostics.getvalue()

    def test_directive_rejection_is_public_invalid_arguments_with_its_reason(self) -> None:
        response, diagnostics = self.serve("explicit-skill-id-not-canonical")

        self.assertFalse(response["ok"])
        self.assertEqual(
            {"code": "invalid-arguments", "message": "explicit-skill-id-not-canonical"},
            response["error"],
        )
        # The user's input never travels back, and a client error is not an internal failure.
        self.assertNotIn("Bad Name", json.dumps(response))
        self.assertNotIn("internal-error", json.dumps(response))
        self.assertEqual("", diagnostics)

    def test_directive_rejection_without_a_specific_reason_uses_the_default(self) -> None:
        response, _ = self.serve(None)
        self.assertEqual("directive-ambiguous", response["error"]["message"])


if __name__ == "__main__":
    unittest.main()
