from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any, Literal, get_args, get_origin, get_type_hints
import re

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
    authority_mode: str = "verified-host"
    host_goal_mutated: bool = False


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
class LocalRecordWorkEventResult(ResultCodec):
    event_ids: tuple[str, ...]
    resulting_state_version: int
    replayed: bool
    authority_mode: str = "router-local"
    evidence_class: str = "user-or-agent-reported-local"
    host_transition_authorized: bool = False


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
class EvaluateGateResult(ResultCodec):
    status: str
    passed: bool
    failures: tuple[str, ...]
    evidence_digest: str
    resulting_state_version: int
    replayed: bool
    gate_scope: str = "router-local"
    authority_mode: str = "router-local"
    evidence_class: str = "user-or-agent-reported-local"
    host_transition_authorized: bool = False


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


# Public Memory commands contain intent and bound identifiers only. In particular,
# no command can manufacture a ProfileWriteAuthority or replace Profile content.
MemoryTarget = Literal["managed-personal", "managed-workspace-local", "user-personal", "workspace-file"]
MemoryCandidateStatus = Literal["proposed", "approved", "rejected", "expired", "suppressed", "superseded", "auto-promoted"]
MemoryFeedbackType = Literal["accepted", "corrected", "rejected", "support-rejected", "capability-unavailable", "gate-failed", "completed", "abandoned", "no-memory"]
MemoryFeedbackReason = Literal["user-accepted", "user-rejected", "user-correction", "support-rejected", "capability-unavailable", "gate-failed", "completed", "abandoned", "no-memory"]
MemoryCorrectionDimension = Literal["work-mode", "phase-order", "primary-skill", "support-skill", "exit-gate", "matcher", "target"]
MemoryPurgeScope = Literal["history-only", "analytics-only", "candidates-only", "revisions-only", "managed-profiles-only", "all-memory-data"]


class _MemoryToolCommand:
    def __post_init__(self) -> None:
        key = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
        digest = re.compile(r"^sha256:[0-9a-f]{64}$")
        if not isinstance(self.context, RequestContext):
            raise ValueError("invalid-memory-context")
        for value in (self.context.session_id, self.context.actor, self.context.runtime_policy_snapshot_id):
            if not isinstance(value, str) or len(value) > 128 or key.fullmatch(value) is None:
                raise ValueError("invalid-memory-context")
        hints = get_type_hints(type(self))
        for item in fields(self):
            name, value = item.name, getattr(self, item.name)
            if get_origin(hints[name]) is Literal and not any(type(value) is type(choice) and value == choice for choice in get_args(hints[name])):
                raise ValueError("invalid-memory-enum")
            if name == "workspace_root" and value is not None:
                if not isinstance(value, str) or not value or len(value) > 4096 or "\x00" in value:
                    raise ValueError("invalid-workspace-root")
            if name in {"idempotency_key", "correlation_id", "workflow_run_id"}:
                if not isinstance(value, str) or key.fullmatch(value) is None:
                    raise ValueError("invalid-memory-identifier")
            prefix = {"candidate_id": "candidate", "proposal_id": "proposal", "source_revision_id": "revision", "observation_id": "observation"}.get(name)
            if prefix and (not isinstance(value, str) or re.fullmatch(prefix + r":[0-9a-f]{32}", value) is None):
                raise ValueError("invalid-memory-artifact-id")
            if name.endswith("_digest") and value is not None:
                if name == "expected_profile_digest" and value == "missing" and isinstance(self, TransitionProfileUpdate):
                    continue
                if not isinstance(value, str) or digest.fullmatch(value) is None:
                    raise ValueError("invalid-memory-digest")
            if name in {"limit", "expected_state_version"}:
                maximum = 1000 if name == "limit" else 2**31 - 1
                if type(value) is not int or not 1 <= value <= maximum:
                    raise ValueError("invalid-memory-integer")
        if isinstance(self, RecordMemoryFeedback):
            dims = self.correction_dimensions
            if len(dims) > 7 or len(set(dims)) != len(dims):
                raise ValueError("invalid-correction-dimensions")
            if self.feedback_type == "corrected":
                if not dims or not self.original_route_digest or not self.corrected_route_digest or self.original_route_digest == self.corrected_route_digest:
                    raise ValueError("correction-binding-required")
            elif dims or self.original_route_digest is not None or self.corrected_route_digest is not None:
                raise ValueError("correction-fields-forbidden")


@dataclass(frozen=True, slots=True)
class MemoryStatusQuery(_MemoryToolCommand):
    context: RequestContext
    workspace_root: str | None


@dataclass(frozen=True, slots=True)
class RememberMemoryWorkflow(_MemoryToolCommand):
    context: RequestContext
    workspace_root: str | None
    workflow_run_id: str
    target_profile_class: MemoryTarget
    risk_class: Literal["r0", "r1", "r2", "r3"]
    side_effect_outcome: Literal["none", "known-success", "known-failure", "unknown"]
    one_shot: Literal["none", "remember-once", "no-memory"]
    idempotency_key: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class RecordMemoryFeedback(_MemoryToolCommand):
    context: RequestContext
    workspace_root: str | None
    workflow_run_id: str
    observation_id: str
    feedback_type: MemoryFeedbackType
    reason_code: MemoryFeedbackReason | None
    correction_dimensions: tuple[MemoryCorrectionDimension, ...]
    original_route_digest: str | None
    corrected_route_digest: str | None
    idempotency_key: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class MemoryCandidatesQuery(_MemoryToolCommand):
    context: RequestContext
    workspace_root: str | None
    status: MemoryCandidateStatus | None
    limit: int


@dataclass(frozen=True, slots=True)
class PreviewProfileUpdate(_MemoryToolCommand):
    context: RequestContext
    workspace_root: str | None
    candidate_id: str


@dataclass(frozen=True, slots=True)
class TransitionProfileUpdate(_MemoryToolCommand):
    context: RequestContext
    workspace_root: str | None
    proposal_id: str
    expected_proposal_digest: str
    expected_profile_digest: str
    action: Literal["approve", "reject"]
    expected_state_version: int
    idempotency_key: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class RollbackProfileRevision(_MemoryToolCommand):
    context: RequestContext
    workspace_root: str | None
    source_revision_id: str
    expected_profile_digest: str
    idempotency_key: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class PurgeWorkflowMemory(_MemoryToolCommand):
    context: RequestContext
    scope: MemoryPurgeScope
    expected_summary_digest: str
    include_managed_profiles: bool
    confirmed: Literal[True]
    idempotency_key: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class MemoryStatusResult(ResultCodec):
    effective_mode: str
    personal_ceiling: str
    workspace_requested_mode: str | None
    policy_digest: str
    capture_enabled: bool
    candidate_generation_enabled: bool
    profile_promotion: str
    allowed_targets: tuple[str, ...]
    memory_store_exists: bool
    reason_codes: tuple[str, ...]
    history_summary_digest: str
    eligible_workflow_count: int
    actual_skill_consistency: str = "unavailable"
    authority_mode: str = "router-local"


@dataclass(frozen=True, slots=True)
class MemoryCandidatesResult(ResultCodec):
    candidates: tuple[dict[str, object], ...]
    truncated: bool
    authority_mode: str = "router-local"


@dataclass(frozen=True, slots=True)
class MemoryProfileResult(ResultCodec):
    status: str
    proposal: dict[str, object] | None
    revision_id: str | None = None
    revision_digest: str | None = None
    replayed: bool = False
    reason_codes: tuple[str, ...] = ()
    authority_mode: str = "router-local"
