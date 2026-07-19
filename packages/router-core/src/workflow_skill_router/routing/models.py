from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol, TYPE_CHECKING

from workflow_skill_router.capabilities.models import Availability, CapabilityKind, RiskLevel

if TYPE_CHECKING:
    from .authority import SelectionOrigin


class GoalRelation(StrEnum):
    NONE = "none"
    PROGRESS = "progress"
    STEER = "steer"
    STATUS = "status"
    SIDE_QUESTION = "side-question"
    UNRELATED = "unrelated"


class ExecutionKind(StrEnum):
    CONTROL_QUERY = "control-query"
    ROUTED_WORK = "routed-work"


class RoutingEnvelope(StrEnum):
    SINGLE = "single"
    PHASED = "phased"
    MANAGED_GOAL = "managed-goal"


class RuntimeMode(StrEnum):
    SKILL_ONLY = "skill-only"
    HYBRID = "hybrid"


class SelectionMode(StrEnum):
    AUTO = "auto"
    EXPLICIT_LOCKED = "explicit-locked"


class ExplicitSemantics(StrEnum):
    PREFERRED_PRIMARY = "preferred-primary"
    ALLOWED_SET = "allowed-set"
    REQUIRED_ALL = "required-all"


class SupportPolicy(StrEnum):
    AUTO = "auto"
    ASK = "ask"
    FORBID = "forbid"


class ScopeKind(StrEnum):
    WORKFLOW = "workflow"
    WORK_ITEM = "work-item"
    PHASE = "phase"
    TASK = "task"


class SkillDisposition(StrEnum):
    ACTIVE_REQUIRED = "active-required"
    ACTIVE_PRIMARY = "active-primary"
    ACTIVE_SUPPORT = "active-support"
    ALLOWED_NOT_SELECTED = "allowed-not-selected"
    NOT_APPLICABLE = "not-applicable"
    REJECTED = "rejected"


class CoverageStatus(StrEnum):
    SATISFIED = "satisfied"
    UNCOVERED = "uncovered"
    WAIVED = "waived"
    NOT_APPLICABLE = "not-applicable"


class OutcomeMode(StrEnum):
    COMPLETE = "complete"
    LIMITED = "limited"
    BLOCKED = "blocked"


class ActivationBindingKind(StrEnum):
    INSTRUCTION_CONTENT = "instruction-content"
    TOOL_SCHEMA = "tool-schema"
    RUNTIME_CONTRACT = "runtime-contract"


@dataclass(frozen=True, slots=True)
class DirectiveInput:
    text: str
    explicit_skill_ids: tuple[str, ...] = ()
    skill_semantics_hint: str | None = None
    requested_work_mode_hint: str | None = None


@dataclass(frozen=True, slots=True)
class UserDirective:
    requested_work_mode: RoutingEnvelope | None
    explicit_skills: tuple[str, ...]
    explicit_semantics: ExplicitSemantics | None
    support_policy: SupportPolicy
    source_text: str

    @classmethod
    def auto(cls) -> "UserDirective":
        return cls(None, (), None, SupportPolicy.AUTO, "")


@dataclass(frozen=True, slots=True)
class TaskSignals:
    intent_count: int = 1
    domain_count: int = 1
    distinct_stages: int = 1
    milestone_count: int = 1
    dependency_edges: int = 0
    resumable: bool = False
    cross_repo: bool = False
    dependency_dag: bool = False
    risk: RiskLevel = RiskLevel.R0

    def __post_init__(self) -> None:
        for name in (
            "intent_count", "domain_count", "distinct_stages", "milestone_count",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} 必須大於等於 1")
        if self.dependency_edges < 0:
            raise ValueError("dependency_edges 不可小於 0")

    @classmethod
    def small(cls) -> "TaskSignals":
        return cls()

    @classmethod
    def large(cls) -> "TaskSignals":
        return cls(milestone_count=2, resumable=True, dependency_dag=True)


@dataclass(frozen=True, slots=True)
class RoutingProfile:
    envelope: RoutingEnvelope
    work_item_envelope_override: RoutingEnvelope | None
    skill_policy: SelectionMode
    risk: RiskLevel
    runtime_mode: RuntimeMode
    detached_read_only: bool = False


@dataclass(frozen=True, slots=True)
class RequestDecision:
    goal_relation: GoalRelation
    execution_kind: ExecutionKind
    routing: RoutingProfile | None


@dataclass(frozen=True, slots=True)
class ScopeAnchor:
    scope_anchor_id: str
    kind: ScopeKind
    aggregate_id: str
    parent_scope_anchor_id: str | None
    semantic_scope_digest: str
    lineage_root_id: str
    stable_scope_key: str
    created_revision: int


@dataclass(frozen=True, slots=True)
class SkillConstraint:
    skill_id: str
    purpose: str


@dataclass(frozen=True, slots=True)
class SkillSelectionPolicy:
    mode: SelectionMode
    explicit_skill_ids: tuple[str, ...]
    explicit_semantics: ExplicitSemantics | None
    support_policy: SupportPolicy
    approved_support_refs: tuple[str, ...]
    rejected_support_refs: tuple[str, ...]
    consent_scope: ScopeKind
    lock_scope: ScopeKind
    scope_anchor_id: str
    plan_revision: int

    def __post_init__(self) -> None:
        if self.plan_revision < 1:
            raise ValueError("plan_revision 必須大於等於 1")
        if self.mode is SelectionMode.AUTO and self.support_policy is not SupportPolicy.AUTO:
            raise ValueError("auto policy 必須使用自動輔助 Skill 政策")
        if self.mode is SelectionMode.EXPLICIT_LOCKED and self.support_policy is SupportPolicy.AUTO:
            raise ValueError("explicit-locked policy 不得自動加入輔助 Skill")
        if self.mode is SelectionMode.AUTO:
            if self.explicit_skill_ids or self.explicit_semantics is not None:
                raise ValueError("auto policy 不可包含 explicit SKILL")
        elif not self.explicit_skill_ids or self.explicit_semantics is None:
            raise ValueError("explicit-locked policy 必須包含技能與語意")
        if len(set(self.explicit_skill_ids)) != len(self.explicit_skill_ids):
            raise ValueError("explicit_skill_ids 不可重複")


@dataclass(frozen=True, slots=True)
class ExplicitSkillDisposition:
    skill_id: str
    scope_anchor_id: str
    disposition: SkillDisposition
    route_ref: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class ExplicitSkillCoverage:
    skill_id: str
    scope_anchor_id: str
    status: CoverageStatus
    evidence_refs: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class SupportProposal:
    proposal_id: str
    capability_id: str
    capability_fingerprint: str
    capability_kind: CapabilityKind
    purpose: str
    role: str
    scope: ScopeKind
    scope_anchor_id: str
    work_item_id: str
    phase_id: str
    goal_binding_id: str | None
    goal_revision: int | None
    plan_revision: int
    context_fingerprint: str
    actor: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ConsentGrant:
    grant_id: str
    capability_id: str
    capability_fingerprint: str
    capability_kind: CapabilityKind
    purpose: str
    role: str
    scope: ScopeKind
    scope_anchor_id: str
    work_item_id: str
    phase_id: str
    goal_binding_id: str | None
    goal_revision: int | None
    plan_revision: int
    context_fingerprint: str
    actor: str
    granted_at: datetime
    expires_at: datetime

    @classmethod
    def from_proposal(
        cls,
        proposal: SupportProposal,
        *,
        grant_id: str,
        scope: ScopeKind,
        scope_anchor_id: str,
        actor: str,
        granted_at: datetime,
        expires_at: datetime,
    ) -> "ConsentGrant":
        return cls(
            grant_id,
            proposal.capability_id,
            proposal.capability_fingerprint,
            proposal.capability_kind,
            proposal.purpose,
            proposal.role,
            scope,
            scope_anchor_id,
            proposal.work_item_id,
            proposal.phase_id,
            proposal.goal_binding_id,
            proposal.goal_revision,
            proposal.plan_revision,
            proposal.context_fingerprint,
            actor,
            granted_at,
            expires_at,
        )


@dataclass(frozen=True, slots=True)
class ConsentRejection:
    rejection_id: str
    capability_id: str
    capability_fingerprint: str
    capability_kind: CapabilityKind
    purpose: str
    role: str
    scope: ScopeKind
    scope_anchor_id: str
    work_item_id: str
    phase_id: str
    goal_binding_id: str | None
    goal_revision: int | None
    plan_revision: int
    context_fingerprint: str
    actor: str
    rejected_at: datetime

    @classmethod
    def from_proposal(
        cls,
        proposal: SupportProposal,
        *,
        rejection_id: str,
        actor: str,
        rejected_at: datetime,
    ) -> "ConsentRejection":
        return cls(
            rejection_id,
            proposal.capability_id,
            proposal.capability_fingerprint,
            proposal.capability_kind,
            proposal.purpose,
            proposal.role,
            proposal.scope,
            proposal.scope_anchor_id,
            proposal.work_item_id,
            proposal.phase_id,
            proposal.goal_binding_id,
            proposal.goal_revision,
            proposal.plan_revision,
            proposal.context_fingerprint,
            actor,
            rejected_at,
        )


@dataclass(frozen=True, slots=True)
class ConsentDecision:
    allowed: bool
    code: str
    grant_ref: str | None
    should_prompt: bool


@dataclass(frozen=True, slots=True)
class CapabilitySelection:
    capability_id: str
    capability_fingerprint: str
    selection_origin: "SelectionOrigin"
    authority_ref: str
    policy_digest: str
    purpose: str
    consent_grant_ref: str | None


@dataclass(frozen=True, slots=True)
class Route:
    route_id: str
    workflow_run_id: str
    work_item_id: str
    phase_id: str
    envelope: RoutingEnvelope
    capability_snapshot_id: str
    primary_selection: CapabilitySelection
    support_selections: tuple[CapabilitySelection, ...]
    skill_policy_revision: int
    explicit_skill_dispositions: tuple[ExplicitSkillDisposition, ...]
    explicit_skill_coverage_ref: str | None
    consent_grant_refs: tuple[str, ...]
    risk: RiskLevel
    context_cost: int
    validation_status: str
    validation_reasons: tuple[str, ...]
    created_at: str


@dataclass(frozen=True, slots=True)
class LeaseActivationBinding:
    kind: str
    trusted_digest: str


@dataclass(frozen=True, slots=True)
class LeaseCapability:
    capability_id: str
    capability_kind: CapabilityKind
    capability_fingerprint: str
    selection_origin: "SelectionOrigin"
    authority_ref: str
    policy_digest: str
    purpose: str
    consent_grant_ref: str | None
    activation_binding: LeaseActivationBinding


@dataclass(frozen=True, slots=True)
class ExecutionLease:
    lease_id: str
    workflow_run_id: str
    phase_id: str
    scope_anchor_id: str
    route_id: str
    capability_snapshot_id: str
    policy_revision: int
    state_version: int
    runtime_policy_snapshot_id: str
    action_digest: str
    runtime_approval_ref: str | None
    runtime_approval_scope_digest: str | None
    content_preflight_policy_digest: str
    allowed_capabilities: tuple[LeaseCapability, ...]
    issued_at: str
    expires_at: str
    max_activations: int
    activation_mode: str


@dataclass(frozen=True, slots=True)
class InvocationContext:
    scope_anchor_id: str
    purpose: str
    actor: str
    session_id: str
    runtime_policy_snapshot_id: str
    context_digest: str


@dataclass(frozen=True, slots=True)
class LeaseConsumptionRequest:
    lease_id: str
    capability_id: str
    capability_fingerprint: str
    scope_anchor_id: str
    purpose: str
    invocation_context_digest: str
    activation_binding_kind: str
    observed_binding_digest: str
    action_digest: str
    runtime_approval_ref: str | None
    runtime_approval_scope_digest: str | None
    state_version: int
    invocation_nonce: str


@dataclass(frozen=True, slots=True)
class LeaseConsumptionReceipt:
    lease_id: str
    invocation_digest: str
    reservation_digest: str
    consumption_version: int
    consumed_at: str


class LeaseConsumptionPort(Protocol):
    def compare_and_consume(
        self,
        request: LeaseConsumptionRequest,
        expected_consumption_version: int = 0,
    ) -> LeaseConsumptionReceipt: ...


@dataclass(frozen=True, slots=True)
class InvocationDecision:
    allowed: bool
    reason: str
    receipt: LeaseConsumptionReceipt | None


@dataclass(frozen=True, slots=True)
class VerifiedRuntimeApproval:
    approval_ref: str
    scope_digest: str
    action_digest: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class RouteValidationRequest:
    route_id: str
    workflow_run_id: str
    work_item_id: str
    phase_id: str
    scope_anchor_id: str
    envelope: RoutingEnvelope
    capability_snapshot_id: str
    primary_selection: CapabilitySelection
    support_selections: tuple[CapabilitySelection, ...]
    explicit_skill_dispositions: tuple[ExplicitSkillDisposition, ...]
    explicit_skill_coverage_ref: str | None
    consent_grant_refs: tuple[str, ...]
    risk: RiskLevel
    action_digest: str
    state_version: int
    purpose: str
    outcome_mode: OutcomeMode
    exit_gate: str | None


@dataclass(frozen=True, slots=True)
class ValidationContext:
    now: datetime
    runtime_mode: RuntimeMode
    runtime_policy_snapshot_id: str
    runtime_policy_digest: str
    actor: str
    session_id: str
    verified_authority_refs: tuple[str, ...]
    consent_grant_refs: tuple[str, ...]
    runtime_approval: VerifiedRuntimeApproval | None
    instruction_content_bindings: tuple[tuple[str, str], ...]
    runtime_contract_bindings: tuple[tuple[str, str, str], ...]
    content_preflight_policy_digest: str
    allowed_availability: tuple[Availability, ...]
    instruction_body_opens: list[str] = field(default_factory=list, compare=False)


@dataclass(frozen=True, slots=True)
class RouteViolation:
    code: str
    capability_id: str | None
    detail: str


@dataclass(frozen=True, slots=True)
class RouteValidationResult:
    valid: bool
    violations: tuple[RouteViolation, ...]
    requires_runtime_approval: bool
    route: Route | None
    lease: ExecutionLease | None
    outcome_mode: OutcomeMode
    exit_gate: str | None
