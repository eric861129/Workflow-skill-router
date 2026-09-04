from __future__ import annotations

from importlib import resources
import unittest

from workflow_skill_router.memory import (
    CompletedWorkflowReader,
    MatcherSeed,
    MemoryRequestContext,
    RememberWorkflowCommand,
    WorkflowMemoryService,
    build_route_observation,
    evaluate_observation_eligibility,
)


class M1BPublicContractTests(unittest.TestCase):
    def test_completed_workflow_reader_is_public(self) -> None:
        self.assertTrue(callable(CompletedWorkflowReader))
        self.assertTrue(hasattr(CompletedWorkflowReader, "read"))

    def test_observation_and_remember_interfaces_are_public(self) -> None:
        self.assertTrue(callable(build_route_observation))
        self.assertTrue(callable(evaluate_observation_eligibility))
        self.assertTrue(hasattr(WorkflowMemoryService, "remember_workflow"))
        self.assertEqual(
            "trusted-routing-context",
            MatcherSeed((), ("api",), (), "trusted-routing-context").source,
        )
        context = MemoryRequestContext("session", "actor", "runtime-policy")
        command = RememberWorkflowCommand(
            context=context,
            workflow_run_id="workflow:contract",
            workspace_root=None,
            matcher_seed=None,
            target_profile_class="managed-personal",
            risk_class="r1",
            side_effect_outcome="none",
            one_shot="none",
            idempotency_key="remember-contract",
            correlation_id="correlation-contract",
        )
        self.assertEqual(context, command.context)

    def test_route_observation_schema_is_packaged(self) -> None:
        schema = resources.files("workflow_skill_router.schemas.json.v2").joinpath(
            "route-observation.schema.json"
        )
        self.assertTrue(schema.is_file())


if __name__ == "__main__":
    unittest.main()
