from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.routing.authority import SelectionOrigin
from workflow_skill_router.routing.consent import (
    match_grant, may_reask_after_rejection, validate_support_selection,
)
from workflow_skill_router.routing.coverage import evaluate_explicit_coverage
from workflow_skill_router.routing.directives import resolve_directive
from workflow_skill_router.routing.models import (
    ConsentGrant, ConsentRejection, CoverageStatus, DirectiveInput,
    ExplicitSemantics, ExplicitSkillDisposition, GoalRelation, OutcomeMode,
    RoutingEnvelope, RuntimeMode, ScopeKind, SelectionMode, SkillDisposition,
    SkillSelectionPolicy, SupportPolicy, SupportProposal, TaskSignals,
)
from workflow_skill_router.routing.profiler import decide_request
from workflow_skill_router.routing.scope import (
    ScopeIndex, create_scope_anchor, descendant_anchor, inherit_explicit_policy,
    replacement_anchor,
)
from workflow_skill_router.routing.validator import RouteValidator

try:
    from .test_route_validator import (
        NOW, POLICY_DIGEST, SKILL, SKILL_Y, SNAPSHOT, auto_policy, context,
        request_for, selection,
    )
except ImportError:
    from test_route_validator import (
        NOW, POLICY_DIGEST, SKILL, SKILL_Y, SNAPSHOT, auto_policy, context,
        request_for, selection,
    )


def disposition(scope: str, skill: str, value=SkillDisposition.ACTIVE_PRIMARY):
    return ExplicitSkillDisposition(skill, scope, value, "route", "scenario")


def explicit_policy(
    scope: str,
    semantics=ExplicitSemantics.PREFERRED_PRIMARY,
    support=SupportPolicy.ASK,
    skills=("skill:x",),
):
    return SkillSelectionPolicy(
        SelectionMode.EXPLICIT_LOCKED, tuple(skills), semantics, support, (), (),
        ScopeKind.PHASE, ScopeKind.WORKFLOW, scope, 1,
    )


def proposal(anchor_id: str, phase_id: str = "phase-1") -> SupportProposal:
    return SupportProposal(
        "proposal-y", "skill:y", SKILL_Y.capability_fingerprint, SKILL_Y.kind,
        "implement", "router-recommended", ScopeKind.PHASE, anchor_id, "work-1",
        phase_id, "goal-1", 1, 1, "context-1", "router", NOW,
    )


class ExplicitSkillScenarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = RouteValidator()
        self.workflow = create_scope_anchor(
            ScopeKind.WORKFLOW, "workflow-1", None, "objective", 1,
        )
        self.phase_one = descendant_anchor(
            self.workflow, ScopeKind.PHASE, "phase-1", "implement", 1,
        )
        self.phase_two = descendant_anchor(
            self.workflow, ScopeKind.PHASE, "phase-2", "verify", 1,
        )
        self.index = ScopeIndex((self.workflow, self.phase_one, self.phase_two))

    def explicit_request(
        self,
        *,
        envelope=RoutingEnvelope.SINGLE,
        support=(),
        outcome=OutcomeMode.COMPLETE,
        exit_gate=None,
        scope=None,
        phase_id="phase-1",
        dispositions=None,
        coverage_ref="coverage-1",
    ):
        scope_id = scope or self.phase_one.scope_anchor_id
        request = request_for(primary=selection(SKILL))
        return replace(
            request,
            envelope=envelope,
            scope_anchor_id=scope_id,
            phase_id=phase_id,
            support_selections=tuple(support),
            explicit_skill_dispositions=(
                tuple(dispositions)
                if dispositions is not None
                else (disposition(scope_id, "skill:x"),)
            ),
            explicit_skill_coverage_ref=coverage_ref,
            consent_grant_refs=tuple(
                item.consent_grant_ref for item in support
                if item.consent_grant_ref is not None
            ),
            outcome_mode=outcome,
            exit_gate=exit_gate,
        )

    def test_small_auto_is_single_with_one_minimal_primary(self) -> None:
        profile = decide_request(
            GoalRelation.NONE, TaskSignals.small(),
            resolve_directive(DirectiveInput("實作功能")), RuntimeMode.HYBRID,
        )
        result = self.validator.validate(
            request_for(), SNAPSHOT, auto_policy(), context(),
        )
        self.assertEqual(RoutingEnvelope.SINGLE, profile.routing.envelope)
        self.assertTrue(result.valid)
        self.assertEqual((), result.route.support_selections)

    def test_small_explicit_skill_routes_only_that_skill_after_support_rejection(self) -> None:
        rejected = ConsentRejection.from_proposal(
            proposal(self.phase_one.scope_anchor_id), rejection_id="rejection-y",
            actor="user", rejected_at=NOW,
        )
        decision = validate_support_selection(
            proposal(self.phase_one.scope_anchor_id), SupportPolicy.ASK, (),
            (rejected,), self.index, NOW,
        )
        result = self.validator.validate(
            self.explicit_request(outcome=OutcomeMode.LIMITED),
            SNAPSHOT,
            explicit_policy(self.phase_one.scope_anchor_id),
            context(),
        )
        self.assertFalse(decision.should_prompt)
        self.assertEqual(RoutingEnvelope.SINGLE, result.route.envelope)
        self.assertEqual("skill:x", result.route.primary_selection.capability_id)
        self.assertEqual((), result.route.support_selections)
        self.assertEqual(OutcomeMode.LIMITED, result.outcome_mode)

    def test_small_only_x_forbids_support_proposal_and_activation(self) -> None:
        support_selection = selection(
            SKILL_Y, origin=SelectionOrigin.ROUTER_RECOMMENDED,
        )
        result = self.validator.validate(
            self.explicit_request(support=(support_selection,)),
            SNAPSHOT,
            explicit_policy(
                self.phase_one.scope_anchor_id,
                ExplicitSemantics.ALLOWED_SET,
                SupportPolicy.FORBID,
            ),
            context(),
        )
        self.assertFalse(result.valid)
        self.assertIn("support-forbidden", {item.code for item in result.violations})

    def test_medium_auto_is_phased_and_each_phase_can_route_differently(self) -> None:
        profile = decide_request(
            GoalRelation.NONE,
            TaskSignals(distinct_stages=2),
            resolve_directive(DirectiveInput("實作並驗證")),
            RuntimeMode.HYBRID,
        )
        first = self.validator.validate(
            replace(request_for(), envelope=RoutingEnvelope.PHASED),
            SNAPSHOT, auto_policy(), context(),
        )
        second_request = replace(
            request_for(primary=selection(SKILL_Y)),
            route_id="route-2", phase_id="phase-2", envelope=RoutingEnvelope.PHASED,
        )
        second = self.validator.validate(second_request, SNAPSHOT, auto_policy(), context())
        self.assertEqual(RoutingEnvelope.PHASED, profile.routing.envelope)
        self.assertTrue(first.valid and second.valid)
        self.assertNotEqual(
            first.route.primary_selection.capability_id,
            second.route.primary_selection.capability_id,
        )

    def test_medium_explicit_lock_is_checked_in_every_phase(self) -> None:
        policy = explicit_policy(self.workflow.scope_anchor_id)
        results = []
        for phase in (self.phase_one, self.phase_two):
            inherited = inherit_explicit_policy(policy, phase, self.index)
            request = self.explicit_request(
                envelope=RoutingEnvelope.PHASED,
                scope=phase.scope_anchor_id,
                phase_id=phase.aggregate_id,
                dispositions=(disposition(phase.scope_anchor_id, "skill:x"),),
            )
            results.append(self.validator.validate(request, SNAPSHOT, inherited, context()))
        self.assertTrue(all(item.valid for item in results))
        self.assertTrue(all(item.route.envelope is RoutingEnvelope.PHASED for item in results))
        self.assertTrue(all(
            disposition_item.skill_id == "skill:x"
            for result in results
            for disposition_item in result.route.explicit_skill_dispositions
        ))

    def test_phase_one_support_grant_cannot_be_reused_in_phase_two(self) -> None:
        first_proposal = proposal(self.phase_one.scope_anchor_id)
        grant = ConsentGrant.from_proposal(
            first_proposal, grant_id="grant-y", scope=ScopeKind.PHASE,
            scope_anchor_id=self.phase_one.scope_anchor_id, actor="user",
            granted_at=NOW, expires_at=NOW + timedelta(hours=1),
        )
        support_selection = selection(
            SKILL_Y, origin=SelectionOrigin.ROUTER_RECOMMENDED, consent=grant.grant_id,
        )
        result = self.validator.validate(
            self.explicit_request(
                envelope=RoutingEnvelope.PHASED,
                scope=self.phase_two.scope_anchor_id,
                phase_id="phase-2",
                support=(support_selection,),
            ),
            SNAPSHOT,
            explicit_policy(self.workflow.scope_anchor_id),
            context(),
        )
        self.assertFalse(match_grant(
            grant, proposal(self.phase_two.scope_anchor_id, "phase-2"), self.index, NOW,
        ))
        self.assertFalse(result.valid)
        self.assertIn("support-consent-missing", {item.code for item in result.violations})

    def test_rejected_support_keeps_original_exit_gate_and_honestly_blocks(self) -> None:
        exit_gate = "必須由 skill:y 驗證"
        rejection = ConsentRejection.from_proposal(
            proposal(self.phase_one.scope_anchor_id), rejection_id="reject-y",
            actor="user", rejected_at=NOW,
        )
        replacement = replacement_anchor(
            self.phase_one, replacement_aggregate_id="phase-replacement", created_revision=2,
        )
        self.assertEqual(self.phase_one.scope_anchor_id, replacement.scope_anchor_id)
        self.assertFalse(may_reask_after_rejection(
            rejection, proposal(replacement.scope_anchor_id, "phase-replacement"),
        ))
        coverage = evaluate_explicit_coverage(
            explicit_policy(self.phase_one.scope_anchor_id),
            (disposition(self.phase_one.scope_anchor_id, "skill:x", SkillDisposition.NOT_APPLICABLE),),
            {}, {}, {},
        )[0]
        result = self.validator.validate(
            self.explicit_request(outcome=OutcomeMode.BLOCKED, exit_gate=exit_gate),
            SNAPSHOT, explicit_policy(self.phase_one.scope_anchor_id), context(),
        )
        self.assertEqual(exit_gate, result.exit_gate)
        self.assertEqual(OutcomeMode.BLOCKED, result.outcome_mode)
        self.assertNotEqual(CoverageStatus.SATISFIED, coverage.status)

    def test_managed_goal_explicit_lock_survives_work_item_and_phase_split(self) -> None:
        decision = decide_request(
            GoalRelation.PROGRESS, TaskSignals.large(),
            resolve_directive(DirectiveInput("使用 X", ("skill:x",), "use")),
            RuntimeMode.HYBRID,
        )
        work_item = descendant_anchor(
            self.workflow, ScopeKind.WORK_ITEM, "work-1", "deliver", 1,
        )
        phase = descendant_anchor(work_item, ScopeKind.PHASE, "phase-child", "code", 1)
        index = ScopeIndex((self.workflow, work_item, phase))
        policy = explicit_policy(self.workflow.scope_anchor_id)
        self.assertEqual(RoutingEnvelope.MANAGED_GOAL, decision.routing.envelope)
        self.assertEqual(("skill:x",), inherit_explicit_policy(policy, phase, index).explicit_skill_ids)

    def test_managed_goal_auto_reclassifies_each_work_item(self) -> None:
        outer = decide_request(
            GoalRelation.PROGRESS, TaskSignals.large(),
            resolve_directive(DirectiveInput("繼續目標")), RuntimeMode.HYBRID,
        )
        small_item = decide_request(
            GoalRelation.NONE, TaskSignals.small(),
            resolve_directive(DirectiveInput("修正一個欄位")), RuntimeMode.HYBRID,
        )
        phased_item = decide_request(
            GoalRelation.NONE, TaskSignals(distinct_stages=2),
            resolve_directive(DirectiveInput("實作並測試")), RuntimeMode.HYBRID,
        )
        self.assertEqual(RoutingEnvelope.MANAGED_GOAL, outer.routing.envelope)
        self.assertEqual(RoutingEnvelope.SINGLE, small_item.routing.envelope)
        self.assertEqual(RoutingEnvelope.PHASED, phased_item.routing.envelope)

    def test_managed_goal_required_all_is_incomplete_without_every_activation(self) -> None:
        policy = explicit_policy(
            self.workflow.scope_anchor_id,
            ExplicitSemantics.REQUIRED_ALL,
            skills=("skill:x", "skill:y"),
        )
        coverage = evaluate_explicit_coverage(
            policy,
            (
                disposition(self.workflow.scope_anchor_id, "skill:x", SkillDisposition.ACTIVE_REQUIRED),
                disposition(self.workflow.scope_anchor_id, "skill:y", SkillDisposition.ALLOWED_NOT_SELECTED),
            ),
            {"skill:x": ("activation-x",)},
            {},
            {},
        )
        self.assertEqual(CoverageStatus.SATISFIED, coverage[0].status)
        self.assertEqual(CoverageStatus.UNCOVERED, coverage[1].status)


if __name__ == "__main__":
    unittest.main()
