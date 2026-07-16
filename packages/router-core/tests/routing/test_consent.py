from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.capabilities.models import CapabilityKind
from workflow_skill_router.routing.consent import (
    ConsentPolicyError,
    match_grant,
    may_reask_after_rejection,
    propose_support,
    validate_support_selection,
)
from workflow_skill_router.routing.models import (
    ConsentGrant,
    ConsentRejection,
    ScopeKind,
    SupportPolicy,
    SupportProposal,
)
from workflow_skill_router.routing.scope import ScopeIndex, create_scope_anchor, descendant_anchor


NOW = datetime(2026, 7, 15, tzinfo=timezone.utc)


class ConsentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = create_scope_anchor(
            ScopeKind.WORKFLOW, "workflow-1", None, "objective", 1,
        )
        self.phase_a = descendant_anchor(
            self.workflow, ScopeKind.PHASE, "phase-a", "api", 1,
        )
        self.phase_b = descendant_anchor(
            self.workflow, ScopeKind.PHASE, "phase-b", "docs", 1,
        )
        self.index = ScopeIndex((self.workflow, self.phase_a, self.phase_b))

    def proposal(
        self,
        skill: str = "skill:support",
        *,
        anchor_id: str | None = None,
        context: str = "ctx-1",
        phase_id: str = "phase-a",
    ) -> SupportProposal:
        return SupportProposal(
            proposal_id=f"proposal:{skill}",
            capability_id=skill,
            capability_fingerprint="sha256:" + "a" * 64,
            capability_kind=CapabilityKind.SKILL,
            purpose="review",
            role="router-recommended",
            scope=ScopeKind.PHASE,
            scope_anchor_id=anchor_id or self.phase_a.scope_anchor_id,
            work_item_id="work-1",
            phase_id=phase_id,
            goal_binding_id="goal-1",
            goal_revision=1,
            plan_revision=1,
            context_fingerprint=context,
            actor="router",
            created_at=NOW,
        )

    def grant(
        self,
        *,
        scope: ScopeKind = ScopeKind.PHASE,
        anchor_id: str | None = None,
        context: str = "ctx-1",
    ) -> ConsentGrant:
        proposal = self.proposal(anchor_id=anchor_id, context=context)
        return ConsentGrant.from_proposal(
            proposal,
            grant_id="grant-1",
            scope=scope,
            scope_anchor_id=anchor_id or self.phase_a.scope_anchor_id,
            actor="user",
            granted_at=NOW,
            expires_at=NOW + timedelta(hours=1),
        )

    def rejection(
        self,
        *,
        context: str = "ctx-1",
        phase_id: str = "phase-old",
    ) -> ConsentRejection:
        return ConsentRejection.from_proposal(
            self.proposal(context=context, phase_id=phase_id),
            rejection_id="reject-1",
            actor="user",
            rejected_at=NOW,
        )

    def test_proposal_is_limited_to_three_distinct_support_skills(self) -> None:
        with self.assertRaisesRegex(ConsentPolicyError, "最多三個"):
            propose_support(
                self.phase_a,
                tuple(self.proposal(f"skill:{name}") for name in "abcd"),
            )

    def test_phase_grant_does_not_apply_to_sibling_phase(self) -> None:
        grant = self.grant()
        self.assertTrue(match_grant(grant, self.proposal(), self.index, NOW))
        sibling = self.proposal(anchor_id=self.phase_b.scope_anchor_id, phase_id="phase-b")
        self.assertFalse(match_grant(grant, sibling, self.index, NOW))

    def test_explicit_workflow_grant_applies_to_descendant_phase(self) -> None:
        grant = self.grant(
            scope=ScopeKind.WORKFLOW,
            anchor_id=self.workflow.scope_anchor_id,
        )
        request = self.proposal(anchor_id=self.phase_a.scope_anchor_id)
        self.assertTrue(match_grant(grant, request, self.index, NOW))

    def test_same_rejection_cannot_be_reasked_after_phase_id_replacement(self) -> None:
        rejection = self.rejection()
        request = self.proposal(context="ctx-1", phase_id="phase-new")
        self.assertFalse(may_reask_after_rejection(rejection, request))

    def test_material_context_change_allows_explained_reproposal(self) -> None:
        self.assertTrue(may_reask_after_rejection(
            self.rejection(context="ctx-old"),
            self.proposal(context="ctx-new"),
        ))

    def test_forbid_policy_never_creates_support_prompt(self) -> None:
        decision = validate_support_selection(
            self.proposal(),
            SupportPolicy.FORBID,
            (),
            (),
            self.index,
            NOW,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual("support-forbidden", decision.code)
        self.assertFalse(decision.should_prompt)

    def test_auto_policy_selects_support_without_prompt_or_grant(self) -> None:
        decision = validate_support_selection(
            self.proposal(),
            SupportPolicy.AUTO,
            (),
            (),
            self.index,
            NOW,
        )
        self.assertTrue(decision.allowed)
        self.assertEqual("support-auto-selected", decision.code)
        self.assertIsNone(decision.grant_ref)
        self.assertFalse(decision.should_prompt)


if __name__ == "__main__":
    unittest.main()
