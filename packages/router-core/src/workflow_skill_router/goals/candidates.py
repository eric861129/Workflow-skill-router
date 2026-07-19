from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from typing import Protocol

from workflow_skill_router.routing.models import RoutingEnvelope
from workflow_skill_router.schemas.artifacts import canonical_json

from .models import GoalBinding


@dataclass(frozen=True, slots=True)
class CandidateRequest:
    workflow_run_id: str
    objective_digest: str
    envelope: RoutingEnvelope
    plan_revision: int
    workflow_state_version: int
    capability_snapshot_id: str


@dataclass(frozen=True, slots=True)
class AcceptanceCompletionRecord:
    gate_id: str
    mandatory: bool
    status: str
    evidence_refs: tuple[str, ...]
    evidence_digest: str
    plan_revision: int
    workflow_state_version: int


@dataclass(frozen=True, slots=True)
class ExplicitCoverageCompletionRecord:
    capability_id: str
    scope_anchor_id: str
    required: bool
    status: str
    disposition_refs: tuple[str, ...]
    activation_evidence_refs: tuple[str, ...]
    coverage_digest: str
    plan_revision: int
    workflow_state_version: int


@dataclass(frozen=True, slots=True)
class SideEffectCompletionRecord:
    action_digest: str
    status: str
    outcome_receipt_ref: str | None
    outcome_digest: str
    plan_revision: int
    workflow_state_version: int


@dataclass(frozen=True, slots=True)
class PendingApprovalRecord:
    approval_id: str
    capability_id: str
    scope_anchor_id: str
    action_digest: str
    status: str
    request_digest: str


@dataclass(frozen=True, slots=True)
class Blocker:
    category: str
    target: str
    required_authority: str
    dependency_digest: str

    @property
    def identity(self) -> tuple[str, str, str, str]:
        return (
            self.category,
            self.target,
            self.required_authority,
            self.dependency_digest,
        )


@dataclass(frozen=True, slots=True)
class CompletionEvidenceSnapshot:
    request: CandidateRequest
    acceptance_records: tuple[AcceptanceCompletionRecord, ...]
    explicit_coverage_records: tuple[ExplicitCoverageCompletionRecord, ...]
    side_effect_records: tuple[SideEffectCompletionRecord, ...]
    unresolved_blockers: tuple[Blocker, ...]
    pending_approvals: tuple[PendingApprovalRecord, ...]
    acceptance_coverage_digest: str | None
    explicit_skill_coverage_digest: str | None
    evidence_digest: str | None
    side_effect_outcome_digest: str | None


class CompletionEvidenceRepository(Protocol):
    def load(self, request: CandidateRequest) -> CompletionEvidenceSnapshot: ...


@dataclass(frozen=True, slots=True)
class WorkflowCompletionCandidate:
    candidate_id: str
    input: CompletionEvidenceSnapshot
    generated_at: str


@dataclass(frozen=True, slots=True)
class GoalStatusCandidate:
    candidate_id: str
    candidate_type: str
    goal_binding_id: str
    host_goal_id: str | None
    host_goal_revision: str | None
    goal_revision: int
    objective_digest: str
    workflow_candidate_id: str | None
    evidence_digest: str
    generated_at: str


@dataclass(frozen=True, slots=True)
class BlockedAudit:
    blocker_identity: tuple[str, str, str, str] | None = None
    consecutive_goal_turns: int = 0
    alternatives_exhausted: bool = False
    runnable_required_work: bool = False

    def observe(
        self,
        blocker: Blocker,
        relation: str,
        alternatives_exhausted: bool,
        runnable_required_work: bool,
    ) -> "BlockedAudit":
        countable = relation in {"progress", "steer"}
        if not countable:
            return self
        same = self.blocker_identity == blocker.identity
        turns = self.consecutive_goal_turns + 1 if same else 1
        return BlockedAudit(
            blocker.identity,
            turns,
            alternatives_exhausted,
            runnable_required_work,
        )

    @property
    def eligible(self) -> bool:
        return (
            self.consecutive_goal_turns >= 3
            and self.alternatives_exhausted
            and not self.runnable_required_work
        )


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(
        canonical_json({"records": value}).encode("utf-8")
    ).hexdigest()


def _record_documents(records: tuple[object, ...]) -> list[dict[str, object]]:
    return [asdict(item) for item in records]


def _aggregate_digests(snapshot: CompletionEvidenceSnapshot) -> tuple[str, str, str, str]:
    acceptance = _digest(_record_documents(snapshot.acceptance_records))
    explicit = _digest(_record_documents(snapshot.explicit_coverage_records))
    evidence_refs = {
        "acceptance": [
            ref for item in snapshot.acceptance_records for ref in item.evidence_refs
        ],
        "activation": [
            ref
            for item in snapshot.explicit_coverage_records
            for ref in item.activation_evidence_refs
        ],
    }
    evidence = _digest(evidence_refs)
    side_effect = _digest(_record_documents(snapshot.side_effect_records))
    return acceptance, explicit, evidence, side_effect


class CandidateFactory:
    def __init__(self, evidence_repository: CompletionEvidenceRepository, *, clock=None) -> None:
        self._evidence = evidence_repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def workflow_complete(
        self,
        request: CandidateRequest,
    ) -> WorkflowCompletionCandidate | None:
        snapshot = self._evidence.load(request)
        if snapshot.request != request:
            return None
        stored = (
            snapshot.acceptance_coverage_digest,
            snapshot.explicit_skill_coverage_digest,
            snapshot.evidence_digest,
            snapshot.side_effect_outcome_digest,
        )
        if any(value is None for value in stored) or stored != _aggregate_digests(snapshot):
            return None
        if snapshot.unresolved_blockers or snapshot.pending_approvals:
            return None
        for item in snapshot.acceptance_records:
            if (
                item.plan_revision != request.plan_revision
                or item.workflow_state_version != request.workflow_state_version
                or (item.mandatory and (item.status != "passed" or not item.evidence_refs))
            ):
                return None
        for item in snapshot.explicit_coverage_records:
            valid_status = item.status in {"satisfied", "waived-by-user"}
            if (
                item.plan_revision != request.plan_revision
                or item.workflow_state_version != request.workflow_state_version
                or (item.required and not valid_status)
                or (item.required and not item.disposition_refs)
                or (item.required and not item.activation_evidence_refs)
            ):
                return None
        for item in snapshot.side_effect_records:
            if (
                item.plan_revision != request.plan_revision
                or item.workflow_state_version != request.workflow_state_version
                or item.status != "confirmed-success"
                or item.outcome_receipt_ref is None
            ):
                return None
        candidate_id = "workflow-candidate:" + _digest({
            "request": asdict(request),
            "digests": stored,
        }).removeprefix("sha256:")
        generated = self._clock().astimezone(timezone.utc).isoformat()
        return WorkflowCompletionCandidate(candidate_id, snapshot, generated)


def goal_complete(
    binding: GoalBinding,
    workflow_candidate: WorkflowCompletionCandidate,
) -> GoalStatusCandidate | None:
    request = workflow_candidate.input.request
    if request.objective_digest != binding.objective_digest:
        return None
    evidence_digest = workflow_candidate.input.evidence_digest
    if evidence_digest is None:
        return None
    identity = {
        "goal_binding_id": binding.goal_binding_id,
        "goal_revision": binding.goal_revision,
        "host_goal_revision": binding.host_goal_revision,
        "workflow_candidate_id": workflow_candidate.candidate_id,
        "evidence_digest": evidence_digest,
    }
    return GoalStatusCandidate(
        "goal-candidate:" + _digest(identity).removeprefix("sha256:"),
        "complete",
        binding.goal_binding_id,
        binding.host_goal_id,
        binding.host_goal_revision,
        binding.goal_revision,
        binding.objective_digest,
        workflow_candidate.candidate_id,
        evidence_digest,
        workflow_candidate.generated_at,
    )


def blocked_candidate(
    binding: GoalBinding,
    audit: BlockedAudit,
    blocker: Blocker,
    *,
    generated_at: str,
) -> GoalStatusCandidate | None:
    if not audit.eligible or audit.blocker_identity != blocker.identity:
        return None
    evidence_digest = _digest({"blocker": blocker.identity, "turns": audit.consecutive_goal_turns})
    return GoalStatusCandidate(
        "goal-candidate:" + evidence_digest.removeprefix("sha256:"),
        "blocked",
        binding.goal_binding_id,
        binding.host_goal_id,
        binding.host_goal_revision,
        binding.goal_revision,
        binding.objective_digest,
        None,
        evidence_digest,
        generated_at,
    )
