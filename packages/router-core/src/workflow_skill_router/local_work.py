from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import sqlite3
from typing import Mapping

from workflow_skill_router.persistence.sqlite_store import (
    ConcurrencyConflict,
    IdempotencyConflict,
)
from workflow_skill_router.schemas.artifacts import canonical_json
from workflow_skill_router.workflow.local_observations import LocalObservationPolicyError


LOCAL_WORK_STATUSES = frozenset({
    "pending",
    "ready",
    "active",
    "verifying",
    "paused",
    "completed",
    "failed",
    "decomposition-required",
    "host-scheduler-required",
})

ROUTER_LOCAL_SINGLE_COMPLETION_CHECK_ID = "router-local-single-completed"


class LocalWorkGraphCorruption(RuntimeError):
    """Raised when persisted Router-owned graph state cannot be trusted."""


@dataclass(frozen=True, slots=True)
class LocalWorkItem:
    work_item_id: str
    workflow_run_id: str
    phase_id: str
    dependency_ids: tuple[str, ...]
    primary_skill_id: str | None
    support_skill_ids: tuple[str, ...]
    status: str
    authority_mode: str = "router-local"


@dataclass(frozen=True, slots=True)
class LocalTransitionAppend:
    transition_id: str
    resulting_state_version: int
    replayed: bool
    observation_document: dict[str, object]
    from_status: str
    to_status: str


def _digest(document: object) -> str:
    return "sha256:" + hashlib.sha256(
        canonical_json(document).encode("utf-8")
    ).hexdigest()


def _public_id(prefix: str, *parts: str) -> str:
    identity = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"{prefix}:{identity}"


def local_transition_request_digest(
    *,
    session_id: str,
    actor: str,
    workflow_run_id: str,
    work_item_id: str,
    transition_kind: str,
    from_status: str | None,
    to_status: str,
    expected_state_version: int,
    resulting_state_version: int,
    observation_document: object | None = None,
) -> str:
    document = {
        "actor": actor,
        "from_status": from_status,
        "to_status": to_status,
        "transition_kind": transition_kind,
        "expected_state_version": expected_state_version,
        "resulting_state_version": resulting_state_version,
        "session_id": session_id,
        "work_item_id": work_item_id,
        "workflow_run_id": workflow_run_id,
    }
    if observation_document is not None:
        document["local_observation"] = observation_document
    return _digest(document)


def local_evidence_digest(check_ids: tuple[str, ...]) -> str:
    return _digest({
        "evidence_class": "user-or-agent-reported-local",
        "persisted_check_ids": sorted(check_ids),
    })


def local_transition_target(from_status: str, transition: str) -> str:
    targets = {
        ("ready", "start"): "active",
        ("pending", "start"): "active",
        ("active", "submit"): "verifying",
        ("active", "pause"): "paused",
        ("verifying", "pause"): "paused",
        ("paused", "resume"): "active",
        ("ready", "fail"): "failed",
        ("active", "fail"): "failed",
        ("verifying", "fail"): "failed",
        ("paused", "fail"): "failed",
    }
    target = targets.get((from_status, transition))
    if target is None:
        raise LocalObservationPolicyError(
            f"local-transition-not-allowed:{from_status}:{transition}"
        )
    return target


def replay_local_transition(
    connection: sqlite3.Connection,
    *,
    session_id: str,
    actor: str,
    workflow_run_id: str,
    work_item_id: str,
    expected_state_version: int,
    idempotency_key: str,
    observation_document: dict[str, object],
) -> LocalTransitionAppend | None:
    row = connection.execute(
        "SELECT * FROM local_work_transitions WHERE session_id=? AND idempotency_key=?",
        (session_id, idempotency_key),
    ).fetchone()
    if row is None:
        return None
    expected_digest = local_transition_request_digest(
        session_id=session_id,
        actor=actor,
        workflow_run_id=workflow_run_id,
        work_item_id=work_item_id,
        transition_kind=str(row["transition_kind"]),
        from_status=row["from_status"],
        to_status=str(row["to_status"]),
        expected_state_version=expected_state_version,
        resulting_state_version=int(row["resulting_state_version"]),
        observation_document=observation_document,
    )
    if (
        row["request_digest"] != expected_digest
        or row["actor"] != actor
        or row["workflow_run_id"] != workflow_run_id
        or row["work_item_id"] != work_item_id
    ):
        raise IdempotencyConflict(
            "相同 idempotency key 不得對應不同 Router-local observation"
        )
    try:
        stored_document = json.loads(row["observation_json"])
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise LocalWorkGraphCorruption(
            "local-work-graph-corruption: replay-observation"
        ) from error
    if stored_document != observation_document:
        raise IdempotencyConflict(
            "相同 idempotency key 不得對應不同 Router-local observation"
        )
    return LocalTransitionAppend(
        transition_id=row["transition_id"],
        resulting_state_version=int(row["resulting_state_version"]),
        replayed=True,
        observation_document=stored_document,
        from_status=row["from_status"],
        to_status=row["to_status"],
    )


def append_local_transition(
    connection: sqlite3.Connection,
    *,
    session_id: str,
    actor: str,
    workflow_run_id: str,
    work_item_id: str,
    transition_kind: str,
    from_status: str,
    to_status: str,
    expected_state_version: int,
    idempotency_key: str,
    observation_document: dict[str, object],
    created_at: str,
) -> LocalTransitionAppend:
    resulting_state_version = expected_state_version + 1
    transition_id = _public_id(
        "work-transition", work_item_id, str(resulting_state_version)
    )
    request_digest = local_transition_request_digest(
        session_id=session_id,
        actor=actor,
        workflow_run_id=workflow_run_id,
        work_item_id=work_item_id,
        transition_kind=transition_kind,
        from_status=from_status,
        to_status=to_status,
        expected_state_version=expected_state_version,
        resulting_state_version=resulting_state_version,
        observation_document=observation_document,
    )
    changed = connection.execute(
        "UPDATE local_work_items SET status=?,state_version=? "
        "WHERE work_item_id=? AND workflow_run_id=? AND status=? AND state_version=?",
        (
            to_status,
            resulting_state_version,
            work_item_id,
            workflow_run_id,
            from_status,
            expected_state_version,
        ),
    ).rowcount
    if changed != 1:
        raise ConcurrencyConflict(
            f"expected={expected_state_version}, local work item changed"
        )
    connection.execute(
        "INSERT INTO local_work_transitions("
        "transition_id,session_id,workflow_run_id,work_item_id,transition_kind,"
        "from_status,to_status,expected_state_version,resulting_state_version,"
        "idempotency_key,request_digest,actor,created_at,observation_json) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            transition_id,
            session_id,
            workflow_run_id,
            work_item_id,
            transition_kind,
            from_status,
            to_status,
            expected_state_version,
            resulting_state_version,
            idempotency_key,
            request_digest,
            actor,
            created_at,
            canonical_json(observation_document),
        ),
    )
    return LocalTransitionAppend(
        transition_id,
        resulting_state_version,
        False,
        observation_document,
        from_status,
        to_status,
    )


def _validate_transition_document(
    transition: sqlite3.Row,
    document: object,
) -> None:
    if not isinstance(document, dict):
        raise LocalWorkGraphCorruption(
            "local-work-graph-corruption: observation-shape"
        )
    common = {
        "authority_mode": "router-local",
        "evidence_class": "user-or-agent-reported-local",
        "host_transition_authorized": False,
    }
    if any(document.get(key) != value for key, value in common.items()):
        raise LocalWorkGraphCorruption(
            "local-work-graph-corruption: observation-authority"
        )
    if document.get("work_item_id") != transition["work_item_id"]:
        raise LocalWorkGraphCorruption(
            "local-work-graph-corruption: observation-item"
        )

    if document.get("kind") == "local-progress":
        expected_fields = {
            "kind", "work_item_id", "transition", "check_ids",
            "reported_outcome", "satisfied_dependency_ids", *common,
        }
        if set(document) != expected_fields:
            raise LocalWorkGraphCorruption(
                "local-work-graph-corruption: progress-fields"
            )
        check_ids = document["check_ids"]
        satisfied_dependency_ids = document["satisfied_dependency_ids"]
        outcome = document["reported_outcome"]
        if (
            not isinstance(check_ids, list)
            or not isinstance(satisfied_dependency_ids, list)
            or any(not isinstance(item, str) for item in check_ids)
            or any(not isinstance(item, str) for item in satisfied_dependency_ids)
            or len(set(check_ids)) != len(check_ids)
            or len(set(satisfied_dependency_ids)) != len(satisfied_dependency_ids)
            or (outcome is not None and not isinstance(outcome, str))
            or transition["transition_kind"] != document["transition"]
        ):
            raise LocalWorkGraphCorruption(
                "local-work-graph-corruption: progress-payload"
            )
        try:
            target = local_transition_target(
                transition["from_status"], str(document["transition"])
            )
        except LocalObservationPolicyError as error:
            raise LocalWorkGraphCorruption(
                "local-work-graph-corruption: progress-transition"
            ) from error
        if target != transition["to_status"]:
            raise LocalWorkGraphCorruption(
                "local-work-graph-corruption: progress-target"
            )
        if document["transition"] != "submit" and check_ids:
            raise LocalWorkGraphCorruption(
                "local-work-graph-corruption: progress-check-scope"
            )
        return

    if document.get("kind") == "local-gate":
        expected_fields = {
            "kind", "work_item_id", "phase_id", "required_check_ids",
            "persisted_check_ids", "passed", "failures", "evidence_digest",
            "expected_plan_revision", *common,
        }
        if set(document) != expected_fields:
            raise LocalWorkGraphCorruption(
                "local-work-graph-corruption: gate-fields"
            )
        required = document["required_check_ids"]
        persisted = document["persisted_check_ids"]
        failures = document["failures"]
        passed = document["passed"]
        if (
            not isinstance(required, list)
            or not isinstance(persisted, list)
            or not isinstance(failures, list)
            or any(not isinstance(item, str) for item in (*required, *persisted, *failures))
            or len(set(required)) != len(required)
            or len(set(persisted)) != len(persisted)
            or not isinstance(passed, bool)
            or isinstance(document["expected_plan_revision"], bool)
            or not isinstance(document["expected_plan_revision"], int)
            or document["evidence_digest"] != local_evidence_digest(tuple(persisted))
            or transition["from_status"] != "verifying"
            or transition["transition_kind"] != ("gate-pass" if passed else "gate-fail")
            or transition["to_status"] != ("completed" if passed else "verifying")
            or passed != (not failures)
        ):
            raise LocalWorkGraphCorruption(
                "local-work-graph-corruption: gate-payload"
            )
        return

    raise LocalWorkGraphCorruption(
        "local-work-graph-corruption: observation-kind"
    )


def build_local_work_items(
    *,
    workflow_run_id: str,
    work_graph_id: str,
    routing_envelope: str,
    goal_binding_id: str | None,
    planned_skill_tree: tuple[object, ...],
    planned_skill_ids: tuple[str, ...],
) -> tuple[LocalWorkItem, ...]:
    """Materialize only Router-owned planned work; never mirror a Host Goal graph."""

    if goal_binding_id is not None:
        return (_boundary_item(
            workflow_run_id,
            work_graph_id,
            phase_id="host-scheduler-boundary",
            status="host-scheduler-required",
        ),)

    if planned_skill_tree:
        items: list[LocalWorkItem] = []
        previous_id: str | None = None
        for index, phase in enumerate(planned_skill_tree):
            phase_id = phase.phase_id
            work_item_id = _public_id(
                "work-item", work_graph_id, str(index), phase_id
            )
            items.append(LocalWorkItem(
                work_item_id=work_item_id,
                workflow_run_id=workflow_run_id,
                phase_id=phase_id,
                dependency_ids=() if previous_id is None else (previous_id,),
                primary_skill_id=phase.primary_skill_id,
                support_skill_ids=tuple(phase.support_skill_ids),
                status="ready" if previous_id is None else "pending",
            ))
            previous_id = work_item_id
        if routing_envelope == "single" and len(items) != 1:
            raise ValueError("single-local-work-graph-requires-one-item")
        return tuple(items)

    if routing_envelope == "single":
        item = _boundary_item(
            workflow_run_id,
            work_graph_id,
            phase_id="single-work",
            status="ready",
        )
        if planned_skill_ids:
            item = replace(
                item,
                primary_skill_id=planned_skill_ids[0],
                support_skill_ids=planned_skill_ids[1:],
            )
        return (item,)

    return (_boundary_item(
        workflow_run_id,
        work_graph_id,
        phase_id="decomposition-boundary",
        status="decomposition-required",
    ),)


def expected_local_check_ids(
    *,
    routing_envelope: str,
    goal_binding_id: str | None,
    planned_skill_tree: tuple[object, ...],
) -> dict[str, tuple[str, ...]]:
    """Bind advisory checks to the Router-owned graph without granting Host authority."""

    if goal_binding_id is not None:
        return {}
    if planned_skill_tree:
        return {
            phase.phase_id: ((phase.exit_gate,) if phase.exit_gate.strip() else ())
            for phase in planned_skill_tree
        }
    if routing_envelope == "single":
        return {
            "single-work": (ROUTER_LOCAL_SINGLE_COMPLETION_CHECK_ID,),
        }
    return {}


def _boundary_item(
    workflow_run_id: str,
    work_graph_id: str,
    *,
    phase_id: str,
    status: str,
) -> LocalWorkItem:
    return LocalWorkItem(
        work_item_id=_public_id("work-item", work_graph_id, "0", phase_id),
        workflow_run_id=workflow_run_id,
        phase_id=phase_id,
        dependency_ids=(),
        primary_skill_id=None,
        support_skill_ids=(),
        status=status,
    )


def persist_local_work_graph(
    connection: sqlite3.Connection,
    *,
    session_id: str,
    work_graph_id: str,
    items: tuple[LocalWorkItem, ...],
    actor: str,
    created_at: str,
) -> int:
    if not items:
        raise ValueError("local-work-graph-empty")

    for item_order, item in enumerate(items):
        if (
            item.status not in LOCAL_WORK_STATUSES
            or item.authority_mode != "router-local"
        ):
            raise ValueError("local-work-item-invalid")
        connection.execute(
            "INSERT INTO local_work_items("
            "work_item_id,workflow_run_id,work_graph_id,item_order,phase_id,"
            "dependency_ids_json,primary_skill_id,support_skill_ids_json,status,"
            "authority_mode,state_version,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,1,?)",
            (
                item.work_item_id,
                item.workflow_run_id,
                work_graph_id,
                item_order,
                item.phase_id,
                canonical_json(list(item.dependency_ids)),
                item.primary_skill_id,
                canonical_json(list(item.support_skill_ids)),
                item.status,
                item.authority_mode,
                created_at,
            ),
        )
        idempotency_key = _public_id(
            "local-work-create", item.workflow_run_id, item.work_item_id
        )
        connection.execute(
            "INSERT INTO local_work_transitions("
            "transition_id,session_id,workflow_run_id,work_item_id,transition_kind,"
            "from_status,to_status,expected_state_version,resulting_state_version,"
            "idempotency_key,request_digest,actor,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,1,?,?,?,?)",
            (
                _public_id("work-transition", item.work_item_id, "1"),
                session_id,
                item.workflow_run_id,
                item.work_item_id,
                "create",
                None,
                item.status,
                0,
                idempotency_key,
                local_transition_request_digest(
                    session_id=session_id,
                    actor=actor,
                    workflow_run_id=item.workflow_run_id,
                    work_item_id=item.work_item_id,
                    transition_kind="create",
                    from_status=None,
                    to_status=item.status,
                    expected_state_version=0,
                    resulting_state_version=1,
                ),
                actor,
                created_at,
            ),
        )

    row = connection.execute(
        "SELECT COUNT(*) FROM local_work_items WHERE workflow_run_id=?",
        (items[0].workflow_run_id,),
    ).fetchone()
    return 0 if row is None else int(row[0])


def load_local_work_items(
    connection: sqlite3.Connection,
    workflow_run_id: str,
) -> tuple[LocalWorkItem, ...]:
    rows = connection.execute(
        "SELECT * FROM local_work_items WHERE workflow_run_id=? ORDER BY item_order",
        (workflow_run_id,),
    ).fetchall()
    return tuple(LocalWorkItem(
        work_item_id=row["work_item_id"],
        workflow_run_id=row["workflow_run_id"],
        phase_id=row["phase_id"],
        dependency_ids=tuple(json.loads(row["dependency_ids_json"])),
        primary_skill_id=row["primary_skill_id"],
        support_skill_ids=tuple(json.loads(row["support_skill_ids_json"])),
        status=row["status"],
        authority_mode=row["authority_mode"],
    ) for row in rows)


def next_ready_local_work_item(
    items: tuple[LocalWorkItem, ...],
) -> tuple[str, LocalWorkItem | None]:
    """Project advisory readiness without persisting activation or progress."""

    completed_ids = {
        item.work_item_id for item in items if item.status == "completed"
    }
    for item in items:
        dependencies_satisfied = set(item.dependency_ids).issubset(completed_ids)
        if item.status == "ready":
            if not dependencies_satisfied:
                raise LocalWorkGraphCorruption(
                    "local-work-graph-corruption: premature-ready"
                )
            return "ready", item
        if item.status == "pending" and dependencies_satisfied:
            return "ready", replace(item, status="ready")
        if item.status == "decomposition-required":
            return "decomposition-required", None
    return "no-ready-work", None


def validate_local_work_graph(
    connection: sqlite3.Connection,
    *,
    workflow_run_id: str,
    work_graph_id: str,
    expected_count: int,
    expected_items: tuple[LocalWorkItem, ...],
    session_id: str,
    expected_actor: str,
    expected_check_ids_by_phase: Mapping[str, tuple[str, ...]],
    expected_plan_revision: int,
) -> tuple[LocalWorkItem, ...]:
    rows = connection.execute(
        "SELECT * FROM local_work_items WHERE workflow_run_id=? ORDER BY item_order",
        (workflow_run_id,),
    ).fetchall()
    if (
        len(rows) != expected_count
        or len(rows) != len(expected_items)
        or not rows
    ):
        raise LocalWorkGraphCorruption("local-work-graph-corruption: item-count")
    rows_by_id = {row["work_item_id"]: row for row in rows}

    for expected_order, row in enumerate(rows):
        expected_item = expected_items[expected_order]
        try:
            raw_dependencies = json.loads(row["dependency_ids_json"])
            raw_support_skills = json.loads(row["support_skill_ids_json"])
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise LocalWorkGraphCorruption(
                "local-work-graph-corruption: invalid-json"
            ) from error
        if (
            not isinstance(raw_dependencies, list)
            or any(not isinstance(item, str) for item in raw_dependencies)
            or not isinstance(raw_support_skills, list)
            or any(not isinstance(item, str) for item in raw_support_skills)
        ):
            raise LocalWorkGraphCorruption(
                "local-work-graph-corruption: invalid-json-shape"
            )
        dependencies = tuple(raw_dependencies)
        support_skills = tuple(raw_support_skills)
        if (
            row["work_item_id"] != expected_item.work_item_id
            or row["workflow_run_id"] != expected_item.workflow_run_id
            or row["work_graph_id"] != work_graph_id
            or int(row["item_order"]) != expected_order
            or row["phase_id"] != expected_item.phase_id
            or dependencies != expected_item.dependency_ids
            or row["primary_skill_id"] != expected_item.primary_skill_id
            or support_skills != expected_item.support_skill_ids
            or row["authority_mode"] != expected_item.authority_mode
            or row["status"] not in LOCAL_WORK_STATUSES
            or len(set(support_skills)) != len(support_skills)
            or (
                row["primary_skill_id"] is not None
                and row["primary_skill_id"] in support_skills
            )
        ):
            raise LocalWorkGraphCorruption("local-work-graph-corruption: item-state")

        transitions = connection.execute(
            "SELECT * FROM local_work_transitions WHERE work_item_id=? "
            "ORDER BY resulting_state_version",
            (row["work_item_id"],),
        ).fetchall()
        if len(transitions) != int(row["state_version"]):
            raise LocalWorkGraphCorruption("local-work-graph-corruption: transition-count")
        required_check_ids = expected_check_ids_by_phase.get(row["phase_id"], ())
        persisted_check_ids: set[str] = set()
        previous_status = None
        for version, transition in enumerate(transitions, start=1):
            expected_from = previous_status
            observation_document = None
            if version == 1:
                if transition["observation_json"] is not None:
                    raise LocalWorkGraphCorruption(
                        "local-work-graph-corruption: create-observation"
                    )
            else:
                try:
                    observation_document = json.loads(transition["observation_json"])
                except (TypeError, ValueError, json.JSONDecodeError) as error:
                    raise LocalWorkGraphCorruption(
                        "local-work-graph-corruption: transition-observation"
                    ) from error
                if canonical_json(observation_document) != transition["observation_json"]:
                    raise LocalWorkGraphCorruption(
                        "local-work-graph-corruption: observation-canonical"
                    )
                _validate_transition_document(transition, observation_document)
                if observation_document["kind"] == "local-progress":
                    check_ids = tuple(observation_document["check_ids"])
                    if not set(check_ids).issubset(required_check_ids):
                        raise LocalWorkGraphCorruption(
                            "local-work-graph-corruption: unknown-local-check"
                        )
                    if observation_document["transition"] == "submit":
                        persisted_check_ids.update(check_ids)
                    satisfied_dependencies = tuple(
                        observation_document["satisfied_dependency_ids"]
                    )
                    if observation_document["transition"] == "start":
                        if satisfied_dependencies != expected_item.dependency_ids:
                            raise LocalWorkGraphCorruption(
                                "local-work-graph-corruption: dependency-proof"
                            )
                        if any(
                            dependency_id not in rows_by_id
                            or rows_by_id[dependency_id]["status"] != "completed"
                            for dependency_id in satisfied_dependencies
                        ):
                            raise LocalWorkGraphCorruption(
                                "local-work-graph-corruption: dependency-proof"
                            )
                    elif satisfied_dependencies:
                        raise LocalWorkGraphCorruption(
                            "local-work-graph-corruption: dependency-proof"
                        )
                elif observation_document["kind"] == "local-gate":
                    failures = tuple(
                        f"missing-local-check:{check_id}"
                        for check_id in required_check_ids
                        if check_id not in persisted_check_ids
                    )
                    if (
                        observation_document["expected_plan_revision"]
                        != expected_plan_revision
                    ):
                        raise LocalWorkGraphCorruption(
                            "local-work-graph-corruption: gate-plan-revision"
                        )
                    if (
                        observation_document["phase_id"] != row["phase_id"]
                        or tuple(observation_document["required_check_ids"])
                        != required_check_ids
                        or tuple(observation_document["persisted_check_ids"])
                        != tuple(sorted(persisted_check_ids))
                        or tuple(observation_document["failures"]) != failures
                        or observation_document["passed"] != (not failures)
                    ):
                        raise LocalWorkGraphCorruption(
                            "local-work-graph-corruption: gate-binding"
                        )
            expected_digest = local_transition_request_digest(
                session_id=session_id,
                actor=expected_actor,
                workflow_run_id=workflow_run_id,
                work_item_id=row["work_item_id"],
                transition_kind=transition["transition_kind"],
                from_status=transition["from_status"],
                to_status=transition["to_status"],
                expected_state_version=int(transition["expected_state_version"]),
                resulting_state_version=int(transition["resulting_state_version"]),
                observation_document=observation_document,
            )
            if (
                transition["session_id"] != session_id
                or transition["actor"] != expected_actor
                or transition["workflow_run_id"] != workflow_run_id
                or transition["work_item_id"] != row["work_item_id"]
                or transition["transition_id"] != _public_id(
                    "work-transition", row["work_item_id"], str(version)
                )
                or transition["from_status"] != expected_from
                or int(transition["expected_state_version"]) != version - 1
                or int(transition["resulting_state_version"]) != version
                or transition["request_digest"] != expected_digest
                or transition["to_status"] not in LOCAL_WORK_STATUSES
                or (version == 1 and transition["transition_kind"] != "create")
                or (version == 1 and transition["to_status"] != expected_item.status)
                or (
                    version == 1
                    and transition["idempotency_key"] != _public_id(
                        "local-work-create", workflow_run_id, row["work_item_id"]
                    )
                )
            ):
                raise LocalWorkGraphCorruption(
                    "local-work-graph-corruption: transition-chain"
                )
            previous_status = transition["to_status"]
        if previous_status != row["status"]:
            raise LocalWorkGraphCorruption("local-work-graph-corruption: status-drift")

    return tuple(LocalWorkItem(
        work_item_id=row["work_item_id"],
        workflow_run_id=row["workflow_run_id"],
        phase_id=row["phase_id"],
        dependency_ids=tuple(json.loads(row["dependency_ids_json"])),
        primary_skill_id=row["primary_skill_id"],
        support_skill_ids=tuple(json.loads(row["support_skill_ids_json"])),
        status=row["status"],
        authority_mode=row["authority_mode"],
    ) for row in rows)
