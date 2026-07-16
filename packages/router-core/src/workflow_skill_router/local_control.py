from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sqlite3

from workflow_skill_router.persistence.migrator import migrate
from workflow_skill_router.persistence.sqlite_store import (
    ConcurrencyConflict,
    IdempotencyConflict,
)
from workflow_skill_router.routing.directives import resolve_directive
from workflow_skill_router.routing.models import (
    DirectiveInput,
    GoalRelation,
    RuntimeMode,
    TaskSignals,
)
from workflow_skill_router.routing.profiler import decide_request
from workflow_skill_router.schemas.artifacts import canonical_json
from workflow_skill_router.service_models import (
    PlanWorkResult,
    RouterStatusView,
)


LOCAL_RUNTIME_MODE = "mcp-local-control-plane"


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_id(prefix: str, session_id: str, idempotency_key: str) -> str:
    identity = hashlib.sha256(
        f"{session_id}\0{idempotency_key}".encode("utf-8")
    ).hexdigest()[:32]
    return f"{prefix}:{identity}"


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
        decision = decide_request(
            GoalRelation.NONE,
            TaskSignals.small(),
            directive,
            RuntimeMode.SKILL_ONLY,
        )
        if decision.routing is None:
            raise RuntimeError("planning-routing-profile-unavailable")

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
            "runtime_policy_snapshot_id": command.context.runtime_policy_snapshot_id,
            "session_id": command.context.session_id,
        }
        request_digest = _digest(canonical_json(request_document))
        support_consent_required = False

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
                if existing["request_digest"] != request_digest:
                    connection.rollback()
                    raise IdempotencyConflict(
                        "相同 idempotency key 不得對應不同規劃請求"
                    )
                connection.commit()
                return self._result(existing)

            connection.execute(
                "INSERT INTO local_control_plans("
                "plan_id,session_id,actor,runtime_policy_snapshot_id,idempotency_key,"
                "request_digest,workflow_run_id,work_graph_id,goal_binding_id,"
                "objective_digest,routing_envelope,selection_mode,support_policy,"
                "support_consent_required,explicit_skill_ids_json,explicit_semantics,"
                "created_work_items,state_version,created_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?)",
                (
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
                    decision.routing.envelope.value,
                    decision.routing.skill_policy.value,
                    directive.support_policy.value,
                    int(support_consent_required),
                    canonical_json(list(directive.explicit_skills)),
                    (
                        None if directive.explicit_semantics is None
                        else directive.explicit_semantics.value
                    ),
                    datetime.now(UTC).isoformat(),
                ),
            )
            stored = connection.execute(
                "SELECT * FROM local_control_plans WHERE workflow_run_id=?",
                (workflow_run_id,),
            ).fetchone()
            connection.commit()
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

    def __getattr__(self, name):
        def unavailable(command):
            del command
            raise RuntimeError("verified-runtime-initialization-required")

        return unavailable

    @staticmethod
    def _result(row: sqlite3.Row) -> PlanWorkResult:
        return PlanWorkResult(
            status="planned-local-control",
            workflow_run_id=row["workflow_run_id"],
            work_graph_id=row["work_graph_id"],
            created_work_items=int(row["created_work_items"]),
            routing_envelope=row["routing_envelope"],
            selection_mode=row["selection_mode"],
            support_consent_required=bool(row["support_consent_required"]),
            planned_skill_ids=tuple(json.loads(row["explicit_skill_ids_json"])),
            runtime_mode=LOCAL_RUNTIME_MODE,
        )
