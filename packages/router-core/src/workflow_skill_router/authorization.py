from __future__ import annotations

from .service_models import RequestContext


class RequestAuthorizationError(PermissionError):
    pass


class SessionRequestAuthorizer:
    def __init__(self, session_repository) -> None:
        self._sessions = session_repository

    def _verify(self, context: RequestContext) -> None:
        authority = self._sessions.require(context.session_id)
        if (
            authority.actor != context.actor
            or authority.runtime_policy_snapshot_id != context.runtime_policy_snapshot_id
        ):
            raise RequestAuthorizationError("request-context-unverified")

    def authorize_read(self, context: RequestContext) -> None:
        self._verify(context)

    def authorize_mutation(
        self,
        context: RequestContext,
        expected_state_version: int,
    ) -> None:
        self._verify(context)
        if expected_state_version < 0:
            raise RequestAuthorizationError("state-version-invalid")

    def authorize_reporting(self, context: RequestContext, observation: object) -> None:
        del observation
        self._verify(context)
