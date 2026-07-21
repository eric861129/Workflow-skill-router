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
    LocalWorkGraphCorruption,
    build_local_work_items,
    persist_local_work_graph,
    validate_local_work_graph,
)
from workflow_skill_router.persistence.migrator import migrate
from workflow_skill_router.persistence.sqlite_store import (
    ConcurrencyConflict,
    IdempotencyConflict,
)
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
from workflow_skill_router.service_models import (
    ClassificationDecisionView,
    PlannedSkillPhase,
    PlanWorkResult,
    RouterStatusView,
    SupportConsentResult,
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
                    if int(existing["local_work_graph_version"]) == 0:
                        existing_count = connection.execute(
                            "SELECT COUNT(*) FROM local_work_items WHERE workflow_run_id=?",
                            (existing["workflow_run_id"],),
                        ).fetchone()
                        if existing_count is None or int(existing_count[0]) != 0:
                            raise LocalWorkGraphCorruption(
                                "local-work-graph-corruption: legacy-marker"
                            )
                        legacy_items = build_local_work_items(
                            workflow_run_id=existing["workflow_run_id"],
                            work_graph_id=existing["work_graph_id"],
                            routing_envelope=existing["routing_envelope"],
                            goal_binding_id=existing["goal_binding_id"],
                            planned_skill_tree=self._planned_tree(existing),
                        )
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
                    validate_local_work_graph(
                        connection,
                        workflow_run_id=existing["workflow_run_id"],
                        work_graph_id=existing["work_graph_id"],
                        expected_count=int(existing["created_work_items"]),
                        session_id=existing["session_id"],
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
                validate_local_work_graph(
                    connection,
                    workflow_run_id=workflow_run_id,
                    work_graph_id=work_graph_id,
                    expected_count=int(stored["created_work_items"]),
                    session_id=command.context.session_id,
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
