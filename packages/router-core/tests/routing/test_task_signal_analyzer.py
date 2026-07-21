from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.routing.directives import resolve_directive
from workflow_skill_router.routing.models import (
    DirectiveInput,
    GoalRelation,
    RoutingEnvelope,
    RuntimeMode,
)
from workflow_skill_router.routing.profiler import decide_request
from workflow_skill_router.routing.task_signal_analyzer import analyze_task_signals


class TaskSignalAnalyzerTests(unittest.TestCase):
    def test_single_review_defaults_conservatively(self) -> None:
        analysis = analyze_task_signals("Review this function")

        self.assertEqual(1, analysis.signals.distinct_stages)
        self.assertEqual("low", analysis.confidence)
        self.assertEqual("deterministic-objective-v1", analysis.classifier_revision)
        self.assertEqual(("single-default",), analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.SINGLE)

    def test_sequenced_chinese_actions_are_phased(self) -> None:
        analysis = analyze_task_signals("先規劃 API，再實作，最後測試與撰寫文件")

        self.assertGreater(analysis.signals.distinct_stages, 1)
        self.assertIn("multi-stage-sequence", analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.PHASED)

    def test_trusted_multiple_domains_are_phased_without_text_authority(self) -> None:
        analysis = analyze_task_signals(
            "Update the implementation and open a pull request",
            trusted_domains=("backend", "frontend"),
        )

        self.assertEqual(2, analysis.signals.domain_count)
        self.assertFalse(analysis.signals.cross_repo)
        self.assertIn("trusted-multi-domain", analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.PHASED)

    def test_two_trusted_strong_signals_enable_managed_goal(self) -> None:
        analysis = analyze_task_signals(
            "Coordinate cross-repository resumable milestones with a dependency DAG",
            trusted_tags=("cross-repo", "resumable", "milestone", "dependency-dag"),
        )

        self.assertTrue(analysis.signals.cross_repo)
        self.assertTrue(analysis.signals.resumable)
        self.assertTrue(analysis.signals.dependency_dag)
        self.assertEqual(2, analysis.signals.milestone_count)
        self.assertEqual("high", analysis.confidence)
        self.assertIn("managed-goal-evidence", analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.MANAGED_GOAL)

    def test_one_strong_signal_does_not_enable_managed_goal(self) -> None:
        analysis = analyze_task_signals(
            "Continue a resumable plan",
            trusted_tags=("resumable",),
        )

        self.assertFalse(analysis.signals.resumable)
        self.assertFalse(analysis.signals.cross_repo)
        self.assert_envelope(analysis, RoutingEnvelope.SINGLE)

    def test_english_action_family_is_phased(self) -> None:
        analysis = analyze_task_signals("Plan, implement, test, and document the release")

        self.assertGreater(analysis.signals.distinct_stages, 1)
        self.assertIn("multi-action-family", analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.PHASED)

    def test_empty_or_overlong_objective_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            analyze_task_signals("  \u3000")
        with self.assertRaises(ValueError):
            analyze_task_signals("x" * 4097)

    def test_full_width_unicode_normalizes_before_classification(self) -> None:
        analysis = analyze_task_signals(
            "  Ｐｌａｎ，　ｉｍｐｌｅｍｅｎｔ，　ｔｅｓｔ，　ａｎｄ　ｄｏｃｕｍｅｎｔ　ｔｈｅ　ｒｅｌｅａｓｅ  "
        )

        self.assertGreater(analysis.signals.distinct_stages, 1)
        self.assert_envelope(analysis, RoutingEnvelope.PHASED)

    def test_sequence_synonym_with_numbered_actions_is_phased(self) -> None:
        analysis = analyze_task_signals("1. Analyze the change; 2. build it; 3. verify the result")

        self.assertGreater(analysis.signals.distinct_stages, 1)
        self.assertIn("multi-stage-sequence", analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.PHASED)

    def test_negated_action_does_not_add_a_stage(self) -> None:
        analysis = analyze_task_signals("Plan the release, but do not test it")

        self.assertEqual(1, analysis.signals.distinct_stages)
        self.assertIn("negated-action-ignored", analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.SINGLE)

    def test_duplicated_connectors_do_not_inflate_stages(self) -> None:
        analysis = analyze_task_signals("Plan and and plan")

        self.assertEqual(1, analysis.signals.distinct_stages)
        self.assert_envelope(analysis, RoutingEnvelope.SINGLE)

    def assert_envelope(self, analysis, expected: RoutingEnvelope) -> None:
        directive = resolve_directive(DirectiveInput("automatic routing"))
        decision = decide_request(
            GoalRelation.NONE,
            analysis.signals,
            directive,
            RuntimeMode.HYBRID,
        )
        self.assertEqual(expected, decision.routing.envelope)


if __name__ == "__main__":
    unittest.main()
