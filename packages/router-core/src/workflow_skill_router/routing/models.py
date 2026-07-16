from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from workflow_skill_router.capabilities.models import CapabilityKind, RiskLevel


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
        return cls(None, (), None, SupportPolicy.ASK, "")


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
