from dataclasses import replace
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.routing.directives import (
    DirectiveAmbiguityError,
    resolve_directive,
)
from workflow_skill_router.routing.models import (
    DirectiveInput,
    ExecutionKind,
    ExplicitSemantics,
    GoalRelation,
    RoutingEnvelope,
    RuntimeMode,
    SelectionMode,
    SupportPolicy,
    TaskSignals,
    UserDirective,
)
from workflow_skill_router.routing.profiler import (
    decide_request,
    resolve_classification_source,
)


class RequestProfilerTests(unittest.TestCase):
    def test_automatic_selection_does_not_require_support_consent(self) -> None:
        automatic = UserDirective.auto()
        resolved = resolve_directive(DirectiveInput("一般任務"))

        self.assertEqual("auto", automatic.support_policy.value)
        self.assertEqual("auto", resolved.support_policy.value)

    def test_status_is_control_query_without_routing_payload(self) -> None:
        decision = decide_request(
            GoalRelation.STATUS,
            TaskSignals.small(),
            UserDirective.auto(),
            RuntimeMode.HYBRID,
        )
        self.assertEqual(ExecutionKind.CONTROL_QUERY, decision.execution_kind)
        self.assertIsNone(decision.routing)

    def test_two_distinct_stages_are_phased_even_with_explicit_skill(self) -> None:
        directive = resolve_directive(DirectiveInput(
            "使用 api-designer",
            ("skill:local/api-designer",),
            "use",
        ))
        decision = decide_request(
            GoalRelation.NONE,
            TaskSignals(intent_count=1, domain_count=1, distinct_stages=2),
            directive,
            RuntimeMode.HYBRID,
        )
        self.assertEqual(RoutingEnvelope.PHASED, decision.routing.envelope)
        self.assertEqual(SelectionMode.EXPLICIT_LOCKED, decision.routing.skill_policy)

    def test_active_goal_side_question_is_detached_read_only_not_managed_goal(self) -> None:
        decision = decide_request(
            GoalRelation.SIDE_QUESTION,
            TaskSignals.small(),
            UserDirective.auto(),
            RuntimeMode.HYBRID,
        )
        self.assertNotEqual(RoutingEnvelope.MANAGED_GOAL, decision.routing.envelope)
        self.assertTrue(decision.routing.detached_read_only)

    def test_progress_in_active_goal_uses_managed_goal(self) -> None:
        decision = decide_request(
            GoalRelation.PROGRESS,
            TaskSignals.small(),
            UserDirective.auto(),
            RuntimeMode.HYBRID,
        )
        self.assertEqual(RoutingEnvelope.MANAGED_GOAL, decision.routing.envelope)

    def test_native_goal_binding_has_first_classification_precedence(self) -> None:
        directive = replace(
            UserDirective.auto(),
            requested_work_mode=RoutingEnvelope.SINGLE,
        )
        decision = decide_request(
            GoalRelation.PROGRESS,
            TaskSignals.large(),
            directive,
            RuntimeMode.HYBRID,
        )

        self.assertEqual(
            "native-goal-binding",
            resolve_classification_source(GoalRelation.PROGRESS, directive, decision),
        )

    def test_caller_work_mode_hint_precedes_deterministic_analysis(self) -> None:
        directive = replace(
            UserDirective.auto(),
            requested_work_mode=RoutingEnvelope.SINGLE,
        )
        decision = decide_request(
            GoalRelation.NONE,
            TaskSignals.large(),
            directive,
            RuntimeMode.HYBRID,
        )

        self.assertEqual(
            "caller-work-mode-hint",
            resolve_classification_source(GoalRelation.NONE, directive, decision),
        )

    def test_non_single_analyzer_decision_is_explainable(self) -> None:
        directive = UserDirective.auto()
        decision = decide_request(
            GoalRelation.NONE,
            TaskSignals(distinct_stages=2),
            directive,
            RuntimeMode.HYBRID,
        )

        self.assertEqual(
            "deterministic-analyzer",
            resolve_classification_source(GoalRelation.NONE, directive, decision),
        )

    def test_single_analyzer_default_uses_builtin_fallback(self) -> None:
        directive = UserDirective.auto()
        decision = decide_request(
            GoalRelation.NONE,
            TaskSignals.small(),
            directive,
            RuntimeMode.HYBRID,
        )

        self.assertEqual(
            "builtin-fallback",
            resolve_classification_source(GoalRelation.NONE, directive, decision),
        )

    def test_explicit_phased_mode_overrides_small_size_classifier(self) -> None:
        directive = replace(
            UserDirective.auto(),
            requested_work_mode=RoutingEnvelope.PHASED,
        )
        decision = decide_request(
            GoalRelation.NONE,
            TaskSignals.small(),
            directive,
            RuntimeMode.HYBRID,
        )
        self.assertEqual(RoutingEnvelope.PHASED, decision.routing.envelope)

    def test_single_mode_inside_native_goal_keeps_outer_goal_and_scopes_current_item(self) -> None:
        directive = replace(
            UserDirective.auto(),
            requested_work_mode=RoutingEnvelope.SINGLE,
        )
        decision = decide_request(
            GoalRelation.PROGRESS,
            TaskSignals.large(),
            directive,
            RuntimeMode.HYBRID,
        )
        self.assertEqual(RoutingEnvelope.MANAGED_GOAL, decision.routing.envelope)
        self.assertEqual(
            RoutingEnvelope.SINGLE,
            decision.routing.work_item_envelope_override,
        )

    def test_use_only_and_all_map_to_distinct_policies(self) -> None:
        use = resolve_directive(DirectiveInput("使用 X", ("skill:x",), "use"))
        only = resolve_directive(DirectiveInput("只用 X", ("skill:x",), "only"))
        all_skills = resolve_directive(DirectiveInput(
            "X 與 Y 都要使用",
            ("skill:x", "skill:y"),
            "all",
        ))
        self.assertEqual(
            (ExplicitSemantics.PREFERRED_PRIMARY, SupportPolicy.ASK),
            (use.explicit_semantics, use.support_policy),
        )
        self.assertEqual(
            (ExplicitSemantics.ALLOWED_SET, SupportPolicy.FORBID),
            (only.explicit_semantics, only.support_policy),
        )
        self.assertEqual(ExplicitSemantics.REQUIRED_ALL, all_skills.explicit_semantics)

    def test_multiple_skills_without_semantics_are_rejected(self) -> None:
        with self.assertRaises(DirectiveAmbiguityError):
            resolve_directive(DirectiveInput("使用技能", ("skill:x", "skill:y"), None))


if __name__ == "__main__":
    unittest.main()
