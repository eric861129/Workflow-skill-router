from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
class RoutingContextInput:
    workspace_root: str | None = None
    domains: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    current_phase_id: str | None = None


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
    routing_context: RoutingContextInput = field(default_factory=RoutingContextInput)


@dataclass(frozen=True, slots=True)
class PlannedSkillPhase(ResultCodec):
    phase_id: str
    primary_skill_id: str
    support_skill_ids: tuple[str, ...]
    exit_gate: str


@dataclass(frozen=True, slots=True)
class ClassificationDecisionView(ResultCodec):
    source: str
    confidence: str
    classifier_revision: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PlanWorkResult(ResultCodec):
    status: str
    workflow_run_id: str | None
    work_graph_id: str | None
    created_work_items: int
    routing_envelope: str
    selection_mode: str
    support_consent_required: bool
    planned_skill_ids: tuple[str, ...]
    runtime_mode: str
    route_source: str
    routing_profile_ids: tuple[str, ...]
    routing_profile_digest: str | None
    matched_profile_rule_id: str | None
    planned_skill_tree: tuple[PlannedSkillPhase, ...]
    activation_status: str
    profile_warnings: tuple[str, ...]
    classification: ClassificationDecisionView


@dataclass(frozen=True, slots=True)
class ProposeSupportConsent:
    context: RequestContext
    workflow_run_id: str
    phase_id: str
    scope_anchor_id: str
    goal_revision: int | None
    plan_revision: int
    primary_skill_id: str
    support_skill_ids: tuple[str, ...]
    context_fingerprint: str
    expected_state_version: int
    idempotency_key: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class TransitionSupportConsent:
    context: RequestContext
    proposal_id: str
    action: str
    current_phase_id: str
    current_scope_anchor_id: str
    current_goal_revision: int | None
    current_plan_revision: int
    current_context_fingerprint: str
    expected_state_version: int
    idempotency_key: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class SupportConsentResult(ResultCodec):
    status: str
    proposal_id: str
    workflow_run_id: str
    phase_id: str
    routing_envelope: str
    selection_mode: str
    primary_skill: str
    support_skills: tuple[str, ...]
    consent_action: str
    goal_relation: str
    decision_ref: str | None
    state_version: int
    replayed: bool
    runtime_mode: str


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


@dataclass(frozen=True, slots=True)
class RunModelEvaluation:
    context: RequestContext
    authorization_ref: str
    sealed_case_ref: str
    repeats: int
    idempotency_key: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class CompareEvaluations:
    context: RequestContext
    authorization_ref: str
    baseline_run_id: str
    candidate_run_id: str
    idempotency_key: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ExportRouterArtifact:
    context: RequestContext
    authorization_ref: str
    comparison_ref: str
    export_kind: str
    attestation_ref: str | None
    idempotency_key: str
    correlation_id: str
