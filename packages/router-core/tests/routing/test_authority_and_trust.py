from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.capabilities.discovery import DiscoveryService
from workflow_skill_router.capabilities.models import (
    AuthState,
    CapabilityKind,
    Compatibility,
    Eligibility,
    Exposure,
    Presence,
    Requirement,
    SideEffect,
)
from workflow_skill_router.capabilities.native_host import (
    NativeHostProvider,
    VerifiedHostCapability,
    VerifiedHostSnapshot,
)
from workflow_skill_router.capabilities.providers import DiscoveryContext
from workflow_skill_router.routing.authority import (
    AuthenticatedContext,
    AuthorityResolver,
    RuntimePolicySnapshot,
    SelectionOrigin,
    VerifiedDirectiveEvent,
)
from workflow_skill_router.routing.scope import ScopeIndex, create_scope_anchor, descendant_anchor
from workflow_skill_router.routing.models import ScopeKind
from workflow_skill_router.routing.trust import RequirementTrustPolicy, assess_requirement


NOW = datetime(2026, 7, 15, tzinfo=timezone.utc)


def snapshot():
    host = VerifiedHostSnapshot(
        "host@1",
        NOW,
        (
            VerifiedHostCapability(
                "skill:x", CapabilityKind.SKILL, "X", Presence.PRESENT,
                Exposure.EXPOSED, AuthState.NOT_REQUIRED, Eligibility.ELIGIBLE,
                Compatibility.COMPATIBLE, "Primary", (), "sha256:" + "a" * 64,
            ),
            VerifiedHostCapability(
                "skill:y", CapabilityKind.SKILL, "Y", Presence.PRESENT,
                Exposure.EXPOSED, AuthState.NOT_REQUIRED, Eligibility.ELIGIBLE,
                Compatibility.COMPATIBLE, "Support", (), "sha256:" + "b" * 64,
            ),
            VerifiedHostCapability(
                "plugin:remote/publisher", CapabilityKind.PLUGIN, "Publisher",
                Presence.PRESENT, Exposure.EXPOSED, AuthState.AUTHORIZED,
                Eligibility.ELIGIBLE, Compatibility.COMPATIBLE, "Remote", (),
                "sha256:" + "c" * 64,
            ),
        ),
        "sha256:" + "d" * 64,
    )
    found = DiscoveryService(
        (NativeHostProvider.from_verified(host),),
        clock=lambda: NOW,
    ).discover(DiscoveryContext("runtime-a", "R1")).snapshot
    capabilities = tuple(
        replace(item, side_effect=SideEffect.REMOTE)
        if item.canonical_id == "plugin:remote/publisher"
        else item
        for item in found.capabilities
    )
    return replace(found, capabilities=capabilities)


class AuthorityAndTrustTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = create_scope_anchor(
            ScopeKind.WORKFLOW, "workflow-1", None, "objective", 1,
        )
        self.phase = descendant_anchor(
            self.workflow, ScopeKind.PHASE, "phase-1", "implement", 1,
        )
        self.other = create_scope_anchor(
            ScopeKind.WORKFLOW, "workflow-2", None, "objective", 1,
        )
        self.index = ScopeIndex((self.workflow, self.phase, self.other))
        self.directive = VerifiedDirectiveEvent(
            event_id="directive-1",
            capability_id="skill:x",
            purpose="implement",
            scope_anchor_id=self.workflow.scope_anchor_id,
            policy_snapshot_id="policy-1",
            actor="user-1",
            session_id="session-1",
            directive_digest="sha256:" + "e" * 64,
        )
        self.resolver = AuthorityResolver(
            RuntimePolicySnapshot("policy-1", "sha256:" + "f" * 64, ()),
            (self.directive,),
            AuthenticatedContext("user-1", "session-1"),
            self.index,
        )
        self.snapshot = snapshot()
        self.trust_policy = RequirementTrustPolicy(
            base_runtime_ids=(),
            allowed_non_skill_kinds=(CapabilityKind.PLUGIN, CapabilityKind.MCP_TOOL),
            trusted_provider_ids=("native-host", "plugin-handshake"),
            allowed_purposes=("publish", "implement"),
        )

    def test_client_cannot_self_declare_system_required(self) -> None:
        result = self.resolver.resolve(
            SelectionOrigin.SYSTEM_REQUIRED,
            "missing",
            capability_id="skill:x",
            purpose="implement",
            scope_anchor_id=self.phase.scope_anchor_id,
        )
        self.assertEqual(SelectionOrigin.ROUTER_RECOMMENDED, result.selection_origin)
        self.assertTrue(result.requires_consent)

    def test_verified_user_directive_produces_user_explicit_origin(self) -> None:
        result = self.resolver.resolve(
            SelectionOrigin.USER_EXPLICIT,
            self.directive.event_id,
            capability_id="skill:x",
            purpose="implement",
            scope_anchor_id=self.phase.scope_anchor_id,
            directive_event=self.directive,
        )
        self.assertEqual(SelectionOrigin.USER_EXPLICIT, result.selection_origin)
        self.assertFalse(result.requires_consent)

    def test_verified_directive_cannot_be_replayed_for_another_capability_or_scope(self) -> None:
        replayed = self.resolver.resolve(
            SelectionOrigin.USER_EXPLICIT,
            self.directive.event_id,
            capability_id="skill:y",
            purpose="implement",
            scope_anchor_id=self.other.scope_anchor_id,
            directive_event=self.directive,
        )
        self.assertEqual(SelectionOrigin.ROUTER_RECOMMENDED, replayed.selection_origin)
        self.assertTrue(replayed.requires_consent)

    def test_workflow_directive_inherits_only_to_validated_descendant_phase(self) -> None:
        inherited = self.resolver.resolve(
            SelectionOrigin.USER_EXPLICIT,
            self.directive.event_id,
            capability_id="skill:x",
            purpose="implement",
            scope_anchor_id=self.phase.scope_anchor_id,
            directive_event=self.directive,
        )
        sibling = self.resolver.resolve(
            SelectionOrigin.USER_EXPLICIT,
            self.directive.event_id,
            capability_id="skill:x",
            purpose="implement",
            scope_anchor_id=self.other.scope_anchor_id,
            directive_event=self.directive,
        )
        self.assertEqual(SelectionOrigin.USER_EXPLICIT, inherited.selection_origin)
        self.assertEqual(SelectionOrigin.ROUTER_RECOMMENDED, sibling.selection_origin)

    def test_skill_requirement_never_bypasses_explicit_lock(self) -> None:
        requirement = Requirement("skill:y", CapabilityKind.SKILL, "implement", True)
        decision = assess_requirement(
            requirement,
            parent_skill="skill:x",
            snapshot=self.snapshot,
            policy=self.trust_policy,
        )
        self.assertFalse(decision.trusted_as_base_requirement)
        self.assertTrue(decision.requires_support_consent)

    def test_remote_plugin_requirement_needs_capability_consent_and_runtime_approval(self) -> None:
        requirement = Requirement(
            "plugin:remote/publisher",
            CapabilityKind.PLUGIN,
            "publish",
            True,
        )
        decision = assess_requirement(
            requirement,
            "skill:x",
            self.snapshot,
            self.trust_policy,
        )
        self.assertTrue(decision.requires_capability_consent)
        self.assertTrue(decision.requires_runtime_approval)


if __name__ == "__main__":
    unittest.main()
