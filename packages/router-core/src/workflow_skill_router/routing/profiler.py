from __future__ import annotations

from .models import (
    ExecutionKind,
    GoalRelation,
    RequestDecision,
    RoutingEnvelope,
    RoutingProfile,
    RuntimeMode,
    SelectionMode,
    TaskSignals,
    UserDirective,
)


def decide_request(
    goal_relation: GoalRelation,
    signals: TaskSignals,
    directive: UserDirective,
    runtime_mode: RuntimeMode,
) -> RequestDecision:
    if goal_relation is GoalRelation.STATUS:
        return RequestDecision(goal_relation, ExecutionKind.CONTROL_QUERY, None)

    if goal_relation in (GoalRelation.PROGRESS, GoalRelation.STEER):
        envelope = RoutingEnvelope.MANAGED_GOAL
        work_item_override = directive.requested_work_mode
    elif directive.requested_work_mode is not None:
        envelope = directive.requested_work_mode
        work_item_override = None
    elif (
        signals.milestone_count > 1
        or signals.resumable
        or signals.cross_repo
        or signals.dependency_dag
    ):
        envelope = RoutingEnvelope.MANAGED_GOAL
        work_item_override = None
    elif (
        signals.distinct_stages > 1
        or signals.domain_count > 1
        or signals.dependency_edges > 0
    ):
        envelope = RoutingEnvelope.PHASED
        work_item_override = None
    else:
        envelope = RoutingEnvelope.SINGLE
        work_item_override = None

    routing = RoutingProfile(
        envelope=envelope,
        work_item_envelope_override=work_item_override,
        skill_policy=(
            SelectionMode.EXPLICIT_LOCKED
            if directive.explicit_skills
            else SelectionMode.AUTO
        ),
        risk=signals.risk,
        runtime_mode=runtime_mode,
        detached_read_only=goal_relation in (
            GoalRelation.SIDE_QUESTION,
            GoalRelation.UNRELATED,
        ),
    )
    return RequestDecision(goal_relation, ExecutionKind.ROUTED_WORK, routing)


def resolve_classification_source(
    goal_relation: GoalRelation,
    directive: UserDirective,
    decision: RequestDecision,
) -> str:
    """依工作包絡的權威優先序回傳可持久化分類來源。"""
    if goal_relation in (GoalRelation.PROGRESS, GoalRelation.STEER):
        return "native-goal-binding"
    if directive.requested_work_mode is not None:
        return "caller-work-mode-hint"
    if (
        decision.routing is not None
        and decision.routing.envelope is not RoutingEnvelope.SINGLE
    ):
        return "deterministic-analyzer"
    return "builtin-fallback"
