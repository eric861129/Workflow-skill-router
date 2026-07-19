from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.service_models import NextWorkQuery, RequestContext, RouterStatusQuery
try:
    from .support import build_router_service, seed_complete_native_goal, seed_paused_workflow
except ImportError:
    from support import build_router_service, seed_complete_native_goal, seed_paused_workflow


CONTEXT = RequestContext("session-1", "agent", "runtime-policy-1")


class RouterServiceTests(unittest.TestCase):
    def test_status_is_read_only_and_does_not_create_work(self) -> None:
        service = build_router_service()
        before = service.diagnostics()
        view = service.get_router_status(RouterStatusQuery(CONTEXT, "goal-1", None))
        after = service.diagnostics()
        self.assertEqual(before.semantic_event_count, after.semantic_event_count)
        self.assertEqual(0, view.created_work_items)

    def test_resume_requires_refresh_before_next_work(self) -> None:
        service = build_router_service()
        seed_paused_workflow(service, "wf-1", "snap-old")
        result = service.get_next_work(NextWorkQuery(CONTEXT, "wf-1"))
        self.assertEqual("refresh-required", result.status)
        self.assertEqual(("goal", "workspace", "capabilities", "evidence"), result.refresh_requirements)

    def test_native_goal_candidate_is_returned_but_not_applied_to_host(self) -> None:
        service = build_router_service()
        seed_complete_native_goal(service, "goal-1")
        view = service.get_router_status(RouterStatusQuery(CONTEXT, "goal-1", None))
        self.assertEqual("complete", view.goal_status_candidate.candidate_type)
        self.assertFalse(view.host_goal_mutated)


if __name__ == "__main__": unittest.main()
