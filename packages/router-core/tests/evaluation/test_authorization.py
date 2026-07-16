from dataclasses import replace
import unittest

from workflow_skill_router.evaluation.authorization import EvalRunRequest, EvaluationAuthorizer
from workflow_skill_router.evaluation.contracts import EvaluationProfile
from workflow_skill_router.service_models import RequestContext


class AuthorizationTests(unittest.TestCase):
    def test_client_cannot_widen_server_authorization(self):
        context = RequestContext("session-1", "agent", "policy-1")
        request = EvalRunRequest(EvaluationProfile.BEHAVIOR, "host-task", "sha256:suite")
        authorizer = EvaluationAuthorizer()
        ref = authorizer.issue_run(context, request)
        with self.assertRaisesRegex(PermissionError, "authorization_widening"):
            authorizer.validate_run(context, ref, replace(request, adapter_kind="external-provider"))

    def test_authorization_is_bound_to_request_context(self):
        context = RequestContext("session-1", "agent", "policy-1")
        request = EvalRunRequest(EvaluationProfile.BEHAVIOR, "host-task", "sha256:suite")
        authorizer = EvaluationAuthorizer()
        ref = authorizer.issue_run(context, request)
        with self.assertRaisesRegex(PermissionError, "request_context_mismatch"):
            authorizer.validate_run(replace(context, session_id="other"), ref, request)


if __name__ == "__main__": unittest.main()
