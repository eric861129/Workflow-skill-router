from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from workflow_skill_router.routing.models import Route, RoutingEnvelope


class WorkflowStatus(StrEnum):
    DRAFT = "draft"
    DISCOVERING = "discovering"
    PLANNED = "planned"
    RUNNING = "running"
    GATE_EVALUATING = "gate-evaluating"
    REROUTING = "rerouting"
    AWAITING_APPROVAL = "awaiting-approval"
    PAUSED = "paused"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class PhaseStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    ACTIVE = "active"
    VERIFYING = "verifying"
    REROUTING = "rerouting"
    AWAITING_APPROVAL = "awaiting-approval"
    PAUSED = "paused"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class WorkflowRun:
    workflow_run_id: str
    parent_workflow_run_id: str | None
    objective: str
    objective_digest: str
    scope: tuple[str, ...]
    constraints: tuple[str, ...]
    envelope: RoutingEnvelope
    status: WorkflowStatus
    plan_revision: int
    capability_snapshot_id: str
    current_phase_id: str | None
    paused_from_status: WorkflowStatus | None
    awaiting_from_status: WorkflowStatus | None
    pause_reason: str | None
    state_version: int


@dataclass(frozen=True, slots=True)
class RoutingQuery:
    objective_digest: str
    phase_purpose: str
    required_outputs: tuple[str, ...]
    risk: str


@dataclass(frozen=True, slots=True)
class ExitGate:
    gate_id: str
    mandatory_checks: tuple[str, ...]
    evidence_requirements: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PhaseRun:
    phase_id: str
    workflow_run_id: str
    work_item_id: str
    name: str
    status: PhaseStatus
    routing_query: RoutingQuery
    route: Route | None
    capability_snapshot_id: str
    risk: str
    entry_conditions: tuple[str, ...]
    exit_gate: ExitGate
    evidence_refs: tuple[str, ...]
    inserted: bool
    sequence_source: str
    plan_revision: int
    state_version: int
    evidence_digest: str
    supersedes_phase_id: str | None
    paused_from_status: PhaseStatus | None
    awaiting_from_status: PhaseStatus | None
    pause_reason: str | None


@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: str
    workflow_run_id: str
    phase_id: str
    evidence_type: str
    content_digest: str
    workspace_revision: str
    produced_at: str
    producer: str
    sensitivity: str

