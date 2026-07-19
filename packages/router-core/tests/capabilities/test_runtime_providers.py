from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.capabilities.agent_runtime import (
    AgentCapabilityView,
    AgentRuntimeSnapshot,
    AgentRuntimeSnapshotProvider,
    decode_agent_runtime_snapshot,
)
from workflow_skill_router.capabilities.availability import derive_availability
from workflow_skill_router.capabilities.cache import CachedSnapshotProvider
from workflow_skill_router.capabilities.discovery import DiscoveryService
from workflow_skill_router.capabilities.models import (
    AuthState,
    Availability,
    CapabilityKind,
    Compatibility,
    Eligibility,
    Exposure,
    Presence,
    RiskLevel,
    TrustLevel,
)
from workflow_skill_router.capabilities.native_host import (
    NativeHostProvider,
    VerifiedHostCapability,
    VerifiedHostSnapshot,
)
from workflow_skill_router.capabilities.plugin_handshake import (
    PluginHandshakeProvider,
    VerifiedPluginHandshake,
    VerifiedToolDescriptor,
)
from workflow_skill_router.capabilities.providers import DiscoveryContext
from workflow_skill_router.schemas.errors import SchemaRegistryError


NOW = datetime(2026, 7, 15, tzinfo=timezone.utc)


def verified_host(exposure: Exposure) -> VerifiedHostSnapshot:
    return VerifiedHostSnapshot(
        revision="host@1",
        observed_at=NOW,
        capabilities=(
            VerifiedHostCapability(
                canonical_id="mcp-tool:workflow-skill-router/validate_route",
                kind=CapabilityKind.MCP_TOOL,
                display_name="Validate route",
                presence=Presence.PRESENT,
                exposure=exposure,
                auth_state=AuthState.NOT_REQUIRED,
                eligibility=Eligibility.ELIGIBLE,
                compatibility=Compatibility.COMPATIBLE,
                description="Host verified tool",
                aliases=(),
                content_digest="sha256:" + "a" * 64,
            ),
        ),
        receipt_digest="sha256:" + "b" * 64,
    )


def agent_snapshot(exposure: Exposure = Exposure.EXPOSED) -> AgentRuntimeSnapshot:
    return AgentRuntimeSnapshot(
        schema_id="workflow-skill-router/agent-runtime-snapshot",
        schema_version="2.0.0-alpha.1",
        artifact_kind="agent-runtime-snapshot",
        runtime_revision="agent@1",
        capabilities=(
            AgentCapabilityView(
                canonical_id="mcp-tool:workflow-skill-router/validate_route",
                kind="mcp-tool",
                display_name="Validate route",
                exposure=exposure.value,
                aliases=(),
            ),
        ),
    )


def previous_available_snapshot():
    return DiscoveryService(
        (NativeHostProvider.from_verified(verified_host(Exposure.EXPOSED)),),
        clock=lambda: NOW,
    ).discover(DiscoveryContext("runtime-a", "R1")).snapshot


class RuntimeProviderTests(unittest.TestCase):
    def test_host_not_exposed_beats_agent_and_cache_available(self) -> None:
        providers = (
            NativeHostProvider.from_verified(verified_host(Exposure.NOT_EXPOSED)),
            AgentRuntimeSnapshotProvider(agent_snapshot()),
            CachedSnapshotProvider(previous_available_snapshot()),
        )
        result = DiscoveryService(providers, clock=lambda: NOW).discover(
            DiscoveryContext("runtime-a", "R1")
        )
        capability = result.snapshot.capabilities[0]
        self.assertEqual(Exposure.NOT_EXPOSED, capability.exposure.value)
        self.assertNotEqual(
            Availability.AVAILABLE,
            derive_availability(capability, RiskLevel.R1, NOW).primary,
        )

    def test_plugin_handshake_fingerprints_schema_and_preserves_auth_required(self) -> None:
        handshake = VerifiedPluginHandshake(
            revision="plugin@1",
            observed_at=NOW,
            tools=(
                VerifiedToolDescriptor(
                    server_id="workflow-skill-router",
                    tool_name="validate_route",
                    display_name="Validate route",
                    schema={"type": "object", "required": ["route"]},
                    healthy=True,
                    auth_state=AuthState.REQUIRED,
                    aliases=(),
                ),
            ),
            receipt_digest="sha256:" + "c" * 64,
        )
        provider = PluginHandshakeProvider.from_verified(handshake)
        observation = provider.discover(DiscoveryContext("runtime-a", "R1")).observations[0]
        self.assertEqual(
            "mcp-tool:workflow-skill-router/validate_route",
            observation.canonical_id,
        )
        self.assertEqual(AuthState.REQUIRED, observation.fields["auth_state"].value)
        self.assertTrue(
            observation.fields["capability_fingerprint"].value.startswith("sha256:")
        )

    def test_agent_snapshot_never_claims_host_authorization(self) -> None:
        observation = AgentRuntimeSnapshotProvider(agent_snapshot(), clock=lambda: NOW).discover(
            DiscoveryContext("runtime-a", "R1")
        ).observations[0]
        self.assertEqual(AuthState.UNKNOWN, observation.fields["auth_state"].value)
        self.assertEqual(TrustLevel.RUNTIME, observation.fields["exposure"].trust_level)

    def test_agent_snapshot_strict_decoder_rejects_authority_fields(self) -> None:
        document = {
            "schema_id": "workflow-skill-router/agent-runtime-snapshot",
            "schema_version": "2.0.0-alpha.1",
            "artifact_kind": "agent-runtime-snapshot",
            "runtime_revision": "agent@1",
            "capabilities": [{
                "canonical_id": "mcp-tool:demo/tool",
                "kind": "mcp-tool",
                "display_name": "Demo",
                "exposure": "exposed",
                "aliases": [],
                "requested_auth_state": "authorized",
            }],
        }
        with self.assertRaisesRegex(SchemaRegistryError, "unknown field"):
            decode_agent_runtime_snapshot(document)

    def test_handshake_schema_change_changes_fingerprint(self) -> None:
        def fingerprint(required: list[str]) -> str:
            provider = PluginHandshakeProvider.from_verified(VerifiedPluginHandshake(
                revision="plugin@1",
                observed_at=NOW,
                tools=(VerifiedToolDescriptor(
                    server_id="demo",
                    tool_name="tool",
                    display_name="Demo",
                    schema={"type": "object", "required": required},
                    healthy=True,
                    auth_state=AuthState.NOT_REQUIRED,
                    aliases=(),
                ),),
                receipt_digest="sha256:" + "d" * 64,
            ))
            return provider.discover(
                DiscoveryContext("runtime-a", "R1")
            ).observations[0].fields["capability_fingerprint"].value

        self.assertNotEqual(fingerprint(["route"]), fingerprint(["route", "scope"]))


if __name__ == "__main__":
    unittest.main()
