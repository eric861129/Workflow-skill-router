from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.service_models import (
    RequestContext, RouterStatusQuery, RuntimeContextSyncIntent,
)
try:
    from .support import build_router_service
except ImportError:
    from support import build_router_service


class ServiceAuthorityTests(unittest.TestCase):
    def test_request_context_actor_and_session_are_authorized_server_side(self):
        service = build_router_service()
        with self.assertRaisesRegex(PermissionError, "request-context-unverified"):
            service.get_router_status(RouterStatusQuery(
                RequestContext("session-other", "client", "runtime-policy-1"), None, None,
            ))

    def test_runtime_sync_intent_cannot_submit_runtime_authority_fields(self):
        self.assertEqual(
            {"host_snapshot_ref", "plugin_handshake_ref", "agent_runtime_snapshot"},
            set(RuntimeContextSyncIntent.__dataclass_fields__),
        )


if __name__ == "__main__": unittest.main()
