from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.persistence.migrator import migrate
from workflow_skill_router.routing.leases import build_invocation_context
from workflow_skill_router.workflow.activation import (
    ActivationPreflightError, ActivationPreflightService, HostActivationReceipt,
    InstructionContentHandle, SQLiteLeaseActivationRepository,
)

try:
    from ..routing.test_route_validator import ACTION_DIGEST, SKILL, RouteValidatorTests
except ImportError:
    from routing.test_route_validator import ACTION_DIGEST, SKILL, RouteValidatorTests


NOW = datetime(2026, 7, 15, tzinfo=timezone.utc)


class ContentResolver:
    def __init__(self, data): self.data = data; self.opens = []
    def open_stable(self, capability_id):
        self.opens.append(capability_id)
        return InstructionContentHandle(capability_id, self.data, "file-id-1")


class Consumer:
    def __init__(self): self.payloads = []
    def consume(self, handle):
        self.payloads.append(handle.bound_bytes)
        return HostActivationReceipt(
            handle.reservation_digest, handle.lease_id, handle.capability_id,
            handle.action_digest, handle.binding_digest, "sha256:" + "f" * 64,
        )


class ActivationContentTests(unittest.TestCase):
    def setUp(self):
        route_test = RouteValidatorTests("test_hybrid_lease_is_single_use_and_requires_bound_content_preflight")
        route_test.setUp()
        self.lease = route_test.valid_result().lease
        self.directory = tempfile.TemporaryDirectory()
        database = Path(self.directory.name) / "router.db"
        migrate(database)
        self.repository = SQLiteLeaseActivationRepository(database, clock=lambda: NOW)
        self.context = build_invocation_context(
            self.lease.scope_anchor_id, "implement", "user-1", "session-1", "policy-1",
        )

    def tearDown(self): self.directory.cleanup()

    def service(self, resolver, consumer=None):
        return ActivationPreflightService(
            self.repository,
            instruction_content_resolver=resolver,
            runtime_contract_resolver=None,
            bound_capability_consumer=consumer,
        )

    def test_body_change_before_preflight_fails_without_reservation(self):
        resolver = ContentResolver(b"changed")
        with self.assertRaisesRegex(ActivationPreflightError, "binding-digest-mismatch"):
            self.service(resolver).bind_single_use(
                self.lease, "skill:x", SKILL.capability_fingerprint, ACTION_DIGEST,
                None, 1, self.context, "nonce-1", NOW,
            )
        self.assertEqual(0, self.repository.consumption_count())

    def test_same_bound_bytes_reach_host_and_handle_cannot_reuse(self):
        # Native host 測試資料使用已驗證的內容摘要作為綁定值，無法反推出原始內容；
        # 因此將 lease 副本綁定到實際測試位元組，以驗證啟用時使用的是同一份內容。
        import hashlib
        from dataclasses import replace
        data = "繁體中文技能內容".encode()
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        capability = replace(
            self.lease.allowed_capabilities[0],
            activation_binding=replace(
                self.lease.allowed_capabilities[0].activation_binding,
                trusted_digest=digest,
            ),
        )
        lease = replace(self.lease, allowed_capabilities=(capability,))
        consumer = Consumer()
        service = self.service(ContentResolver(data), consumer)
        handle = service.bind_single_use(
            lease, "skill:x", SKILL.capability_fingerprint, ACTION_DIGEST,
            None, 1, self.context, "nonce-1", NOW,
        )
        receipt = service.consume_bound(handle)
        self.assertEqual([data], consumer.payloads)
        self.assertEqual(handle.reservation_digest, receipt.reservation_digest)
        with self.assertRaisesRegex(ActivationPreflightError, "handle-consumed"):
            service.consume_bound(handle)

    def test_missing_content_support_prevents_hybrid_activation(self):
        with self.assertRaisesRegex(ActivationPreflightError, "content-preflight-unavailable"):
            ActivationPreflightService(
                self.repository,
                instruction_content_resolver=None,
                runtime_contract_resolver=None,
                bound_capability_consumer=None,
            ).bind_single_use(
                self.lease, "skill:x", SKILL.capability_fingerprint, ACTION_DIGEST,
                None, 1, self.context, "nonce-1", NOW,
            )


if __name__ == "__main__": unittest.main()
