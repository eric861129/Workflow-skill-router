from __future__ import annotations

from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from workflow_skill_router.local_work import (
    append_local_transition,
    LocalWorkItem,
    LocalWorkGraphCorruption,
    build_local_work_items,
    expected_local_check_ids,
    local_evidence_digest,
    local_transition_target,
    next_ready_local_work_item,
    persist_local_work_graph,
    replay_local_transition,
    validate_local_work_graph,
)
from workflow_skill_router.persistence.migrator import migrate
from workflow_skill_router.persistence.sqlite_store import (
    ConcurrencyConflict,
    IdempotencyConflict,
)
from workflow_skill_router.profiles.contract import is_canonical_skill_id
from workflow_skill_router.profiles.resolver import RoutingMatchContext, resolve_profile_route
from workflow_skill_router.profiles.storage import RoutingProfileRepository
from workflow_skill_router.routing.directives import resolve_directive
from workflow_skill_router.routing.consent import ConsentPolicyError
from workflow_skill_router.routing.models import (
    DirectiveInput,
    GoalRelation,
    RuntimeMode,
)
from workflow_skill_router.routing.profiler import (
    decide_request,
    resolve_classification_source,
)
from workflow_skill_router.routing.task_signal_analyzer import analyze_task_signals
from workflow_skill_router.schemas.artifacts import canonical_json
from workflow_skill_router.runtime_readiness import CapabilityUnavailable
from workflow_skill_router.service_models import (
    ClassificationDecisionView,
    EvaluateGateResult,
    LocalRecordWorkEventResult,
    PlannedSkillPhase,
    PlanWorkResult,
    NextWorkResult,
    RouterStatusView,
    SupportConsentResult,
)
from workflow_skill_router.workflow.local_observations import (
    LOCAL_PROGRESS_TRANSITIONS,
    LocalObservationPolicyError,
    LocalProgressObservation,
)


LOCAL_RUNTIME_MODE = "mcp-local-control-plane"
_ROUTING_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_id(prefix: str, session_id: str, idempotency_key: str) -> str:
    identity = hashlib.sha256(
        f"{session_id}\0{idempotency_key}".encode("utf-8")
    ).hexdigest()[:32]
    return f"{prefix}:{identity}"


def _legacy_plan_request_digest(command, directive, objective_digest: str) -> str:
    """Recreate the beta.1 request digest for idempotent plan replay."""

    document = {
        "actor": command.context.actor,
        "correlation_id": command.correlation_id,
        "explicit_semantics": (
            None if directive.explicit_semantics is None
            else directive.explicit_semantics.value
        ),
        "explicit_skill_ids": list(directive.explicit_skills),
        "goal_binding_id": command.goal_binding_id,
        "objective_digest": objective_digest,
        "requested_work_mode": command.requested_work_mode,
        "runtime_policy_snapshot_id": command.context.runtime_policy_snapshot_id,
        "session_id": command.context.session_id,
    }
    return _digest(canonical_json(document))


def _is_default_routing_context(routing_context) -> bool:
    return (
        routing_context.workspace_root is None
        and not routing_context.domains
        and not routing_context.tags
        and routing_context.current_phase_id is None
    )


class LocalControlPlaneService:
    """提供可持久化的 R0 規劃；需主機驗證的執行能力維持關閉。"""

    runtime_profile = "bundled-local-r0"

    def __init__(self, database: Path) -> None:
        self._database = database
        migrate(database)

    def plan_work(self, command) -> PlanWorkResult:
        objective = command.objective.strip()
        if not objective:
            raise ValueError("objective 不得為空")
        if command.expected_state_version != 0:
            raise ConcurrencyConflict(
                f"expected={command.expected_state_version}, actual=0"
            )

        directive = resolve_directive(DirectiveInput(
            text=objective,
            explicit_skill_ids=command.explicit_skill_ids,
            skill_semantics_hint=command.explicit_semantics,
            requested_work_mode_hint=command.requested_work_mode,
        ))
        if command.requested_work_mode is None:
            directive = replace(directive, requested_work_mode=None)
        routing_context = command.routing_context
        for field_name, values in (
            ("domains", routing_context.domains),
            ("tags", routing_context.tags),
        ):
            if len(values) > 32 or len(set(values)) != len(values):
                raise ValueError(f"routing_context.{field_name} 必須唯一且最多 32 項")
            if any(
                not isinstance(value, str)
                or _ROUTING_IDENTIFIER.fullmatch(value) is None
                for value in values
            ):
                raise ValueError(f"routing_context.{field_name} 含有無效識別值")
        if routing_context.current_phase_id is not None and (
            not isinstance(routing_context.current_phase_id, str)
            or _ROUTING_IDENTIFIER.fullmatch(routing_context.current_phase_id) is None
        ):
            raise ValueError("routing_context.current_phase_id 格式無效")

        analysis = analyze_task_signals(
            objective,
            trusted_domains=routing_context.domains,
            trusted_tags=routing_context.tags,
        )
        goal_relation = (
            GoalRelation.PROGRESS
            if command.goal_binding_id is not None
            else GoalRelation.NONE
        )
        decision = decide_request(
            goal_relation,
            analysis.signals,
            directive,
            RuntimeMode.SKILL_ONLY,
        )
        if decision.routing is None:
            raise RuntimeError("planning-routing-profile-unavailable")

        routing_envelope = decision.routing.envelope.value
        classification_source = resolve_classification_source(
            goal_relation,
            directive,
            decision,
        )
        route_source = "builtin-default"
        routing_profile_ids: tuple[str, ...] = ()
        routing_profile_digest = None
        matched_profile_rule_id = None
        planned_skill_tree: tuple[PlannedSkillPhase, ...] = ()
        profile_warnings: tuple[str, ...] = ()
        activation_status = "not-planned"
        planned_skill_ids = directive.explicit_skills

        if directive.explicit_skills:
            route_source = "user-explicit"
            activation_status = "intended-unverified"
        else:
            workspace_root = (
                None
                if routing_context.workspace_root is None
                else Path(routing_context.workspace_root)
            )
            profiles = RoutingProfileRepository(self._database.parent).load_layers(
                workspace_root=workspace_root
            )
            resolved = resolve_profile_route(
                profiles,
                objective=objective,
                default_work_mode=routing_envelope,
                context=RoutingMatchContext(
                    domains=routing_context.domains,
                    tags=routing_context.tags,
                    current_phase_id=routing_context.current_phase_id,
                    lock_work_mode=(
                        command.requested_work_mode is not None
                        or command.goal_binding_id is not None
                    ),
                ),
            )
            if resolved is not None:
                if resolved.work_mode != routing_envelope:
                    classification_source = "profile-route"
                routing_envelope = resolved.work_mode
                route_source = resolved.route_source
                routing_profile_ids = resolved.applied_profile_ids
                routing_profile_digest = resolved.profile_digest
                matched_profile_rule_id = resolved.matched_rule_id
                planned_skill_ids = resolved.current_skill_ids
                planned_skill_tree = tuple(
                    PlannedSkillPhase(
                        phase.phase_id,
                        phase.primary_skill_id,
                        phase.support_skill_ids,
                        phase.exit_gate,
                    )
                    for phase in resolved.skill_tree
                )
                activation_status = resolved.activation_status

        workflow_run_id = _stable_id(
            "workflow",
            command.context.session_id,
            command.idempotency_key,
        )
        work_graph_id = _stable_id(
            "work-graph",
            command.context.session_id,
            command.idempotency_key,
        )
        objective_digest = _digest(objective)
        request_document = {
            "actor": command.context.actor,
            "correlation_id": command.correlation_id,
            "explicit_semantics": (
                None if directive.explicit_semantics is None
                else directive.explicit_semantics.value
            ),
            "explicit_skill_ids": list(directive.explicit_skills),
            "goal_binding_id": command.goal_binding_id,
            "objective_digest": objective_digest,
            "requested_work_mode": command.requested_work_mode,
            "routing_context": {
                "current_phase_id": routing_context.current_phase_id,
                "domains": list(routing_context.domains),
                "tags": list(routing_context.tags),
                "workspace_root_digest": (
                    None
                    if routing_context.workspace_root is None
                    else _digest(str(Path(routing_context.workspace_root).expanduser().resolve()))
                ),
            },
            "runtime_policy_snapshot_id": command.context.runtime_policy_snapshot_id,
            "session_id": command.context.session_id,
        }
        request_digest = _digest(canonical_json(request_document))
        support_consent_required = False
        created_at = datetime.now(UTC).isoformat()
        local_work_items = build_local_work_items(
            workflow_run_id=workflow_run_id,
            work_graph_id=work_graph_id,
            routing_envelope=routing_envelope,
            goal_binding_id=command.goal_binding_id,
            planned_skill_tree=planned_skill_tree,
            planned_skill_ids=planned_skill_ids,
        )

        with closing(sqlite3.connect(self._database, timeout=30.0)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM local_control_plans "
                "WHERE session_id=? AND idempotency_key=?",
                (command.context.session_id, command.idempotency_key),
            ).fetchone()
            if existing is not None:
                try:
                    if existing["request_digest"] != request_digest:
                        legacy_digest = _legacy_plan_request_digest(
                            command, directive, objective_digest
                        )
                        if (
                            not _is_default_routing_context(routing_context)
                            or existing["request_digest"] != legacy_digest
                        ):
                            raise IdempotencyConflict(
                                "相同 idempotency key 不得對應不同規劃請求"
                            )
                    if existing["actor"] != command.context.actor:
                        raise LocalWorkGraphCorruption(
                            "local-work-graph-corruption: plan-actor"
                        )
                    if int(existing["local_work_graph_version"]) == 0:
                        existing_count = connection.execute(
                            "SELECT COUNT(*) FROM local_work_items WHERE workflow_run_id=?",
                            (existing["workflow_run_id"],),
                        ).fetchone()
                        if existing_count is None or int(existing_count[0]) != 0:
                            raise LocalWorkGraphCorruption(
                                "local-work-graph-corruption: legacy-marker"
                            )
                        legacy_items = self._expected_local_work_items(existing)
                        persisted_count = persist_local_work_graph(
                            connection,
                            session_id=existing["session_id"],
                            work_graph_id=existing["work_graph_id"],
                            items=legacy_items,
                            actor=existing["actor"],
                            created_at=created_at,
                        )
                        connection.execute(
                            "UPDATE local_control_plans SET created_work_items=?,"
                            "local_work_graph_version=1 WHERE plan_id=? "
                            "AND local_work_graph_version=0",
                            (persisted_count, existing["plan_id"]),
                        )
                        existing = connection.execute(
                            "SELECT * FROM local_control_plans WHERE plan_id=?",
                            (existing["plan_id"],),
                        ).fetchone()
                        if existing is None:
                            raise LocalWorkGraphCorruption(
                                "local-work-graph-corruption: legacy-plan"
                            )
                    expected_items = self._expected_local_work_items(existing)
                    validate_local_work_graph(
                        connection,
                        workflow_run_id=existing["workflow_run_id"],
                        work_graph_id=existing["work_graph_id"],
                        expected_count=int(existing["created_work_items"]),
                        expected_items=expected_items,
                        session_id=existing["session_id"],
                        expected_actor=existing["actor"],
                        expected_check_ids_by_phase=self._expected_local_check_ids(existing),
                        expected_plan_revision=int(existing["state_version"]),
                    )
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
                return self._result(existing)

            columns = (
                "plan_id", "session_id", "actor", "runtime_policy_snapshot_id",
                "idempotency_key", "request_digest", "workflow_run_id", "work_graph_id",
                "goal_binding_id", "objective_digest", "routing_envelope", "selection_mode",
                "support_policy", "support_consent_required", "explicit_skill_ids_json",
                "explicit_semantics", "route_source", "routing_profile_ids_json",
                "routing_profile_digest", "matched_profile_rule_id", "planned_skill_ids_json",
                "planned_skill_tree_json", "activation_status", "profile_warnings_json",
                "classification_source", "classification_confidence",
                "classifier_revision", "classification_reason_codes_json",
                "created_work_items", "local_work_graph_version", "state_version", "created_at",
            )
            values = (
                    _stable_id("plan", command.context.session_id, command.idempotency_key),
                    command.context.session_id,
                    command.context.actor,
                    command.context.runtime_policy_snapshot_id,
                    command.idempotency_key,
                    request_digest,
                    workflow_run_id,
                    work_graph_id,
                    command.goal_binding_id,
                    objective_digest,
                    routing_envelope,
                    decision.routing.skill_policy.value,
                    directive.support_policy.value,
                    int(support_consent_required),
                    canonical_json(list(directive.explicit_skills)),
                    (
                        None if directive.explicit_semantics is None
                        else directive.explicit_semantics.value
                    ),
                    route_source,
                    canonical_json(list(routing_profile_ids)),
                    routing_profile_digest,
                    matched_profile_rule_id,
                    canonical_json(list(planned_skill_ids)),
                    canonical_json([phase.to_dict() for phase in planned_skill_tree]),
                    activation_status,
                    canonical_json(list(profile_warnings)),
                    classification_source,
                    analysis.confidence,
                    analysis.classifier_revision,
                    canonical_json(list(analysis.reason_codes)),
                    1,
                    1,
                    1,
                    created_at,
                )
            try:
                connection.execute(
                    f"INSERT INTO local_control_plans({','.join(columns)}) "
                    f"VALUES ({','.join('?' for _ in values)})",
                    values,
                )
                persisted_count = persist_local_work_graph(
                    connection,
                    session_id=command.context.session_id,
                    work_graph_id=work_graph_id,
                    items=local_work_items,
                    actor=command.context.actor,
                    created_at=created_at,
                )
                connection.execute(
                    "UPDATE local_control_plans SET created_work_items=? "
                    "WHERE workflow_run_id=? AND local_work_graph_version=1",
                    (persisted_count, workflow_run_id),
                )
                stored = connection.execute(
                    "SELECT * FROM local_control_plans WHERE workflow_run_id=?",
                    (workflow_run_id,),
                ).fetchone()
                if stored is None:
                    raise RuntimeError("persisted-plan-unavailable")
                expected_items = self._expected_local_work_items(stored)
                validate_local_work_graph(
                    connection,
                    workflow_run_id=workflow_run_id,
                    work_graph_id=work_graph_id,
                    expected_count=int(stored["created_work_items"]),
                    expected_items=expected_items,
                    session_id=command.context.session_id,
                    expected_actor=stored["actor"],
                    expected_check_ids_by_phase=self._expected_local_check_ids(stored),
                    expected_plan_revision=int(stored["state_version"]),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        if stored is None:
            raise RuntimeError("persisted-plan-unavailable")
        return self._result(stored)

    def get_router_status(self, query) -> RouterStatusView:
        clauses = ["session_id=?"]
        values: list[object] = [query.context.session_id]
        if query.workflow_run_id is not None:
            clauses.append("workflow_run_id=?")
            values.append(query.workflow_run_id)
        if query.goal_binding_id is not None:
            clauses.append("goal_binding_id=?")
            values.append(query.goal_binding_id)
        with closing(sqlite3.connect(self._database)) as connection:
            row = connection.execute(
                "SELECT COALESCE(SUM(created_work_items), 0) "
                f"FROM local_control_plans WHERE {' AND '.join(clauses)}",
                tuple(values),
            ).fetchone()
        return RouterStatusView(
            query.goal_binding_id,
            query.workflow_run_id,
            int(row[0]) if row is not None else 0,
            None,
            False,
        )

    def require_local_capability(self, tool_name: str, command) -> None:
        if tool_name == "get_next_work":
            self._validated_next_work(command)
            return
        if tool_name in {"record_work_event", "evaluate_gate"}:
            self._require_router_local_plan(command, tool_name)
            return
        raise CapabilityUnavailable.for_tool(tool_name)

    def get_next_work(self, query) -> NextWorkResult:
        _, items = self._validated_next_work(query)
        status, work_item = next_ready_local_work_item(items)
        refresh_requirements = (
            ("local-work-graph-decomposition-required",)
            if status == "decomposition-required"
            else ()
        )
        return NextWorkResult(
            status=status,
            refresh_requirements=refresh_requirements,
            work_item=work_item,
            authority_mode="router-local",
            host_goal_mutated=False,
        )

    def _validated_next_work(self, query) -> tuple[sqlite3.Row, tuple[LocalWorkItem, ...]]:
        with closing(sqlite3.connect(self._database)) as connection:
            connection.row_factory = sqlite3.Row
            plan = connection.execute(
                "SELECT * FROM local_control_plans WHERE workflow_run_id=? "
                "AND session_id=? AND actor=? AND runtime_policy_snapshot_id=?",
                (
                    query.workflow_run_id,
                    query.context.session_id,
                    query.context.actor,
                    query.context.runtime_policy_snapshot_id,
                ),
            ).fetchone()
            if plan is None:
                raise CapabilityUnavailable.for_local_condition(
                    "get_next_work",
                    required_capabilities=("router-owned-work-graph",),
                    fallback_action=(
                        "Create or replay a Router-owned local work graph in this session."
                    ),
                )
            graph_version = int(plan["local_work_graph_version"])
            graph_row = connection.execute(
                "SELECT "
                "(SELECT COUNT(*) FROM local_work_items WHERE workflow_run_id=?),"
                "(SELECT COUNT(*) FROM local_work_transitions WHERE workflow_run_id=?)",
                (plan["workflow_run_id"], plan["workflow_run_id"]),
            ).fetchone()
            graph_row_count = (
                0
                if graph_row is None
                else int(graph_row[0]) + int(graph_row[1])
            )
            if graph_version == 0:
                if graph_row_count != 0:
                    raise LocalWorkGraphCorruption(
                        "local-work-graph-corruption: version-marker"
                    )
                raise CapabilityUnavailable.for_local_condition(
                    "get_next_work",
                    required_capabilities=("router-owned-work-graph",),
                    fallback_action=(
                        "Replay or create the Router-owned local work graph before scheduling."
                    ),
                )
            if graph_version != 1:
                raise LocalWorkGraphCorruption(
                    "local-work-graph-corruption: version-marker"
                )
            items = validate_local_work_graph(
                connection,
                workflow_run_id=plan["workflow_run_id"],
                work_graph_id=plan["work_graph_id"],
                expected_count=int(plan["created_work_items"]),
                expected_items=self._expected_local_work_items(plan),
                session_id=plan["session_id"],
                expected_actor=plan["actor"],
                expected_check_ids_by_phase=self._expected_local_check_ids(plan),
                expected_plan_revision=int(plan["state_version"]),
            )
        if plan["goal_binding_id"] is not None:
            raise CapabilityUnavailable.for_local_condition(
                "get_next_work",
                required_capabilities=("verified-host-scheduler",),
                fallback_action=(
                    "Continue this native Goal through the verified host scheduler."
                ),
            )
        return plan, items

    def record_work_event(self, command) -> LocalRecordWorkEventResult:
        observation = command.observation
        if (
            not isinstance(observation, LocalProgressObservation)
            or command.activation_receipt_ref is not None
        ):
            raise LocalObservationPolicyError(
                "router-local-recording-rejects-formal-or-receipt-observation"
            )
        if (
            isinstance(command.expected_state_version, bool)
            or not isinstance(command.expected_state_version, int)
            or not isinstance(observation.work_item_id, str)
            or not isinstance(observation.transition, str)
            or not isinstance(observation.check_ids, tuple)
        ):
            raise LocalObservationPolicyError("invalid-local-progress-command")
        if observation.transition not in LOCAL_PROGRESS_TRANSITIONS:
            raise LocalObservationPolicyError("unknown-local-transition")
        if (
            not observation.work_item_id.strip()
            or len(observation.check_ids) > 32
            or len(set(observation.check_ids)) != len(observation.check_ids)
            or any(
                not isinstance(check_id, str)
                or _ROUTING_IDENTIFIER.fullmatch(check_id) is None
                for check_id in observation.check_ids
            )
            or (
                observation.reported_outcome is not None
                and (
                    not isinstance(observation.reported_outcome, str)
                    or not observation.reported_outcome.strip()
                    or len(observation.reported_outcome) > 2048
                )
            )
        ):
            raise LocalObservationPolicyError("invalid-local-progress-observation")

        now = datetime.now(UTC).isoformat()
        with closing(sqlite3.connect(self._database, timeout=30.0)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("BEGIN IMMEDIATE")
            try:
                plan, items = self._bound_local_graph(connection, command, "record_work_event")
                item = next(
                    (candidate for candidate in items
                     if candidate.work_item_id == observation.work_item_id),
                    None,
                )
                if item is None or item.workflow_run_id != command.workflow_run_id:
                    raise LocalObservationPolicyError("local-work-item-cross-workflow")
                if item.phase_id != command.phase_id:
                    raise LocalObservationPolicyError("local-work-item-phase-drift")

                required_check_ids = self._required_check_ids(plan, item.phase_id)
                unknown_check_ids = set(observation.check_ids) - set(required_check_ids)
                if unknown_check_ids:
                    raise LocalObservationPolicyError("unknown-local-check-id")
                if observation.transition != "submit" and observation.check_ids:
                    raise LocalObservationPolicyError(
                        "local-checks-only-accepted-on-submit"
                    )
                satisfied_dependency_ids: tuple[str, ...] = ()
                if observation.transition == "start":
                    status_by_id = {
                        candidate.work_item_id: candidate.status
                        for candidate in items
                    }
                    if any(
                        status_by_id.get(dependency_id) != "completed"
                        for dependency_id in item.dependency_ids
                    ):
                        raise LocalObservationPolicyError(
                            "local-work-item-dependencies-incomplete"
                        )
                    satisfied_dependency_ids = item.dependency_ids
                document: dict[str, object] = {
                    "kind": "local-progress",
                    "work_item_id": observation.work_item_id,
                    "transition": observation.transition,
                    "check_ids": list(observation.check_ids),
                    "reported_outcome": observation.reported_outcome,
                    "satisfied_dependency_ids": list(satisfied_dependency_ids),
                    "authority_mode": "router-local",
                    "evidence_class": "user-or-agent-reported-local",
                    "host_transition_authorized": False,
                }
                replay = replay_local_transition(
                    connection,
                    session_id=command.context.session_id,
                    actor=command.context.actor,
                    workflow_run_id=command.workflow_run_id,
                    work_item_id=observation.work_item_id,
                    expected_state_version=command.expected_state_version,
                    idempotency_key=command.idempotency_key,
                    observation_document=document,
                )
                if replay is None:
                    row = connection.execute(
                        "SELECT status,state_version FROM local_work_items "
                        "WHERE work_item_id=? AND workflow_run_id=?",
                        (observation.work_item_id, command.workflow_run_id),
                    ).fetchone()
                    if row is None:
                        raise LocalObservationPolicyError("local-work-item-unavailable")
                    if int(row["state_version"]) != command.expected_state_version:
                        raise ConcurrencyConflict(
                            f"expected={command.expected_state_version}, actual={row['state_version']}"
                        )
                    to_status = local_transition_target(
                        row["status"], observation.transition
                    )
                    replay = append_local_transition(
                        connection,
                        session_id=command.context.session_id,
                        actor=command.context.actor,
                        workflow_run_id=command.workflow_run_id,
                        work_item_id=observation.work_item_id,
                        transition_kind=observation.transition,
                        from_status=row["status"],
                        to_status=to_status,
                        expected_state_version=command.expected_state_version,
                        idempotency_key=command.idempotency_key,
                        observation_document=document,
                        created_at=now,
                    )
                    validate_local_work_graph(
                        connection,
                        workflow_run_id=plan["workflow_run_id"],
                        work_graph_id=plan["work_graph_id"],
                        expected_count=int(plan["created_work_items"]),
                        expected_items=self._expected_local_work_items(plan),
                        session_id=plan["session_id"],
                        expected_actor=plan["actor"],
                        expected_check_ids_by_phase=self._expected_local_check_ids(plan),
                        expected_plan_revision=int(plan["state_version"]),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return LocalRecordWorkEventResult(
            event_ids=(replay.transition_id,),
            resulting_state_version=replay.resulting_state_version,
            replayed=replay.replayed,
            authority_mode="router-local",
            evidence_class="user-or-agent-reported-local",
            host_transition_authorized=False,
        )

    def evaluate_gate(self, command) -> EvaluateGateResult:
        if (
            isinstance(command.expected_state_version, bool)
            or not isinstance(command.expected_state_version, int)
            or isinstance(command.expected_plan_revision, bool)
            or not isinstance(command.expected_plan_revision, int)
            or not isinstance(command.evidence_refs, tuple)
            or not isinstance(command.expected_evidence_digest, str)
            or re.fullmatch(
                r"sha256:[0-9a-f]{64}", command.expected_evidence_digest
            ) is None
        ):
            raise LocalObservationPolicyError("invalid-local-gate-command")
        if command.evidence_refs:
            raise LocalObservationPolicyError(
                "router-local-gate-rejects-formal-evidence-refs"
            )
        now = datetime.now(UTC).isoformat()
        with closing(sqlite3.connect(self._database, timeout=30.0)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("BEGIN IMMEDIATE")
            try:
                plan, items = self._bound_local_graph(connection, command, "evaluate_gate")
                persisted_plan_revision = int(plan["state_version"])
                if command.expected_plan_revision != persisted_plan_revision:
                    raise ConcurrencyConflict(
                        "expected_plan_revision="
                        f"{command.expected_plan_revision}, actual={persisted_plan_revision}"
                    )
                matching = tuple(
                    item for item in items if item.phase_id == command.phase_id
                )
                if len(matching) != 1:
                    raise LocalObservationPolicyError("local-gate-phase-drift")
                item = matching[0]
                required_check_ids = self._required_check_ids(plan, item.phase_id)
                if not required_check_ids:
                    raise LocalObservationPolicyError("local-exit-gate-unconfigured")
                existing_replay = connection.execute(
                    "SELECT observation_json FROM local_work_transitions "
                    "WHERE session_id=? AND idempotency_key=?",
                    (command.context.session_id, command.idempotency_key),
                ).fetchone()
                replay = None
                if existing_replay is not None:
                    if existing_replay["observation_json"] is None:
                        raise IdempotencyConflict(
                            "相同 idempotency key 不得對應不同 Router-local gate"
                        )
                    try:
                        document = json.loads(existing_replay["observation_json"])
                    except (TypeError, ValueError, json.JSONDecodeError) as error:
                        raise LocalWorkGraphCorruption(
                            "local-work-graph-corruption: gate-replay"
                        ) from error
                    if (
                        not isinstance(document, dict)
                        or document.get("kind") != "local-gate"
                        or document.get("work_item_id") != item.work_item_id
                        or document.get("phase_id") != command.phase_id
                        or tuple(document.get("required_check_ids", ()))
                        != required_check_ids
                        or document.get("expected_plan_revision")
                        != command.expected_plan_revision
                        or document.get("evidence_digest")
                        != command.expected_evidence_digest
                    ):
                        raise IdempotencyConflict(
                            "相同 idempotency key 不得對應不同 Router-local gate"
                        )
                    replay = replay_local_transition(
                        connection,
                        session_id=command.context.session_id,
                        actor=command.context.actor,
                        workflow_run_id=command.workflow_run_id,
                        work_item_id=item.work_item_id,
                        expected_state_version=command.expected_state_version,
                        idempotency_key=command.idempotency_key,
                        observation_document=document,
                    )
                if replay is None:
                    persisted_check_ids = self._persisted_local_check_ids(
                        connection, item.work_item_id
                    )
                    evidence_digest = local_evidence_digest(persisted_check_ids)
                    if command.expected_evidence_digest != evidence_digest:
                        raise ConcurrencyConflict("local-evidence-digest-changed")
                    failures = tuple(
                        f"missing-local-check:{check_id}"
                        for check_id in required_check_ids
                        if check_id not in persisted_check_ids
                    )
                    passed = not failures
                    document = {
                        "kind": "local-gate",
                        "work_item_id": item.work_item_id,
                        "phase_id": item.phase_id,
                        "required_check_ids": list(required_check_ids),
                        "persisted_check_ids": list(persisted_check_ids),
                        "passed": passed,
                        "failures": list(failures),
                        "evidence_digest": evidence_digest,
                        "expected_plan_revision": command.expected_plan_revision,
                        "authority_mode": "router-local",
                        "evidence_class": "user-or-agent-reported-local",
                        "host_transition_authorized": False,
                    }
                    row = connection.execute(
                        "SELECT status,state_version FROM local_work_items "
                        "WHERE work_item_id=? AND workflow_run_id=?",
                        (item.work_item_id, command.workflow_run_id),
                    ).fetchone()
                    if row is None:
                        raise LocalObservationPolicyError("local-work-item-unavailable")
                    if int(row["state_version"]) != command.expected_state_version:
                        raise ConcurrencyConflict(
                            f"expected={command.expected_state_version}, actual={row['state_version']}"
                        )
                    if row["status"] != "verifying":
                        raise LocalObservationPolicyError(
                            "local-gate-requires-verifying-item"
                        )
                    replay = append_local_transition(
                        connection,
                        session_id=command.context.session_id,
                        actor=command.context.actor,
                        workflow_run_id=command.workflow_run_id,
                        work_item_id=item.work_item_id,
                        transition_kind="gate-pass" if passed else "gate-fail",
                        from_status="verifying",
                        to_status="completed" if passed else "verifying",
                        expected_state_version=command.expected_state_version,
                        idempotency_key=command.idempotency_key,
                        observation_document=document,
                        created_at=now,
                    )
                    validate_local_work_graph(
                        connection,
                        workflow_run_id=plan["workflow_run_id"],
                        work_graph_id=plan["work_graph_id"],
                        expected_count=int(plan["created_work_items"]),
                        expected_items=self._expected_local_work_items(plan),
                        session_id=plan["session_id"],
                        expected_actor=plan["actor"],
                        expected_check_ids_by_phase=self._expected_local_check_ids(plan),
                        expected_plan_revision=int(plan["state_version"]),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        stored = replay.observation_document
        return EvaluateGateResult(
            status="evaluated-local",
            passed=bool(stored["passed"]),
            failures=tuple(stored["failures"]),
            evidence_digest=str(stored["evidence_digest"]),
            resulting_state_version=replay.resulting_state_version,
            replayed=replay.replayed,
        )

    def _require_router_local_plan(self, command, tool_name: str) -> None:
        with closing(sqlite3.connect(self._database)) as connection:
            connection.row_factory = sqlite3.Row
            self._bound_local_graph(connection, command, tool_name)

    def _bound_local_graph(
        self,
        connection: sqlite3.Connection,
        command,
        tool_name: str,
    ) -> tuple[sqlite3.Row, tuple[LocalWorkItem, ...]]:
        graph_action = {
            "record_work_event": "reporting local progress",
            "evaluate_gate": "evaluating a local gate",
        }.get(tool_name, "continuing")
        plan = connection.execute(
            "SELECT * FROM local_control_plans WHERE workflow_run_id=? "
            "AND session_id=? AND actor=? AND runtime_policy_snapshot_id=?",
            (
                command.workflow_run_id,
                command.context.session_id,
                command.context.actor,
                command.context.runtime_policy_snapshot_id,
            ),
        ).fetchone()
        if plan is None:
            raise CapabilityUnavailable.for_local_condition(
                tool_name,
                required_capabilities=("router-owned-work-graph",),
                fallback_action=(
                    "Create or replay a Router-owned local work graph in this session "
                    f"before {graph_action}."
                ),
            )
        graph_version = int(plan["local_work_graph_version"])
        if graph_version != 1:
            graph_row = connection.execute(
                "SELECT "
                "(SELECT COUNT(*) FROM local_work_items WHERE workflow_run_id=?),"
                "(SELECT COUNT(*) FROM local_work_transitions WHERE workflow_run_id=?)",
                (plan["workflow_run_id"], plan["workflow_run_id"]),
            ).fetchone()
            graph_row_count = (
                0 if graph_row is None else int(graph_row[0]) + int(graph_row[1])
            )
            if graph_version != 0 or graph_row_count != 0:
                raise LocalWorkGraphCorruption(
                    "local-work-graph-corruption: version-marker"
                )
            raise CapabilityUnavailable.for_local_condition(
                tool_name,
                required_capabilities=("router-owned-work-graph",),
                fallback_action=(
                    "Replay or create the Router-owned local work graph before "
                    f"{graph_action}."
                ),
            )
        items = validate_local_work_graph(
            connection,
            workflow_run_id=plan["workflow_run_id"],
            work_graph_id=plan["work_graph_id"],
            expected_count=int(plan["created_work_items"]),
            expected_items=self._expected_local_work_items(plan),
            session_id=plan["session_id"],
            expected_actor=plan["actor"],
            expected_check_ids_by_phase=self._expected_local_check_ids(plan),
            expected_plan_revision=int(plan["state_version"]),
        )
        if plan["goal_binding_id"] is not None:
            native_goal_requirements = {
                "record_work_event": (
                    "verified-event-store", "activation-receipt-verifier",
                ),
                "evaluate_gate": ("verified-evidence-store", "gate-authority"),
            }
            native_goal_fallbacks = {
                "record_work_event": (
                    "Retain the observation locally and report it only through a "
                    "verified host."
                ),
                "evaluate_gate": (
                    "Keep the gate pending until verified evidence and state are available."
                ),
            }
            raise CapabilityUnavailable.for_local_condition(
                tool_name,
                required_capabilities=native_goal_requirements[tool_name],
                fallback_action=native_goal_fallbacks[tool_name],
            )
        return plan, items

    @staticmethod
    def _required_check_ids(
        plan: sqlite3.Row,
        phase_id: str,
    ) -> tuple[str, ...]:
        return LocalControlPlaneService._expected_local_check_ids(plan).get(
            phase_id, ()
        )

    @staticmethod
    def _persisted_local_check_ids(
        connection: sqlite3.Connection,
        work_item_id: str,
    ) -> tuple[str, ...]:
        rows = connection.execute(
            "SELECT observation_json FROM local_work_transitions "
            "WHERE work_item_id=? AND observation_json IS NOT NULL "
            "ORDER BY resulting_state_version",
            (work_item_id,),
        ).fetchall()
        check_ids: list[str] = []
        for row in rows:
            try:
                document = json.loads(row["observation_json"])
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                raise LocalWorkGraphCorruption(
                    "local-work-graph-corruption: local-check-observation"
                ) from error
            if (
                isinstance(document, dict)
                and document.get("kind") == "local-progress"
                and document.get("transition") == "submit"
            ):
                check_ids.extend(document["check_ids"])
        return tuple(sorted(set(check_ids)))

    def propose_support_consent(self, command) -> SupportConsentResult:
        support_skills = tuple(sorted(command.support_skill_ids))
        if not command.phase_id.strip() or not command.scope_anchor_id.strip():
            raise ConsentPolicyError("support proposal 必須綁定目前 Phase scope")
        if not command.primary_skill_id.strip():
            raise ConsentPolicyError("primary SKILL 不得為空")
        if not support_skills:
            raise ConsentPolicyError("support proposal 至少需要一個輔助 SKILL")
        if len(support_skills) > 3:
            raise ConsentPolicyError("每個 scope 最多三個不同的輔助 SKILL")
        if len(set(support_skills)) != len(support_skills):
            raise ConsentPolicyError("同一 capability 不可重複提案")
        if command.primary_skill_id in support_skills:
            raise ConsentPolicyError("primary SKILL 不可同時列為 support")
        if re.fullmatch(r"sha256:[0-9a-f]{64}", command.context_fingerprint) is None:
            raise ConsentPolicyError("context fingerprint 格式無效")

        request_document = {
            "actor": command.context.actor,
            "context_fingerprint": command.context_fingerprint,
            "goal_revision": command.goal_revision,
            "phase_id": command.phase_id,
            "plan_revision": command.plan_revision,
            "primary_skill_id": command.primary_skill_id,
            "runtime_policy_snapshot_id": command.context.runtime_policy_snapshot_id,
            "scope_anchor_id": command.scope_anchor_id,
            "session_id": command.context.session_id,
            "support_skill_ids": list(support_skills),
            "workflow_run_id": command.workflow_run_id,
        }
        request_digest = _digest(canonical_json(request_document))
        now = datetime.now(UTC).isoformat()

        with closing(sqlite3.connect(self._database, timeout=30.0)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM local_support_consent_proposals "
                "WHERE session_id=? AND idempotency_key=?",
                (command.context.session_id, command.idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["request_digest"] != request_digest:
                    connection.rollback()
                    raise IdempotencyConflict(
                        "相同 idempotency key 不得對應不同 support proposal"
                    )
                connection.commit()
                return self._consent_result(existing, replayed=True)

            plan = connection.execute(
                "SELECT * FROM local_control_plans "
                "WHERE workflow_run_id=? AND session_id=?",
                (command.workflow_run_id, command.context.session_id),
            ).fetchone()
            if plan is None:
                connection.rollback()
                raise ConsentPolicyError("找不到目前 session 的 routing plan")
            if int(plan["state_version"]) != command.expected_state_version:
                connection.rollback()
                raise ConcurrencyConflict(
                    f"expected={command.expected_state_version}, actual={plan['state_version']}"
                )
            if command.plan_revision != 1:
                connection.rollback()
                raise ConcurrencyConflict(
                    f"expected_plan_revision={command.plan_revision}, actual=1"
                )
            planned_skills = tuple(json.loads(plan["explicit_skill_ids_json"]))
            if (
                plan["selection_mode"] != "explicit-locked"
                or plan["support_policy"] != "ask"
                or command.primary_skill_id not in planned_skills
            ):
                connection.rollback()
                raise ConsentPolicyError(
                    "只有 explicit-locked 且允許詢問支援的 plan 可建立 proposal"
                )
            if plan["goal_binding_id"] is None and command.goal_revision is not None:
                connection.rollback()
                raise ConsentPolicyError("非 Goal plan 不可帶 goal revision")
            if plan["goal_binding_id"] is not None and command.goal_revision is None:
                connection.rollback()
                raise ConsentPolicyError("Goal plan 必須綁定 goal revision")
            duplicate = connection.execute(
                "SELECT status FROM local_support_consent_proposals "
                "WHERE workflow_run_id=? AND scope_anchor_id=? "
                "AND goal_revision IS ? AND plan_revision=? AND primary_skill_id=? "
                "AND support_skill_ids_json=? AND context_fingerprint=? LIMIT 1",
                (
                    command.workflow_run_id,
                    command.scope_anchor_id,
                    command.goal_revision,
                    command.plan_revision,
                    command.primary_skill_id,
                    canonical_json(list(support_skills)),
                    command.context_fingerprint,
                ),
            ).fetchone()
            if duplicate is not None:
                connection.rollback()
                raise ConsentPolicyError(
                    "相同 scope 與 material context 的 support set 不得重複提案"
                )

            proposal_id = _stable_id(
                "support-proposal",
                command.context.session_id,
                command.idempotency_key,
            )
            connection.execute(
                "INSERT INTO local_support_consent_proposals("
                "proposal_id,session_id,idempotency_key,request_digest,workflow_run_id,"
                "phase_id,scope_anchor_id,goal_binding_id,goal_revision,plan_revision,"
                "routing_envelope,selection_mode,primary_skill_id,support_skill_ids_json,"
                "context_fingerprint,status,decision_ref,state_version,actor,created_at,decided_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', NULL, 1, ?, ?, NULL)",
                (
                    proposal_id,
                    command.context.session_id,
                    command.idempotency_key,
                    request_digest,
                    command.workflow_run_id,
                    command.phase_id,
                    command.scope_anchor_id,
                    plan["goal_binding_id"],
                    command.goal_revision,
                    command.plan_revision,
                    plan["routing_envelope"],
                    plan["selection_mode"],
                    command.primary_skill_id,
                    canonical_json(list(support_skills)),
                    command.context_fingerprint,
                    command.context.actor,
                    now,
                ),
            )
            stored = connection.execute(
                "SELECT * FROM local_support_consent_proposals WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
            connection.commit()
        if stored is None:
            raise RuntimeError("persisted-support-proposal-unavailable")
        return self._consent_result(stored, replayed=False)

    def transition_support_consent(self, command) -> SupportConsentResult:
        if command.action not in {"approve", "reject"}:
            raise ConsentPolicyError("consent action 必須是 approve 或 reject")
        if re.fullmatch(r"sha256:[0-9a-f]{64}", command.current_context_fingerprint) is None:
            raise ConsentPolicyError("current context fingerprint 格式無效")
        request_document = {
            "action": command.action,
            "actor": command.context.actor,
            "current_context_fingerprint": command.current_context_fingerprint,
            "current_goal_revision": command.current_goal_revision,
            "current_phase_id": command.current_phase_id,
            "current_plan_revision": command.current_plan_revision,
            "current_scope_anchor_id": command.current_scope_anchor_id,
            "proposal_id": command.proposal_id,
            "runtime_policy_snapshot_id": command.context.runtime_policy_snapshot_id,
            "session_id": command.context.session_id,
        }
        request_digest = _digest(canonical_json(request_document))
        now = datetime.now(UTC).isoformat()

        with closing(sqlite3.connect(self._database, timeout=30.0)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("BEGIN IMMEDIATE")
            replay = connection.execute(
                "SELECT * FROM local_support_consent_transitions "
                "WHERE session_id=? AND idempotency_key=?",
                (command.context.session_id, command.idempotency_key),
            ).fetchone()
            if replay is not None:
                if replay["request_digest"] != request_digest:
                    connection.rollback()
                    raise IdempotencyConflict(
                        "相同 idempotency key 不得對應不同 consent transition"
                    )
                stored = connection.execute(
                    "SELECT * FROM local_support_consent_proposals WHERE proposal_id=?",
                    (replay["proposal_id"],),
                ).fetchone()
                connection.commit()
                if stored is None:
                    raise RuntimeError("persisted-consent-transition-unavailable")
                return self._consent_result(stored, replayed=True)

            proposal = connection.execute(
                "SELECT * FROM local_support_consent_proposals "
                "WHERE proposal_id=? AND session_id=?",
                (command.proposal_id, command.context.session_id),
            ).fetchone()
            if proposal is None:
                connection.rollback()
                raise ConsentPolicyError("support proposal 不存在或不屬於目前 session")
            if int(proposal["state_version"]) != command.expected_state_version:
                connection.rollback()
                raise ConcurrencyConflict(
                    f"expected={command.expected_state_version}, actual={proposal['state_version']}"
                )
            current_binding = (
                command.current_phase_id,
                command.current_scope_anchor_id,
                command.current_goal_revision,
                command.current_plan_revision,
                command.current_context_fingerprint,
            )
            proposal_binding = (
                proposal["phase_id"],
                proposal["scope_anchor_id"],
                proposal["goal_revision"],
                int(proposal["plan_revision"]),
                proposal["context_fingerprint"],
            )
            if current_binding != proposal_binding:
                connection.rollback()
                raise ConcurrencyConflict("consent proposal 已因 scope、revision 或 context 漂移而失效")
            if proposal["status"] != "pending":
                connection.rollback()
                raise ConcurrencyConflict("consent proposal 已完成，不可再次轉移")

            status = "approved" if command.action == "approve" else "rejected"
            decision_ref = _stable_id(
                "consent-grant" if status == "approved" else "consent-rejection",
                command.context.session_id,
                command.idempotency_key,
            )
            changed = connection.execute(
                "UPDATE local_support_consent_proposals "
                "SET status=?,decision_ref=?,state_version=2,decided_at=? "
                "WHERE proposal_id=? AND state_version=1 AND status='pending'",
                (status, decision_ref, now, command.proposal_id),
            ).rowcount
            if changed != 1:
                connection.rollback()
                raise ConcurrencyConflict("consent proposal compare-and-swap 失敗")
            connection.execute(
                "INSERT INTO local_support_consent_transitions("
                "transition_id,session_id,idempotency_key,request_digest,proposal_id,"
                "action,decision_ref,resulting_state_version,actor,created_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, 2, ?, ?)",
                (
                    _stable_id(
                        "consent-transition",
                        command.context.session_id,
                        command.idempotency_key,
                    ),
                    command.context.session_id,
                    command.idempotency_key,
                    request_digest,
                    command.proposal_id,
                    command.action,
                    decision_ref,
                    command.context.actor,
                    now,
                ),
            )
            stored = connection.execute(
                "SELECT * FROM local_support_consent_proposals WHERE proposal_id=?",
                (command.proposal_id,),
            ).fetchone()
            connection.commit()
        if stored is None:
            raise RuntimeError("persisted-consent-transition-unavailable")
        return self._consent_result(stored, replayed=False)

    def __getattr__(self, name):
        def unavailable(command):
            del command
            raise RuntimeError("verified-runtime-initialization-required")

        return unavailable

    @staticmethod
    def _planned_tree(row: sqlite3.Row) -> tuple[PlannedSkillPhase, ...]:
        return tuple(
            PlannedSkillPhase(
                phase["phase_id"],
                phase["primary_skill_id"],
                tuple(phase["support_skill_ids"]),
                phase["exit_gate"],
            )
            for phase in json.loads(row["planned_skill_tree_json"])
        )

    @staticmethod
    def _expected_local_work_items(
        row: sqlite3.Row,
    ) -> tuple[LocalWorkItem, ...]:
        return build_local_work_items(
            workflow_run_id=row["workflow_run_id"],
            work_graph_id=row["work_graph_id"],
            routing_envelope=row["routing_envelope"],
            goal_binding_id=row["goal_binding_id"],
            planned_skill_tree=LocalControlPlaneService._planned_tree(row),
            planned_skill_ids=LocalControlPlaneService._planned_skill_ids(row),
        )

    @staticmethod
    def _planned_skill_ids(row: sqlite3.Row) -> tuple[str, ...]:
        """讀取並驗證持久化的 Skill ID，避免重播時改寫 Router-owned 圖。"""

        try:
            skill_ids = json.loads(row["planned_skill_ids_json"])
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise LocalWorkGraphCorruption(
                "local-work-graph-corruption: planned-skill-ids"
            ) from error
        if (
            not isinstance(skill_ids, list)
            or any(not is_canonical_skill_id(skill_id) for skill_id in skill_ids)
            or len(set(skill_ids)) != len(skill_ids)
        ):
            raise LocalWorkGraphCorruption(
                "local-work-graph-corruption: planned-skill-ids"
            )
        return tuple(skill_ids)

    @staticmethod
    def _expected_local_check_ids(
        row: sqlite3.Row,
    ) -> dict[str, tuple[str, ...]]:
        return expected_local_check_ids(
            routing_envelope=row["routing_envelope"],
            goal_binding_id=row["goal_binding_id"],
            planned_skill_tree=LocalControlPlaneService._planned_tree(row),
        )

    @staticmethod
    def _result(row: sqlite3.Row) -> PlanWorkResult:
        planned_tree = LocalControlPlaneService._planned_tree(row)
        return PlanWorkResult(
            status="planned-local-control",
            workflow_run_id=row["workflow_run_id"],
            work_graph_id=row["work_graph_id"],
            created_work_items=int(row["created_work_items"]),
            routing_envelope=row["routing_envelope"],
            selection_mode=row["selection_mode"],
            support_consent_required=bool(row["support_consent_required"]),
            planned_skill_ids=tuple(json.loads(row["planned_skill_ids_json"])),
            runtime_mode=LOCAL_RUNTIME_MODE,
            route_source=row["route_source"],
            routing_profile_ids=tuple(json.loads(row["routing_profile_ids_json"])),
            routing_profile_digest=row["routing_profile_digest"],
            matched_profile_rule_id=row["matched_profile_rule_id"],
            planned_skill_tree=planned_tree,
            activation_status=row["activation_status"],
            profile_warnings=tuple(json.loads(row["profile_warnings_json"])),
            classification=ClassificationDecisionView(
                source=row["classification_source"],
                confidence=row["classification_confidence"],
                classifier_revision=row["classifier_revision"],
                reason_codes=tuple(
                    json.loads(row["classification_reason_codes_json"])
                ),
            ),
        )

    @staticmethod
    def _consent_result(row: sqlite3.Row, *, replayed: bool) -> SupportConsentResult:
        status = row["status"]
        proposed_support = tuple(json.loads(row["support_skill_ids_json"]))
        return SupportConsentResult(
            status="proposal-required" if status == "pending" else status,
            proposal_id=row["proposal_id"],
            workflow_run_id=row["workflow_run_id"],
            phase_id=row["phase_id"],
            routing_envelope=row["routing_envelope"],
            selection_mode=row["selection_mode"],
            primary_skill=row["primary_skill_id"],
            support_skills=proposed_support if status != "rejected" else (),
            consent_action="proposal-required" if status == "pending" else status,
            goal_relation="progress" if row["goal_binding_id"] is not None else "none",
            decision_ref=row["decision_ref"],
            state_version=int(row["state_version"]),
            replayed=replayed,
            runtime_mode=LOCAL_RUNTIME_MODE,
        )
