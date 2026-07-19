import io
import json
import unittest

from workflow_skill_router.bridge import serve
from workflow_skill_router.runtime_readiness import CapabilityUnavailable


class FakeDispatcher:
    def __init__(self): self.calls = 0
    def dispatch(self, tool, arguments):
        self.calls += 1; return {"sequence": self.calls, "arguments": arguments}


class UnavailableDispatcher:
    def dispatch(self, tool, arguments):
        del tool, arguments
        raise CapabilityUnavailable.for_tool("get_next_work")


class BridgeTests(unittest.TestCase):
    def test_two_requests_share_one_dispatcher(self):
        source = io.StringIO('{"request_id":"r1","tool":"get_router_status","arguments":{}}\n'
                             '{"request_id":"r2","tool":"get_router_status","arguments":{}}\n')
        output = io.StringIO(); serve(source, output, FakeDispatcher())
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([1, 2], [row["result"]["sequence"] for row in rows])

    def test_unknown_tool_does_not_echo_secret(self):
        output = io.StringIO()
        serve(io.StringIO('{"request_id":"r1","tool":"raw_append","arguments":{"token":"secret"}}\n'), output, FakeDispatcher())
        self.assertEqual("unknown-tool", json.loads(output.getvalue())["error"]["code"])
        self.assertNotIn("secret", output.getvalue())

    def test_known_unavailable_capability_returns_public_safe_requirement(self):
        source = io.StringIO(
            '{"request_id":"r1","tool":"get_next_work","arguments":{}}\n'
        )
        output = io.StringIO()
        diagnostics = io.StringIO()
        serve(source, output, UnavailableDispatcher(), diagnostics)
        response = json.loads(output.getvalue())
        self.assertEqual("capability-unavailable", response["error"]["code"])
        self.assertEqual(
            "verified-host-required", response["error"]["availability"]
        )
        self.assertEqual("", diagnostics.getvalue())


if __name__ == "__main__": unittest.main()
