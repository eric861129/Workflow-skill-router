from __future__ import annotations

from dataclasses import dataclass

from workflow_skill_router.routing.models import RoutingEnvelope


@dataclass(frozen=True, slots=True)
class GoalBinding:
    goal_binding_id: str
    host_goal_id: str | None
    goal_revision: int
    host_goal_revision: str | None
    objective_digest: str
    objective_snapshot: str
    status_snapshot: str
    budget_snapshot: str | None
    synced_at: str
    source: str


@dataclass(frozen=True, slots=True)
class AcceptanceCoverage:
    criterion_id: str
    source_digest: str
    mandatory: bool
    work_item_ids: tuple[str, ...]
    gate_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    status: str


@dataclass(frozen=True, slots=True)
class WorkItem:
    work_item_id: str
    milestone_id: str
    title: str
    required: bool
    status: str
    envelope: RoutingEnvelope
    dependency_ids: tuple[str, ...]
    read_resources: tuple[str, ...]
    write_resources: tuple[str, ...]
    scope: tuple[str, ...]
    skill_policy_ref: str
    phase_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkGraph:
    work_graph_id: str
    goal_binding_id: str
    objective_digest: str
    plan_revision: int
    acceptance_coverage_ref: str
    items: tuple[WorkItem, ...]

