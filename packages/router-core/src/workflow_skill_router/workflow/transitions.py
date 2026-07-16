from __future__ import annotations

from dataclasses import dataclass

from .events import EventDraft
from .models import PhaseRun, PhaseStatus, WorkflowRun, WorkflowStatus


WORKFLOW_EDGES = {
    ("draft", "discovering"), ("discovering", "planned"), ("planned", "running"),
    ("running", "gate-evaluating"), ("gate-evaluating", "running"),
    ("gate-evaluating", "completed"), ("awaiting-approval", "rerouting"),
    ("paused", "rerouting"), ("blocked", "rerouting"),
    ("rerouting", "planned"), ("rerouting", "running"),
}
PHASE_EDGES = {
    ("pending", "ready"), ("ready", "active"), ("active", "verifying"),
    ("verifying", "completed"), ("awaiting-approval", "rerouting"),
    ("paused", "rerouting"), ("rerouting", "ready"),
    ("verifying", "active"), ("verifying", "rerouting"), ("verifying", "failed"),
    ("pending", "skipped"), ("ready", "skipped"),
}
WAIT_TARGETS = {"awaiting-approval", "paused", "blocked"}
TERMINAL_TARGETS = {"completed", "cancelled", "failed"}


class InvalidTransition(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TransitionRequest:
    target_status: PhaseStatus | WorkflowStatus
    actor: str
    expected_state_version: int
    expected_evidence_digest: str
    expected_plan_revision: int


@dataclass(frozen=True, slots=True)
class TransitionContext:
    entry_conditions_met: bool
    route_and_lease_valid: bool
    runtime_approval_valid: bool
    unknown_side_effect: bool
    mandatory_gate_failed: bool


@dataclass(frozen=True, slots=True)
class TransitionDecision:
    target_status: PhaseStatus | WorkflowStatus
    events: tuple[EventDraft, ...]
    paused_from_status: PhaseStatus | WorkflowStatus | None
    awaiting_from_status: PhaseStatus | WorkflowStatus | None
    pause_reason: str | None


def _check_concurrency(current, request: TransitionRequest) -> None:
    if (
        current.state_version != request.expected_state_version
        or current.plan_revision != request.expected_plan_revision
        or getattr(current, "evidence_digest", request.expected_evidence_digest)
        != request.expected_evidence_digest
    ):
        raise InvalidTransition("concurrency conflict: state、plan 或 evidence 已變更")


def _actor_allowed(target: str, actor: str) -> bool:
    if target == "paused":
        return actor in {"host-adapter", "user", "system"}
    if target == "awaiting-approval":
        return actor in {"host-adapter", "router-core", "system"}
    if target == "blocked":
        return actor in {"router-core", "system"}
    if target in TERMINAL_TARGETS:
        return actor in {"agent", "router-core", "host-adapter", "system", "user"}
    return actor in {"agent", "router-core", "host-adapter", "system"}


class PhaseStateMachine:
    def decide(
        self,
        phase: PhaseRun,
        request: TransitionRequest,
        context: TransitionContext,
    ) -> TransitionDecision:
        _check_concurrency(phase, request)
        source = phase.status.value
        target = request.target_status.value
        if source in {"completed", "skipped", "failed"}:
            raise InvalidTransition("terminal Phase 不可 reopen")
        allowed = (source, target) in PHASE_EDGES
        if target in {"paused", "awaiting-approval"}:
            allowed = True
        if target == "failed":
            allowed = True
        if not allowed or not _actor_allowed(target, request.actor):
            raise InvalidTransition(f"不允許 Phase transition: {source} -> {target}")
        if target == "active" and (not context.entry_conditions_met or not context.route_and_lease_valid):
            raise InvalidTransition("Phase entry conditions 或 route/lease 無效")
        if target == "verifying" and context.unknown_side_effect:
            raise InvalidTransition("unknown side effect 不可進入 verifying")
        if target == "completed" and context.mandatory_gate_failed:
            raise InvalidTransition("mandatory gate 失敗不可完成")
        if target == "active" and not context.runtime_approval_valid:
            raise InvalidTransition("runtime approval 無效")
        paused = phase.status if target == "paused" else phase.paused_from_status
        awaiting = phase.status if target == "awaiting-approval" else phase.awaiting_from_status
        event = EventDraft(
            event_type="PHASE_STATUS_TRANSITIONED",
            actor=request.actor,
            plan_revision=phase.plan_revision,
            inline_payload={
                "phase_id": phase.phase_id,
                "from": source,
                "to": target,
                "evidence_digest": phase.evidence_digest,
            },
            payload_ref=None,
            correlation_id=f"phase:{phase.phase_id}",
            causation_id=None,
        )
        return TransitionDecision(request.target_status, (event,), paused, awaiting, None)


class WorkflowStateMachine:
    def decide(
        self,
        workflow: WorkflowRun,
        request: TransitionRequest,
        context: TransitionContext,
    ) -> TransitionDecision:
        _check_concurrency(workflow, request)
        source = workflow.status.value
        target = request.target_status.value
        if source in {"completed", "cancelled", "failed"}:
            raise InvalidTransition("terminal Workflow 不可 reopen")
        allowed = (source, target) in WORKFLOW_EDGES
        if target in WAIT_TARGETS or target in {"cancelled", "failed"}:
            allowed = True
        if not allowed or not _actor_allowed(target, request.actor):
            raise InvalidTransition(f"不允許 Workflow transition: {source} -> {target}")
        if target == "completed" and context.mandatory_gate_failed:
            raise InvalidTransition("mandatory gate 失敗不可完成")
        paused = workflow.status if target == "paused" else workflow.paused_from_status
        awaiting = workflow.status if target == "awaiting-approval" else workflow.awaiting_from_status
        event = EventDraft(
            workflow_run_id=workflow.workflow_run_id,
            event_type="WORKFLOW_STATUS_TRANSITIONED",
            actor=request.actor,
            plan_revision=workflow.plan_revision,
            inline_payload={"from": source, "to": target},
            payload_ref=None,
            correlation_id=f"workflow:{workflow.workflow_run_id}",
            causation_id=None,
        )
        return TransitionDecision(request.target_status, (event,), paused, awaiting, None)
