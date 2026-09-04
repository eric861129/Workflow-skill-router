from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from workflow_skill_router.local_work import (
    LocalWorkGraphCorruption,
    build_local_work_items,
    expected_local_check_ids,
    validate_local_work_graph,
)
from workflow_skill_router.profiles.contract import is_canonical_skill_id
from workflow_skill_router.schemas.artifacts import canonical_json
from workflow_skill_router.service_models import PlannedSkillPhase


_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")


class WorkflowReadError(RuntimeError):
    """Raised when persisted Router-local work cannot be safely observed."""


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _is_link_or_reparse(metadata: os.stat_result) -> bool:
    if stat.S_ISLNK(metadata.st_mode):
        return True
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return bool(attributes & flag)


def _validate_database(path: Path) -> Path:
    database = Path(path).expanduser()
    if not database.is_absolute():
        database = (Path.cwd() / database).absolute()
    else:
        database = database.absolute()
    try:
        metadata = database.lstat()
    except OSError as error:
        raise WorkflowReadError("workflow-database-unavailable") from error
    if _is_link_or_reparse(metadata):
        raise WorkflowReadError("workflow-database-link-forbidden")
    if not stat.S_ISREG(metadata.st_mode):
        raise WorkflowReadError("workflow-database-not-regular")
    return database


def _tuple_of_strings(raw: object, field: str, *, skill_ids: bool = False) -> tuple[str, ...]:
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise WorkflowReadError("workflow-graph-corrupt") from error
    if (
        not isinstance(value, list)
        or len(value) > 64
        or any(not isinstance(item, str) for item in value)
        or len(set(value)) != len(value)
    ):
        raise WorkflowReadError("workflow-graph-corrupt")
    if skill_ids:
        if any(not is_canonical_skill_id(item) for item in value):
            raise WorkflowReadError("workflow-graph-corrupt")
    elif any(not item or len(item) > 128 for item in value):
        raise WorkflowReadError("workflow-graph-corrupt")
    return tuple(value)


@dataclass(frozen=True, slots=True)
class MemoryRequestContext:
    session_id: str
    actor: str
    runtime_policy_snapshot_id: str

    def __post_init__(self) -> None:
        for name, value in (
            ("session_id", self.session_id),
            ("actor", self.actor),
            ("runtime_policy_snapshot_id", self.runtime_policy_snapshot_id),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError(f"invalid-memory-request-context:{name}")


@dataclass(frozen=True, slots=True)
class CompletedWorkflowPhase:
    phase_id: str
    primary_skill_id: str | None
    support_skill_ids: tuple[str, ...]
    exit_gate_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "phase_id": self.phase_id,
            "primary_skill_id": self.primary_skill_id,
            "support_skill_ids": list(self.support_skill_ids),
            "exit_gate_ids": list(self.exit_gate_ids),
        }


@dataclass(frozen=True, slots=True)
class CompletedWorkflowSnapshot:
    workflow_run_id: str
    workflow_run_digest: str
    workflow_fingerprint: str
    workspace_identity_digest: str | None
    work_mode: str
    terminal_status: str
    required_gates_passed: bool
    route_source: str
    routing_profile_ids: tuple[str, ...]
    routing_profile_digest: str | None
    matched_profile_rule_id: str | None
    activation_status: str
    routing_domains: tuple[str, ...]
    routing_tags: tuple[str, ...]
    profile_objective_keywords: tuple[str, ...]
    profile_domains: tuple[str, ...]
    profile_tags: tuple[str, ...]
    phases: tuple[CompletedWorkflowPhase, ...]
    pending_consent: bool

    def route_document(self) -> dict[str, object]:
        return {
            "work_mode": self.work_mode,
            "route_source": self.route_source,
            "routing_profile_ids": list(self.routing_profile_ids),
            "routing_profile_digest": self.routing_profile_digest,
            "matched_profile_rule_id": self.matched_profile_rule_id,
            "phases": [phase.to_dict() for phase in self.phases],
        }


class CompletedWorkflowReader:
    """Read one completed Router-owned Workflow through a strict read-only boundary."""

    def __init__(self, database: Path) -> None:
        self._database = _validate_database(Path(database))

    def read(
        self,
        context: MemoryRequestContext,
        workflow_run_id: str,
    ) -> CompletedWorkflowSnapshot:
        if not isinstance(context, MemoryRequestContext):
            raise TypeError("context must be MemoryRequestContext")
        if not isinstance(workflow_run_id, str) or not workflow_run_id or len(workflow_run_id) > 160:
            raise WorkflowReadError("invalid-workflow-run-id")

        uri = self._database.as_uri() + "?mode=ro"
        try:
            with closing(sqlite3.connect(uri, uri=True, timeout=5.0)) as connection:
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA foreign_keys = ON")
                row = connection.execute(
                    "SELECT * FROM local_control_plans WHERE workflow_run_id=?",
                    (workflow_run_id,),
                ).fetchone()
                if row is None:
                    raise WorkflowReadError("workflow-not-found")
                if (
                    row["session_id"] != context.session_id
                    or row["actor"] != context.actor
                    or row["runtime_policy_snapshot_id"] != context.runtime_policy_snapshot_id
                ):
                    raise WorkflowReadError("workflow-context-mismatch")
                if row["goal_binding_id"] is not None:
                    raise WorkflowReadError("native-goal-not-observable")
                if int(row["local_work_graph_version"]) != 1:
                    raise WorkflowReadError("workflow-graph-corrupt")

                planned_tree = self._planned_tree(row)
                planned_skill_ids = _tuple_of_strings(
                    row["planned_skill_ids_json"],
                    "planned_skill_ids_json",
                    skill_ids=True,
                )
                expected_items = build_local_work_items(
                    workflow_run_id=row["workflow_run_id"],
                    work_graph_id=row["work_graph_id"],
                    routing_envelope=row["routing_envelope"],
                    goal_binding_id=row["goal_binding_id"],
                    planned_skill_tree=planned_tree,
                    planned_skill_ids=planned_skill_ids,
                )
                checks = expected_local_check_ids(
                    routing_envelope=row["routing_envelope"],
                    goal_binding_id=row["goal_binding_id"],
                    planned_skill_tree=planned_tree,
                )
                try:
                    items = validate_local_work_graph(
                        connection,
                        workflow_run_id=row["workflow_run_id"],
                        work_graph_id=row["work_graph_id"],
                        expected_count=int(row["created_work_items"]),
                        expected_items=expected_items,
                        session_id=row["session_id"],
                        expected_actor=row["actor"],
                        expected_check_ids_by_phase=checks,
                        expected_plan_revision=int(row["state_version"]),
                    )
                except (LocalWorkGraphCorruption, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                    raise WorkflowReadError("workflow-graph-corrupt") from error
                if not items or any(item.status != "completed" for item in items):
                    raise WorkflowReadError("workflow-not-completed")
                pending = connection.execute(
                    "SELECT 1 FROM local_support_consent_proposals "
                    "WHERE workflow_run_id=? AND status='pending' LIMIT 1",
                    (workflow_run_id,),
                ).fetchone() is not None

                phases = tuple(
                    CompletedWorkflowPhase(
                        phase_id=item.phase_id,
                        primary_skill_id=item.primary_skill_id,
                        support_skill_ids=item.support_skill_ids,
                        exit_gate_ids=checks.get(item.phase_id, ()),
                    )
                    for item in items
                )
                for phase in phases:
                    if phase.primary_skill_id is not None and not is_canonical_skill_id(phase.primary_skill_id):
                        raise WorkflowReadError("workflow-graph-corrupt")
                    if any(not is_canonical_skill_id(item) for item in phase.support_skill_ids):
                        raise WorkflowReadError("workflow-graph-corrupt")

                workspace_digest = row["workspace_identity_digest"]
                if workspace_digest is not None and (
                    not isinstance(workspace_digest, str) or not _DIGEST.fullmatch(workspace_digest)
                ):
                    raise WorkflowReadError("workflow-graph-corrupt")
                profile_digest = row["routing_profile_digest"]
                if profile_digest is not None and (
                    not isinstance(profile_digest, str) or not _DIGEST.fullmatch(profile_digest)
                ):
                    raise WorkflowReadError("workflow-graph-corrupt")

                workflow_run_digest = _digest({"workflow_run_id": workflow_run_id})
                fingerprint = _digest({
                    "objective_digest": row["objective_digest"],
                    "workflow_run_digest": workflow_run_digest,
                    "route": {
                        "work_mode": row["routing_envelope"],
                        "route_source": row["route_source"],
                        "phases": [phase.to_dict() for phase in phases],
                    },
                })
                return CompletedWorkflowSnapshot(
                    workflow_run_id=workflow_run_id,
                    workflow_run_digest=workflow_run_digest,
                    workflow_fingerprint=fingerprint,
                    workspace_identity_digest=workspace_digest,
                    work_mode=row["routing_envelope"],
                    terminal_status="completed",
                    required_gates_passed=True,
                    route_source=row["route_source"],
                    routing_profile_ids=_tuple_of_strings(row["routing_profile_ids_json"], "routing_profile_ids_json"),
                    routing_profile_digest=profile_digest,
                    matched_profile_rule_id=row["matched_profile_rule_id"],
                    activation_status=row["activation_status"],
                    routing_domains=_tuple_of_strings(row["routing_domains_json"], "routing_domains_json"),
                    routing_tags=_tuple_of_strings(row["routing_tags_json"], "routing_tags_json"),
                    profile_objective_keywords=_tuple_of_strings(row["profile_objective_keywords_json"], "profile_objective_keywords_json"),
                    profile_domains=_tuple_of_strings(row["profile_domains_json"], "profile_domains_json"),
                    profile_tags=_tuple_of_strings(row["profile_tags_json"], "profile_tags_json"),
                    phases=phases,
                    pending_consent=pending,
                )
        except WorkflowReadError:
            raise
        except sqlite3.Error as error:
            raise WorkflowReadError("workflow-database-read-failed") from error

    @staticmethod
    def _planned_tree(row: sqlite3.Row) -> tuple[PlannedSkillPhase, ...]:
        try:
            raw = json.loads(row["planned_skill_tree_json"])
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise WorkflowReadError("workflow-graph-corrupt") from error
        if not isinstance(raw, list) or len(raw) > 64:
            raise WorkflowReadError("workflow-graph-corrupt")
        phases: list[PlannedSkillPhase] = []
        for item in raw:
            if not isinstance(item, dict) or set(item) != {
                "phase_id", "primary_skill_id", "support_skill_ids", "exit_gate"
            }:
                raise WorkflowReadError("workflow-graph-corrupt")
            phase_id = item["phase_id"]
            primary = item["primary_skill_id"]
            supports = item["support_skill_ids"]
            exit_gate = item["exit_gate"]
            if (
                not isinstance(phase_id, str)
                or not _IDENTIFIER.fullmatch(phase_id)
                or not is_canonical_skill_id(primary)
                or not isinstance(supports, list)
                or any(not is_canonical_skill_id(value) for value in supports)
                or len(set(supports)) != len(supports)
                or not isinstance(exit_gate, str)
                or not exit_gate
                or len(exit_gate) > 128
            ):
                raise WorkflowReadError("workflow-graph-corrupt")
            phases.append(PlannedSkillPhase(phase_id, primary, tuple(supports), exit_gate))
        return tuple(phases)


__all__ = [
    "CompletedWorkflowPhase",
    "CompletedWorkflowReader",
    "CompletedWorkflowSnapshot",
    "MemoryRequestContext",
    "WorkflowReadError",
]
