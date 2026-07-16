from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from workflow_skill_router.capabilities.agent_runtime import AgentRuntimeSnapshot
from workflow_skill_router.routing.models import RouteValidationRequest
from workflow_skill_router.workflow.observations import Observation


class ResultCodec:
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RequestContext:
    session_id: str
    actor: str
    runtime_policy_snapshot_id: str


@dataclass(frozen=True, slots=True)
class RuntimeContextSyncIntent:
    host_snapshot_ref: str | None
    plugin_handshake_ref: str | None
    agent_runtime_snapshot: AgentRuntimeSnapshot


@dataclass(frozen=True, slots=True)
class SyncRuntimeContext:
    context: RequestContext
    intent: RuntimeContextSyncIntent
    expected_state_version: int
    idempotency_key: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class PlanWork:
    context: RequestContext
    objective: str
    goal_binding_id: str | None
    requested_work_mode: str | None
    explicit_skill_ids: tuple[str, ...]
    explicit_semantics: str | None
    expected_state_version: int
    idempotency_key: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class PlanWorkResult(ResultCodec):
    status: str
    workflow_run_id: str | None
    work_graph_id: str | None
    created_work_items: int


@dataclass(frozen=True, slots=True)
class NextWorkQuery:
    context: RequestContext
    workflow_run_id: str


@dataclass(frozen=True, slots=True)
class NextWorkResult(ResultCodec):
    status: str
    refresh_requirements: tuple[str, ...]
    work_item: object | None


@dataclass(frozen=True, slots=True)
class ValidateRoute:
    context: RequestContext
    route_proposal: RouteValidationRequest
    capability_snapshot_id: str
    policy_revision: int
    expected_state_version: int
    idempotency_key: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class RecordWorkEvent:
    context: RequestContext
    workflow_run_id: str
    phase_id: str
    observation: Observation
    activation_receipt_ref: str | None
    expected_state_version: int
    idempotency_key: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class RecordWorkEventResult(ResultCodec):
    event_ids: tuple[str, ...]
    resulting_state_version: int
    replayed: bool

    @classmethod
    def from_append(cls, append) -> "RecordWorkEventResult":
        return cls(
            tuple(item.event_id for item in append.events),
            append.resulting_state_version,
            append.replayed,
        )


@dataclass(frozen=True, slots=True)
class EvaluateGate:
    context: RequestContext
    workflow_run_id: str
    phase_id: str
    expected_state_version: int
    expected_plan_revision: int
    expected_evidence_digest: str
    evidence_refs: tuple[str, ...]
    idempotency_key: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class RouterStatusQuery:
    context: RequestContext
    goal_binding_id: str | None
    workflow_run_id: str | None


@dataclass(frozen=True, slots=True)
class GoalStatusView(ResultCodec):
    candidate_id: str
    candidate_type: str
    evidence_digest: str


@dataclass(frozen=True, slots=True)
class RouterStatusView(ResultCodec):
    goal_binding_id: str | None
    workflow_run_id: str | None
    created_work_items: int
    goal_status_candidate: GoalStatusView | None
    host_goal_mutated: bool


@dataclass(frozen=True, slots=True)
class RouterDiagnostics(ResultCodec):
    semantic_event_count: int
    projection_checkpoint: int
    pending_activation_reservations: int

