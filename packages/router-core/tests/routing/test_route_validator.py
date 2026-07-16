from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.capabilities.discovery import DiscoveryService
from workflow_skill_router.capabilities.models import (
    AuthState, Availability, CapabilityKind, Compatibility, Eligibility,
    Exposure, Freshness, Presence, RiskLevel,
)
from workflow_skill_router.capabilities.native_host import (
    NativeHostProvider, VerifiedHostCapability, VerifiedHostSnapshot,
)
from workflow_skill_router.capabilities.plugin_handshake import (
    PluginHandshakeProvider, VerifiedPluginHandshake, VerifiedToolDescriptor,
)
from workflow_skill_router.capabilities.providers import DiscoveryContext
from workflow_skill_router.routing.authority import SelectionOrigin
from workflow_skill_router.routing.leases import (
    InMemoryLeaseConsumptionPort,
    build_invocation_context,
    validate_invocation,
)
from workflow_skill_router.routing.models import (
    CapabilitySelection, OutcomeMode, RouteValidationRequest, RoutingEnvelope,
    RuntimeMode, ScopeKind, SelectionMode, SkillSelectionPolicy, SupportPolicy,
    ValidationContext, VerifiedRuntimeApproval,
)
from workflow_skill_router.routing.validator import RouteValidator


NOW = datetime(2026, 7, 15, tzinfo=timezone.utc)
ACTION_DIGEST = "sha256:" + "1" * 64
POLICY_DIGEST = "sha256:" + "2" * 64
CONTENT_POLICY_DIGEST = "sha256:" + "3" * 64


def capability_snapshot():
    host = VerifiedHostSnapshot(
        "host@1", NOW,
        (
            VerifiedHostCapability(
                "skill:x", CapabilityKind.SKILL, "X", Presence.PRESENT,
                Exposure.EXPOSED, AuthState.NOT_REQUIRED, Eligibility.ELIGIBLE,
                Compatibility.COMPATIBLE, "Primary", (), "sha256:" + "a" * 64,
            ),
            VerifiedHostCapability(
                "skill:y", CapabilityKind.SKILL, "Y", Presence.PRESENT,
                Exposure.EXPOSED, AuthState.NOT_REQUIRED, Eligibility.ELIGIBLE,
                Compatibility.COMPATIBLE, "Support", (), "sha256:" + "e" * 64,
            ),
            VerifiedHostCapability(
                "mcp-tool:demo/validate", CapabilityKind.MCP_TOOL, "Validate",
                Presence.PRESENT, Exposure.EXPOSED, AuthState.NOT_REQUIRED,
                Eligibility.ELIGIBLE, Compatibility.COMPATIBLE, "Tool", (),
                "sha256:" + "d" * 64,
            ),
        ),
        "sha256:" + "b" * 64,
    )
    plugin = VerifiedPluginHandshake(
        "plugin@1", NOW,
        (VerifiedToolDescriptor(
            "demo", "validate", "Validate", {"type": "object"}, True,
            AuthState.NOT_REQUIRED, (),
        ),),
        "sha256:" + "c" * 64,
    )
    return DiscoveryService(
        (
            NativeHostProvider.from_verified(host),
            PluginHandshakeProvider.from_verified(plugin),
        ),
        clock=lambda: NOW,
    ).discover(DiscoveryContext("runtime-a", "R1")).snapshot


SNAPSHOT = capability_snapshot()
SKILL = next(item for item in SNAPSHOT.capabilities if item.canonical_id == "skill:x")
SKILL_Y = next(item for item in SNAPSHOT.capabilities if item.canonical_id == "skill:y")
MCP = next(item for item in SNAPSHOT.capabilities if item.kind is CapabilityKind.MCP_TOOL)


def selection(capability=SKILL, *, origin=SelectionOrigin.USER_EXPLICIT, consent=None):
    return CapabilitySelection(
        capability.canonical_id,
        capability.capability_fingerprint,
        origin,
        "directive-1" if origin is SelectionOrigin.USER_EXPLICIT else "router-derived",
        POLICY_DIGEST,
        "implement",
        consent,
    )


def auto_policy() -> SkillSelectionPolicy:
    return SkillSelectionPolicy(
        SelectionMode.AUTO, (), None, SupportPolicy.ASK, (), (), ScopeKind.PHASE,
        ScopeKind.PHASE, "scope:phase-1", 1,
    )


def approval() -> VerifiedRuntimeApproval:
    return VerifiedRuntimeApproval(
        "approval-1", "scope-digest-1", ACTION_DIGEST, NOW + timedelta(minutes=4),
    )


def context(*, include_content=True, include_tool=True, runtime_approval=None):
    return ValidationContext(
        now=NOW,
        runtime_mode=RuntimeMode.HYBRID,
        runtime_policy_snapshot_id="policy-1",
        runtime_policy_digest=POLICY_DIGEST,
        actor="user-1",
        session_id="session-1",
        verified_authority_refs=("directive-1",),
        consent_grant_refs=(),
        runtime_approval=runtime_approval,
        instruction_content_bindings=(
            tuple(
                (item.canonical_id, item.installer_content_digest.value)
                for item in (SKILL, SKILL_Y)
            )
            if include_content else ()
        ),
        runtime_contract_bindings=(
            ((MCP.canonical_id, "tool-schema", MCP.capability_fingerprint),)
            if include_tool else ()
        ),
        content_preflight_policy_digest=CONTENT_POLICY_DIGEST,
        allowed_availability=(Availability.AVAILABLE, Availability.DEGRADED, Availability.STALE),
    )


def request_for(
    capability_id="skill:x",
    *,
    capability=SKILL,
    risk=RiskLevel.R1,
    action_digest=ACTION_DIGEST,
    primary=None,
):
    chosen = primary or (
        selection(capability)
        if capability_id == capability.canonical_id
        else replace(selection(capability), capability_id=capability_id)
    )
    return RouteValidationRequest(
        route_id="route-1",
        workflow_run_id="workflow-1",
        work_item_id="work-1",
        phase_id="phase-1",
        scope_anchor_id="scope:phase-1",
        envelope=RoutingEnvelope.SINGLE,
        capability_snapshot_id=SNAPSHOT.snapshot_id,
        primary_selection=chosen,
        support_selections=(),
        explicit_skill_dispositions=(),
        explicit_skill_coverage_ref=None,
        consent_grant_refs=(),
        risk=risk,
        action_digest=action_digest,
        state_version=1,
        purpose="implement",
        outcome_mode=OutcomeMode.COMPLETE,
        exit_gate=None,
    )


class RouteValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = RouteValidator()
        self.consumptions = InMemoryLeaseConsumptionPort(clock=lambda: NOW)

    def valid_result(self):
        return self.validator.validate(
            request_for(), SNAPSHOT, auto_policy(), context(include_content=True),
        )

    def test_unavailable_capability_never_receives_lease(self) -> None:
        result = self.validator.validate(
            request_for("skill:missing"), SNAPSHOT, auto_policy(), context(),
        )
        self.assertFalse(result.valid)
        self.assertIsNone(result.lease)

    def test_r3_requires_fresh_snapshot_runtime_approval_and_action_digest(self) -> None:
        stale = replace(SNAPSHOT, freshness=Freshness(NOW, NOW, False, True))
        request = request_for(risk=RiskLevel.R3, action_digest="")
        result = self.validator.validate(request, stale, auto_policy(), context())
        self.assertEqual(
            {"snapshot-stale", "runtime-approval-required", "action-digest-required"},
            {item.code for item in result.violations},
        )

    def test_expired_lease_cannot_authorize_new_invocation(self) -> None:
        lease = replace(self.valid_result().lease, expires_at="2026-07-14T00:00:00Z")
        invocation_context = build_invocation_context(
            lease.scope_anchor_id, "implement", "user-1", "session-1", "policy-1",
        )
        decision = validate_invocation(
            lease, SKILL.canonical_id, SKILL.capability_fingerprint, ACTION_DIGEST,
            None, SKILL.installer_content_digest.value, 1, NOW,
            invocation_context=invocation_context,
            invocation_nonce="invocation-expired",
            consumption_port=self.consumptions,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual("lease-expired", decision.reason)

    def test_invocation_binds_action_content_and_consumes_once(self) -> None:
        lease = self.valid_result().lease
        invocation_context = build_invocation_context(
            lease.scope_anchor_id, "implement", "user-1", "session-1", "policy-1",
        )
        args = (
            lease, SKILL.canonical_id, SKILL.capability_fingerprint, ACTION_DIGEST,
            None, SKILL.installer_content_digest.value, 1, NOW,
        )
        first = validate_invocation(
            *args, invocation_context=invocation_context, invocation_nonce="invocation-1",
            consumption_port=self.consumptions,
        )
        second = validate_invocation(
            *args, invocation_context=invocation_context, invocation_nonce="invocation-2",
            consumption_port=self.consumptions,
        )
        self.assertTrue(first.allowed)
        self.assertEqual("lease-consumed", second.reason)

    def test_concurrent_lease_consumption_allows_exactly_one_invocation(self) -> None:
        lease = self.valid_result().lease
        invocation_context = build_invocation_context(
            lease.scope_anchor_id, "implement", "user-1", "session-1", "policy-1",
        )
        def invoke(nonce):
            return validate_invocation(
                lease, SKILL.canonical_id, SKILL.capability_fingerprint, ACTION_DIGEST,
                None, SKILL.installer_content_digest.value, 1, NOW,
                invocation_context=invocation_context, invocation_nonce=nonce,
                consumption_port=self.consumptions,
            )
        with ThreadPoolExecutor(max_workers=2) as executor:
            decisions = tuple(executor.map(invoke, ("one", "two")))
        self.assertEqual(1, sum(item.allowed for item in decisions))
        self.assertEqual(1, sum(item.reason == "lease-consumed" for item in decisions))

    def test_lease_cannot_replay_across_purpose_or_scope(self) -> None:
        lease = self.valid_result().lease
        for invocation_context in (
            build_invocation_context(lease.scope_anchor_id, "publish", "user-1", "session-1", "policy-1"),
            build_invocation_context("scope:other", "implement", "user-1", "session-1", "policy-1"),
        ):
            with self.subTest(invocation_context=invocation_context):
                decision = validate_invocation(
                    lease, SKILL.canonical_id, SKILL.capability_fingerprint, ACTION_DIGEST,
                    None, SKILL.installer_content_digest.value, 1, NOW,
                    invocation_context=invocation_context, invocation_nonce="replay",
                    consumption_port=InMemoryLeaseConsumptionPort(clock=lambda: NOW),
                )
                self.assertFalse(decision.allowed)
                self.assertEqual("invocation-context-mismatch", decision.reason)

    def test_hybrid_lease_is_single_use_and_requires_bound_content_preflight(self) -> None:
        result = self.valid_result()
        self.assertTrue(result.valid)
        self.assertEqual((1, "single-use-preflight"), (result.lease.max_activations, result.lease.activation_mode))
        self.assertEqual("instruction-content", result.lease.allowed_capabilities[0].activation_binding.kind)
        missing = self.validator.validate(
            request_for(), SNAPSHOT, auto_policy(), context(include_content=False),
        )
        self.assertIn("content-preflight-unavailable", {item.code for item in missing.violations})

    def test_non_skill_lease_uses_verified_runtime_binding_without_opening_skill_body(self) -> None:
        request = request_for(
            MCP.canonical_id,
            capability=MCP,
            primary=replace(selection(MCP), purpose="implement"),
        )
        validation_context = context(include_content=False, include_tool=True)
        result = self.validator.validate(request, SNAPSHOT, auto_policy(), validation_context)
        self.assertTrue(result.valid)
        binding = result.lease.allowed_capabilities[0].activation_binding
        self.assertEqual("tool-schema", binding.kind)
        self.assertEqual(MCP.capability_fingerprint, binding.trusted_digest)
        self.assertEqual([], validation_context.instruction_body_opens)

    def test_skill_only_fallback_is_valid_but_never_receives_hybrid_lease(self) -> None:
        fallback_context = replace(
            context(include_content=False),
            runtime_mode=RuntimeMode.SKILL_ONLY,
        )
        result = self.validator.validate(
            request_for(), SNAPSHOT, auto_policy(), fallback_context,
        )
        self.assertTrue(result.valid)
        self.assertIsNone(result.lease)


if __name__ == "__main__":
    unittest.main()
