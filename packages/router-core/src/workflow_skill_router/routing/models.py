from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from workflow_skill_router.capabilities.models import RiskLevel


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

