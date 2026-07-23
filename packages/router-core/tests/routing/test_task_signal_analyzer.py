from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.capabilities.models import RiskLevel
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
    def test_required_single_fixture(self) -> None:
        analysis = analyze_task_signals("修正登入頁的空白錯誤")

        self.assertEqual(1, analysis.signals.distinct_stages)
        self.assertEqual("low", analysis.confidence)
        self.assertEqual("deterministic-objective-v1", analysis.classifier_revision)
        self.assertEqual(("single-default",), analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.SINGLE)

    def test_required_chinese_phased_fixture(self) -> None:
        analysis = analyze_task_signals("先盤點 API，再實作、測試並更新文件")

        self.assertEqual(4, analysis.signals.distinct_stages)
        self.assertEqual("high", analysis.confidence)
        self.assertEqual(("multi-stage-sequence",), analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.PHASED)

    def test_required_trusted_domains_fixture(self) -> None:
        analysis = analyze_task_signals(
            "更新 backend 與 frontend，完成後建立 PR",
            trusted_domains=("backend", "frontend"),
        )

        self.assertEqual(2, analysis.signals.domain_count)
        self.assertFalse(analysis.signals.cross_repo)
        self.assertEqual("medium", analysis.confidence)
        self.assertEqual(("trusted-multi-domain",), analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.PHASED)

    def test_required_managed_goal_fixture(self) -> None:
        analysis = analyze_task_signals(
            "持續進行跨 repository 遷移，包含 milestones 與相依工作",
            trusted_tags=("cross-repo", "resumable", "milestone", "dependency-dag"),
        )

        self.assertEqual(1, analysis.signals.domain_count)
        self.assertTrue(analysis.signals.cross_repo)
        self.assertTrue(analysis.signals.resumable)
        self.assertTrue(analysis.signals.dependency_dag)
        self.assertEqual(2, analysis.signals.milestone_count)
        self.assertEqual("high", analysis.confidence)
        self.assertEqual(
            (
                "cross-repository-signal",
                "resumable-signal",
                "milestone-signal",
                "dependency-signal",
                "managed-goal-evidence",
            ),
            analysis.reason_codes,
        )
        self.assert_envelope(analysis, RoutingEnvelope.MANAGED_GOAL)

    def test_required_english_single_fixture(self) -> None:
        analysis = analyze_task_signals("Review this function")

        self.assertEqual(("single-default",), analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.SINGLE)

    def test_required_english_phased_fixture(self) -> None:
        analysis = analyze_task_signals("Plan, implement, test, and document the release")

        self.assertEqual(4, analysis.signals.distinct_stages)
        self.assertEqual("high", analysis.confidence)
        self.assertEqual(("multi-action-family",), analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.PHASED)

    def test_objective_strong_signals_can_select_managed_goal_without_authority(self) -> None:
        analysis = analyze_task_signals("Coordinate cross-repository resumable migration")

        self.assertEqual(1, analysis.signals.domain_count)
        self.assertEqual(RiskLevel.R0, analysis.signals.risk)
        self.assertTrue(analysis.signals.cross_repo)
        self.assertTrue(analysis.signals.resumable)
        self.assertFalse(hasattr(analysis, "capability"))
        self.assertFalse(hasattr(analysis, "authority"))
        self.assertEqual(
            (
                "cross-repository-signal",
                "resumable-signal",
                "managed-goal-evidence",
            ),
            analysis.reason_codes,
        )
        self.assert_envelope(analysis, RoutingEnvelope.MANAGED_GOAL)

    def test_one_objective_strong_signal_remains_single(self) -> None:
        analysis = analyze_task_signals("Continue resumable work")

        self.assertFalse(analysis.signals.resumable)
        self.assertFalse(analysis.signals.cross_repo)
        self.assertEqual(("resumable-signal", "single-default"), analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.SINGLE)

    def test_write_code_is_only_one_implementation_action(self) -> None:
        analysis = analyze_task_signals("write code")

        self.assertEqual(1, analysis.signals.distinct_stages)
        self.assertEqual(("single-default",), analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.SINGLE)

    def test_numbered_non_actions_do_not_create_stages(self) -> None:
        analysis = analyze_task_signals("1. inspect the configuration; 2. read the output")

        self.assertEqual(1, analysis.signals.distinct_stages)
        self.assertEqual(("single-default",), analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.SINGLE)

    def test_numbered_positive_actions_are_phased(self) -> None:
        analysis = analyze_task_signals("1. plan the change; 2. implement it")

        self.assertEqual(2, analysis.signals.distinct_stages)
        self.assertEqual(("multi-stage-sequence",), analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.PHASED)

    def test_sequenced_same_action_family_is_phased(self) -> None:
        analysis = analyze_task_signals("Plan backend, then plan frontend")

        self.assertEqual(2, analysis.signals.distinct_stages)
        self.assertEqual(("multi-stage-sequence",), analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.PHASED)

    def test_duplicated_connectors_without_sequence_remain_single(self) -> None:
        analysis = analyze_task_signals("Plan and and plan")

        self.assertEqual(1, analysis.signals.distinct_stages)
        self.assertEqual(("single-default",), analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.SINGLE)

    def test_english_negation_does_not_add_a_stage(self) -> None:
        analysis = analyze_task_signals("Plan the release, but do not test it")

        self.assertEqual(1, analysis.signals.distinct_stages)
        self.assertEqual(("negated-action-ignored", "single-default"), analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.SINGLE)

    def test_coordinated_english_negation_ignores_each_action(self) -> None:
        analysis = analyze_task_signals("Plan the release, but do not test or document it")

        self.assertEqual(1, analysis.signals.distinct_stages)
        self.assertEqual(("negated-action-ignored", "single-default"), analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.SINGLE)

    def test_chinese_negation_is_ignored(self) -> None:
        analysis = analyze_task_signals("規劃釋出，但不要測試")

        self.assertEqual(1, analysis.signals.distinct_stages)
        self.assertEqual(("negated-action-ignored", "single-default"), analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.SINGLE)

    def test_chinese_not_needed_negation_is_ignored(self) -> None:
        analysis = analyze_task_signals("規劃釋出，但不需要測試")

        self.assertEqual(1, analysis.signals.distinct_stages)
        self.assertEqual(("negated-action-ignored", "single-default"), analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.SINGLE)

    def test_positive_action_remains_when_later_occurrence_is_negated(self) -> None:
        analysis = analyze_task_signals(
            "Plan release, test staging, then do not test production"
        )

        self.assertEqual(2, analysis.signals.distinct_stages)
        self.assertEqual(
            ("negated-action-ignored", "multi-action-family"),
            analysis.reason_codes,
        )
        self.assert_envelope(analysis, RoutingEnvelope.PHASED)

    def test_chinese_coordinated_negation_is_occurrence_specific(self) -> None:
        analysis = analyze_task_signals("規劃釋出，但不要測試或更新文件")

        self.assertEqual(1, analysis.signals.distinct_stages)
        self.assertEqual(("negated-action-ignored", "single-default"), analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.SINGLE)

    def test_positive_chinese_action_survives_later_coordinated_negation(self) -> None:
        analysis = analyze_task_signals("規劃、測試 staging，但不要測試或更新文件")

        self.assertEqual(2, analysis.signals.distinct_stages)
        self.assertEqual(
            ("negated-action-ignored", "multi-action-family"),
            analysis.reason_codes,
        )
        self.assert_envelope(analysis, RoutingEnvelope.PHASED)

    def test_leading_sequence_marker_does_not_inflate_repeated_action(self) -> None:
        analysis = analyze_task_signals("Then plan backend and plan frontend")

        self.assertEqual(1, analysis.signals.distinct_stages)
        self.assertEqual(("single-default",), analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.SINGLE)

    def test_empty_or_overlong_objective_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            analyze_task_signals("  \u3000")
        with self.assertRaises(ValueError):
            analyze_task_signals("x" * 4097)

    def test_full_width_unicode_normalizes_before_classification(self) -> None:
        analysis = analyze_task_signals(
            "  Ｐｌａｎ，　ｉｍｐｌｅｍｅｎｔ，　ｔｅｓｔ，　ａｎｄ　ｄｏｃｕｍｅｎｔ　ｔｈｅ　ｒｅｌｅａｓｅ  "
        )

        self.assertEqual(4, analysis.signals.distinct_stages)
        self.assertEqual(("multi-action-family",), analysis.reason_codes)
        self.assert_envelope(analysis, RoutingEnvelope.PHASED)

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
