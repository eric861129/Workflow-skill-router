from __future__ import annotations

from typing import Protocol, runtime_checkable

from .service_models import RequestContext


class RequestAuthorizer(Protocol):
    def authorize_read(self, context: RequestContext) -> None: ...
    def authorize_mutation(self, context: RequestContext, expected_state_version: int) -> None: ...
    def authorize_reporting(self, context: RequestContext, observation: object) -> None: ...


class RuntimeAuthorityContextRepository(Protocol):
    def require(self, context: RequestContext): ...


class RuntimeContextPort(Protocol):
    def sync_verified(self, request): ...


class ArtifactStorePort(Protocol):
    def put_bytes(self, content: bytes, media_type: str, classification: str, purpose: str): ...


class SnapshotCodecPort(Protocol):
    def encode(self, snapshot) -> bytes: ...


class RuntimeSyncCoordinatorPort(Protocol):
    def persist(self, command, result, snapshot_ref) -> None: ...


class ProjectionRunnerPort(Protocol):
    def catch_up(self) -> None: ...


class PlannerPort(Protocol):
    def validate_and_persist(self, command): ...


class SchedulerPort(Protocol):
    def next(self, query, require_resume_refresh: bool = True): ...


class SnapshotRepositoryPort(Protocol):
    def require(self, snapshot_id: str): ...


class PolicyRepositoryPort(Protocol):
    def require(self, policy_revision: int, runtime_policy_snapshot_id: str): ...


class ValidationContextPort(Protocol):
    def current_for(self, command, snapshot, policy): ...


class RouteValidatorPort(Protocol):
    def validate(self, request, snapshot, policy, context): ...


class ActivationPreflightPort(Protocol):
    def bind_single_use_after_validation(self, command, result, snapshot): ...
    def verify_consumption_receipt(self, command) -> None: ...


class WorkEventCoordinatorPort(Protocol):
    def record(self, command): ...


class GateContextPort(Protocol):
    def build_from_current_projection(self, command): ...


class GateEvaluatorPort(Protocol):
    def evaluate(self, request): ...


class GateCoordinatorPort(Protocol):
    def persist_result(self, command, result): ...


class StatusReaderPort(Protocol):
    def read(self, query): ...


class DiagnosticsReaderPort(Protocol):
    def read(self): ...


class ArtifactProtectorPort(Protocol):
    def protect(self, content: bytes, purpose: str): ...


class EvaluationPort(Protocol):
    def run(self, command): ...
    def compare(self, command): ...
    def export(self, command): ...


@runtime_checkable
class HostIntegrationAdapterPort(Protocol):
    """只能由伺服器端 composition root 解析與建立的 Host adapter。"""

    def host_manifest(self): ...
    def build_router_ports(self, **server_owned_resources): ...
    def build_conformance_fixture(self): ...
