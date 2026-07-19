from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.goals.models import WorkGraph, WorkItem
from workflow_skill_router.goals.orchestrator import GoalOrchestrator, InvalidWorkGraph
from workflow_skill_router.routing.models import GoalRelation, RoutingEnvelope


def item(item_id, status="pending", deps=(), writes=(), envelope=RoutingEnvelope.SINGLE):
    return WorkItem(
        item_id, "m1", item_id, True, status, envelope, deps, (), writes,
        ("goal-scope",), "policy-1", (),
    )


class GoalOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orchestrator = GoalOrchestrator()

    def test_native_binding_requires_host_identity(self) -> None:
        with self.assertRaises(ValueError):
            self.orchestrator.bind_native(None, None, "建置 V2", "active", None)

    def test_status_relation_does_not_increment_semantic_revision(self) -> None:
        binding = self.orchestrator.bind_native(
            "goal-7", "host-r3", "建置 V2", "active", None,
        )
        result = self.orchestrator.observe_message(
            binding, GoalRelation.STATUS, "目前進度？",
        )
        self.assertEqual(binding.goal_revision, result.binding.goal_revision)
        self.assertEqual("GOAL_SIDE_QUERY_OBSERVED", result.audit_event_type)
        self.assertIsNone(result.replacement_graph)

    def test_goal_edit_keeps_completed_items_and_replaces_unstarted_items(self) -> None:
        binding = self.orchestrator.bind_native(
            "goal-7", "host-r3", "建置 V2", "active", None,
        )
        graph = WorkGraph(
            "graph-1", binding.goal_binding_id, binding.objective_digest, 1, "coverage-1",
            (
                item("done", "completed"),
                item("next", "pending", ("done",), ("repo",), RoutingEnvelope.PHASED),
            ),
        )
        revised = self.orchestrator.reconcile(
            binding, graph, "建置 V2 並新增 CLI", "host-r4",
        )
        self.assertEqual("completed", revised.graph.items[0].status)
        self.assertEqual(2, revised.binding.goal_revision)
        self.assertNotEqual("next", revised.graph.items[1].work_item_id)

    def test_cycle_and_overlapping_ready_write_scopes_are_rejected(self) -> None:
        with self.assertRaises(InvalidWorkGraph):
            self.orchestrator.validate_graph((
                item("a", "ready", ("b",), ("repo",)),
                item("b", "ready", ("a",), ("repo",)),
            ))
        with self.assertRaisesRegex(InvalidWorkGraph, "write resource"):
            self.orchestrator.validate_graph((
                item("a", "ready", (), ("repo",)),
                item("b", "ready", (), ("repo",)),
            ))

    def test_next_work_respects_dependency_completion(self) -> None:
        binding = self.orchestrator.bind_managed("建置 V2", "active", None)
        graph = WorkGraph(
            "graph-1", binding.goal_binding_id, binding.objective_digest, 1, "coverage-1",
            (item("done", "completed"), item("next", "pending", ("done",))),
        )
        self.assertEqual("next", self.orchestrator.get_next_work(graph).work_item_id)


if __name__ == "__main__":
    unittest.main()
