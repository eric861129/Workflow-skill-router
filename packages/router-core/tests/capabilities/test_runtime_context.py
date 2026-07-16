from datetime import datetime, timezone
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.capabilities.availability import derive_availability
from workflow_skill_router.capabilities.models import Availability, Exposure, RiskLevel
from workflow_skill_router.capabilities.native_host import (
    HostReceiptVerificationError,
    VerifiedHostSnapshot,
)
from workflow_skill_router.capabilities.plugin_handshake import (
    PluginReceiptVerificationError,
    VerifiedPluginHandshake,
)
from workflow_skill_router.capabilities.runtime_context import (
    RuntimeContextService,
    RuntimeContextSyncRequest,
    RuntimeContextVerificationError,
    VerifiedRuntimeAuthority,
)

try:
    from .test_runtime_providers import (
        NOW,
        agent_snapshot,
        previous_available_snapshot,
        verified_host,
    )
except ImportError:
    from test_runtime_providers import (
        NOW,
        agent_snapshot,
        previous_available_snapshot,
        verified_host,
    )


class HostVerifier:
    def __init__(self, snapshots: dict[str, VerifiedHostSnapshot]) -> None:
        self._snapshots = snapshots

    def resolve(self, reference: str, session_id: str, receipt_digest: str):
        if session_id != "session-1" or receipt_digest != "sha256:" + "e" * 64:
            raise HostReceiptVerificationError("host_receipt_unverified")
        try:
            return self._snapshots[reference]
        except KeyError as error:
            raise HostReceiptVerificationError("host_receipt_unverified") from error


class HandshakeVerifier:
    def resolve(self, reference: str, session_id: str, receipt_digest: str):
        raise PluginReceiptVerificationError("plugin_receipt_unverified")


class BlockingHandshakeVerifier:
    def resolve(self, reference: str, session_id: str, receipt_digest: str):
        del reference, session_id, receipt_digest
        time.sleep(0.05)
        return VerifiedPluginHandshake("late", NOW, (), "sha256:" + "f" * 64)


class SnapshotReader:
    def __init__(self, snapshot=None) -> None:
        self._snapshot = snapshot

    def latest(self, runtime_fingerprint: str):
        del runtime_fingerprint
        return self._snapshot


def authority() -> VerifiedRuntimeAuthority:
    return VerifiedRuntimeAuthority(
        session_id="session-1",
        runtime_fingerprint="runtime-a",
        risk=RiskLevel.R1,
        runtime_policy_snapshot_id="policy-1",
        verification_receipt_digest="sha256:" + "e" * 64,
    )


def runtime_request(
    *,
    host_snapshot_ref: str | None = None,
    plugin_handshake_ref: str | None = None,
) -> RuntimeContextSyncRequest:
    return RuntimeContextSyncRequest(
        authority=authority(),
        host_snapshot_ref=host_snapshot_ref,
        plugin_handshake_ref=plugin_handshake_ref,
        agent_runtime_snapshot=agent_snapshot(),
    )


class RuntimeContextServiceTests(unittest.TestCase):
    def service(
        self,
        *,
        host_verifier=None,
        handshake_verifier=None,
        snapshot=None,
        provider_deadlines=None,
    ) -> RuntimeContextService:
        return RuntimeContextService(
            host_verifier=host_verifier or HostVerifier({}),
            handshake_verifier=handshake_verifier or HandshakeVerifier(),
            snapshot_reader=SnapshotReader(snapshot),
            filesystem_providers=(),
            provider_deadlines=provider_deadlines,
            clock=lambda: NOW,
        )

    def test_forged_host_payload_without_verified_reference_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            RuntimeContextVerificationError,
            "host_receipt_unverified",
        ):
            self.service().sync_verified(
                runtime_request(host_snapshot_ref="unregistered-host-receipt")
            )

    def test_provider_timeout_is_returned_and_snapshot_is_degraded(self) -> None:
        service = self.service(
            handshake_verifier=BlockingHandshakeVerifier(),
            provider_deadlines={"plugin-handshake": 0.005},
        )
        result = service.sync_verified(runtime_request(plugin_handshake_ref="hs-1"))
        self.assertTrue(result.degraded)
        failures = tuple(
            item for item in result.provider_failures
            if item.provider_id == "plugin-handshake"
        )
        self.assertEqual(1, len(failures))
        self.assertTrue(failures[0].timed_out)

    def test_cache_is_reported_but_cannot_promote_runtime_unavailable(self) -> None:
        host = verified_host(Exposure.NOT_EXPOSED)
        result = self.service(
            host_verifier=HostVerifier({"host-1": host}),
            snapshot=previous_available_snapshot(),
        ).sync_verified(runtime_request(host_snapshot_ref="host-1"))
        self.assertTrue(result.cache_used)
        availability = derive_availability(
            result.snapshot.capabilities[0],
            RiskLevel.R1,
            NOW,
        )
        self.assertNotEqual(Availability.AVAILABLE, availability.primary)


if __name__ == "__main__":
    unittest.main()
