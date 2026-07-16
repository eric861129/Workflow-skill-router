from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.routing.coverage import evaluate_explicit_coverage
from workflow_skill_router.routing.models import (
    CoverageStatus,
    ExplicitSemantics,
    ExplicitSkillDisposition,
    ScopeKind,
    SelectionMode,
    SkillDisposition,
    SkillSelectionPolicy,
    SupportPolicy,
)
from workflow_skill_router.routing.scope import (
    ScopeIndex,
    ScopePolicyError,
    create_scope_anchor,
    descendant_anchor,
    inherit_explicit_policy,
    replacement_anchor,
)


def policy(anchor_id: str, semantics: ExplicitSemantics, *skills: str) -> SkillSelectionPolicy:
    return SkillSelectionPolicy(
        mode=SelectionMode.EXPLICIT_LOCKED,
        explicit_skill_ids=skills,
        explicit_semantics=semantics,
        support_policy=SupportPolicy.ASK,
        approved_support_refs=(),
        rejected_support_refs=(),
        consent_scope=ScopeKind.PHASE,
        lock_scope=ScopeKind.WORKFLOW,
        scope_anchor_id=anchor_id,
        plan_revision=1,
    )


def disposition(
    scope_id: str,
    skill_id: str,
    value: SkillDisposition,
) -> ExplicitSkillDisposition:
    return ExplicitSkillDisposition(skill_id, scope_id, value, "route-test", "fixture")


class ExplicitLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = create_scope_anchor(
            ScopeKind.WORKFLOW,
            "workflow-1",
            None,
            "objective-a",
            1,
        )
        self.phase = descendant_anchor(
            self.workflow,
            ScopeKind.PHASE,
            "phase-1",
            "api-contract",
            1,
        )
        self.index = ScopeIndex((self.workflow, self.phase))

    def test_replacement_phase_keeps_semantic_anchor_and_lock(self) -> None:
        replacement = replacement_anchor(
            self.phase,
            replacement_aggregate_id="phase-2",
            created_revision=2,
        )
        index = ScopeIndex((self.workflow, self.phase, replacement))
        locked = policy(
            self.workflow.scope_anchor_id,
            ExplicitSemantics.PREFERRED_PRIMARY,
            "skill:local/api-designer",
        )
        self.assertEqual(self.phase.scope_anchor_id, replacement.scope_anchor_id)
        self.assertEqual(
            ("skill:local/api-designer",),
            inherit_explicit_policy(locked, replacement, index).explicit_skill_ids,
        )

    def test_same_semantic_siblings_in_same_or_different_workflows_never_collide(self) -> None:
        second_root = create_scope_anchor(
            ScopeKind.WORKFLOW,
            "workflow-2",
            None,
            "objective-a",
            1,
        )
        sibling = descendant_anchor(
            self.workflow,
            ScopeKind.PHASE,
            "phase-2",
            "api-contract",
            1,
        )
        other = descendant_anchor(
            second_root,
            ScopeKind.PHASE,
            "phase-1",
            "api-contract",
            1,
        )
        self.assertEqual(
            3,
            len({self.phase.scope_anchor_id, sibling.scope_anchor_id, other.scope_anchor_id}),
        )

    def test_required_all_cannot_pass_with_allowed_not_selected(self) -> None:
        required = policy(
            self.phase.scope_anchor_id,
            ExplicitSemantics.REQUIRED_ALL,
            "skill:a",
            "skill:b",
        )
        coverage = evaluate_explicit_coverage(
            required,
            (
                disposition(self.phase.scope_anchor_id, "skill:a", SkillDisposition.ACTIVE_REQUIRED),
                disposition(self.phase.scope_anchor_id, "skill:b", SkillDisposition.ALLOWED_NOT_SELECTED),
            ),
            {"skill:a": ("activation-1",)},
            {},
            {},
        )
        self.assertEqual(CoverageStatus.SATISFIED, coverage[0].status)
        self.assertEqual(CoverageStatus.UNCOVERED, coverage[1].status)

    def test_preferred_primary_requires_one_primary_route(self) -> None:
        preferred = policy(
            self.phase.scope_anchor_id,
            ExplicitSemantics.PREFERRED_PRIMARY,
            "skill:a",
        )
        coverage = evaluate_explicit_coverage(
            preferred,
            (disposition(self.phase.scope_anchor_id, "skill:a", SkillDisposition.NOT_APPLICABLE),),
            {},
            {},
            {},
        )
        self.assertEqual(CoverageStatus.UNCOVERED, coverage[0].status)

    def test_unknown_or_cyclic_scope_never_inherits_lock(self) -> None:
        locked = policy(
            self.workflow.scope_anchor_id,
            ExplicitSemantics.PREFERRED_PRIMARY,
            "skill:a",
        )
        unknown = create_scope_anchor(
            ScopeKind.PHASE,
            "phase-unknown",
            "scope:missing",
            "unknown",
            1,
        )
        with self.assertRaises(ScopePolicyError):
            inherit_explicit_policy(locked, unknown, self.index)
        self.assertFalse(self.index.is_same_or_descendant(
            candidate_id="scope:missing",
            ancestor_id=self.workflow.scope_anchor_id,
        ))


if __name__ == "__main__":
    unittest.main()
