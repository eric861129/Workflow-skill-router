from __future__ import annotations

from dataclasses import fields
import unittest

from workflow_skill_router.evaluation.composition import EvaluationCompositionPorts, EvaluationFacade
from workflow_skill_router.evaluation.contracts import EvalRunAuthorization, EvaluationProfile
from workflow_skill_router.service_models import RequestContext, RunModelEvaluation


class RecordingRegistry:
    def __init__(self) -> None:
        self.call = None

    def require(self, adapter_id, *, authorization):
        self.call = (adapter_id, authorization)
        return "trusted-adapter"


class Authorizer:
    def __init__(self, authorization) -> None:
        self.authorization = authorization

    def validate_reference(self, context, reference):
        return self.authorization


class Repository:
    def require(self, reference):
        return "sealed-case"


class Broker:
    def run(self, case, authorization, adapter, repeats):
        return case, authorization, adapter, repeats


class SubprocessCompositionTests(unittest.TestCase):
    def test_mcp_command_has_no_executable_path_environment_or_adapter_fields(self):
        names = {field.name for field in fields(RunModelEvaluation)}
        self.assertTrue({"authorization_ref", "sealed_case_ref"}.issubset(names))
        self.assertTrue(names.isdisjoint({"command", "executable", "path", "environment", "adapter_kind"}))

    def test_facade_resolves_adapter_from_server_authorization(self):
        authorization = EvalRunAuthorization(
            "auth-1", "session-1", "agent", "policy-1", EvaluationProfile.BEHAVIOR,
            "subprocess", "sha256:suite",
        )
        registry = RecordingRegistry()
        unused = object()
        ports = EvaluationCompositionPorts(
            run_authorizer=Authorizer(authorization),
            adapter_registry=registry,
            sealed_case_repository=Repository(),
            worker_broker=Broker(),
            isolation_verifier=unused,
            cancellation=unused,
            evaluation_store=unused,
            artifact_store=unused,
            release_policy=unused,
            scorer=unused,
            comparison_store=unused,
            trace_verifier=unused,
            collection_verifier=unused,
            review_verifiers=unused,
            clock=unused,
            id_factory=unused,
        )
        command = RunModelEvaluation(
            RequestContext("session-1", "agent", "policy-1"),
            "auth-1", "case-1", 3, "idem-1", "corr-1",
        )

        result = EvaluationFacade(ports).run(command)

        self.assertEqual(("subprocess", authorization), registry.call)
        self.assertEqual(("sealed-case", authorization, "trusted-adapter", 3), result)


if __name__ == "__main__":
    unittest.main()
