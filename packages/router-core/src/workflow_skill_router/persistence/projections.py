from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3

from workflow_skill_router.capabilities.codecs import decode_snapshot, encode_capability
from workflow_skill_router.capabilities.models import CapabilitySnapshot, RiskLevel
from workflow_skill_router.schemas.artifacts import canonical_json
from workflow_skill_router.workflow.models import WorkflowRun, WorkflowStatus
from workflow_skill_router.routing.models import RoutingEnvelope


SUPPORTED_EVENT_SCHEMA = (
    "workflow-skill-router/workflow-event",
    "2.0.0-alpha.1",
    "workflow-event",
)
PROJECTION_CLEAR_ORDER = (
    "side_effect_attempts", "resource_locks", "lease_content_bindings",
    "lease_activation_consumptions", "consent_rejections", "consent_grants",
    "evidence_metadata", "goal_status_candidates", "workflow_completion_candidates",
    "work_items", "work_graphs", "goal_acceptance_coverage", "goal_revisions",
    "goal_bindings", "phase_runs", "workflow_runs", "capability_drifts",
    "capabilities", "capability_snapshots",
)


class ProjectionConflict(RuntimeError):
    pass


class ProjectionRunner:
    projection_name = "router-read-model-v2"

    def __init__(self, database: Path, *, artifact_store=None) -> None:
        self._database = database
        self._artifacts = artifact_store

    def checkpoint(self) -> int:
        with closing(sqlite3.connect(self._database)) as connection:
            row = connection.execute(
                "SELECT last_sequence FROM projection_checkpoints WHERE projection_name=?",
                (self.projection_name,),
            ).fetchone()
            return 0 if row is None else int(row[0])

    def catch_up(self) -> int:
        with closing(sqlite3.connect(self._database)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            try:
                count = self._apply_pending(connection)
                connection.commit()
                return count
            except Exception:
                connection.rollback()
                raise

    def rebuild(self) -> int:
        with closing(sqlite3.connect(self._database)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            try:
                for table in PROJECTION_CLEAR_ORDER:
                    connection.execute(f"DELETE FROM {table}")
                connection.execute(
                    "DELETE FROM projection_checkpoints WHERE projection_name=?",
                    (self.projection_name,),
                )
                count = self._apply_pending(connection)
                connection.commit()
                return count
            except Exception:
                connection.rollback()
                raise

    def _apply_pending(self, connection: sqlite3.Connection) -> int:
        row = connection.execute(
            "SELECT last_sequence FROM projection_checkpoints WHERE projection_name=?",
            (self.projection_name,),
        ).fetchone()
        checkpoint = 0 if row is None else int(row[0])
        events = connection.execute(
            "SELECT * FROM workflow_events WHERE sequence>? ORDER BY sequence",
            (checkpoint,),
        ).fetchall()
        for event in events:
            schema = (event["schema_id"], event["schema_version"], event["artifact_kind"])
            if schema != SUPPORTED_EVENT_SCHEMA:
                raise ProjectionConflict("unsupported workflow event schema")
            self._apply_event(connection, event)
            checkpoint = int(event["sequence"])
        connection.execute(
            "INSERT INTO projection_checkpoints(projection_name,last_sequence) VALUES (?, ?) "
            "ON CONFLICT(projection_name) DO UPDATE SET last_sequence=excluded.last_sequence",
            (self.projection_name, checkpoint),
        )
        return len(events)

    def _apply_event(self, connection: sqlite3.Connection, event: sqlite3.Row) -> None:
        payload = json.loads(event["inline_payload"])
        event_type = event["event_type"]
        if event_type == "WORKFLOW_CREATED":
            document = {
                "workflow_run_id": event["aggregate_id"],
                "parent_workflow_run_id": payload.get("parent_workflow_run_id"),
                "objective": payload.get("objective", ""),
                "objective_digest": payload["objective_digest"],
                "scope": payload.get("scope", []),
                "constraints": payload.get("constraints", []),
                "envelope": payload["envelope"],
                "status": payload.get("status", "draft"),
                "plan_revision": int(event["plan_revision"]),
                "capability_snapshot_id": payload["capability_snapshot_id"],
                "current_phase_id": None,
                "paused_from_status": None,
                "awaiting_from_status": None,
                "pause_reason": None,
                "state_version": int(event["state_version_after"]),
            }
            connection.execute(
                "INSERT INTO workflow_runs VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, ?, ?)",
                (
                    document["workflow_run_id"], document["objective_digest"],
                    document["envelope"], document["status"], document["plan_revision"],
                    document["capability_snapshot_id"], document["state_version"],
                    canonical_json(document),
                ),
            )
        elif event_type == "WORKFLOW_STATUS_TRANSITIONED":
            current = connection.execute(
                "SELECT state_version,payload_json FROM workflow_runs WHERE workflow_run_id=?",
                (event["aggregate_id"],),
            ).fetchone()
            if current is None or int(current[0]) != int(event["state_version_before"]):
                raise ProjectionConflict("workflow projection version conflict")
            document = json.loads(current[1])
            document["status"] = payload["to"]
            document["state_version"] = int(event["state_version_after"])
            connection.execute(
                "UPDATE workflow_runs SET status=?,state_version=?,payload_json=? WHERE workflow_run_id=?",
                (payload["to"], event["state_version_after"], canonical_json(document), event["aggregate_id"]),
            )
        elif event_type == "CAPABILITY_SNAPSHOT_CREATED":
            self._apply_capability_snapshot(connection, event, payload)
        elif event_type == "CAPABILITY_DRIFT_DETECTED":
            connection.execute(
                "INSERT INTO capability_drifts VALUES (?, ?, ?, ?, ?, ?)",
                (
                    payload["drift_id"], payload["previous_snapshot_id"],
                    payload["current_snapshot_id"], payload["capability_id"],
                    payload["kind"], canonical_json(payload),
                ),
            )
        # Observation/audit events without read-model columns intentionally advance checkpoint.

    def _apply_capability_snapshot(
        self,
        connection: sqlite3.Connection,
        event: sqlite3.Row,
        identity: dict[str, object],
    ) -> None:
        expected = {
            "snapshot_id", "schema_version", "runtime_fingerprint", "provider_revisions",
            "provider_failures", "artifact_digest",
        }
        if set(identity) != expected:
            raise ProjectionConflict("capability snapshot identity fields mismatch")
        if self._artifacts is None or event["payload_ref"] != identity["artifact_digest"]:
            raise ProjectionConflict("capability snapshot artifact unavailable")
        raw = self._artifacts.open_verified(str(event["payload_ref"]))
        document = json.loads(raw.decode("utf-8"))
        snapshot = decode_snapshot(document)
        if (
            snapshot.snapshot_id != identity["snapshot_id"]
            or snapshot.schema_version != identity["schema_version"]
            or snapshot.runtime_fingerprint != identity["runtime_fingerprint"]
            or list(snapshot.provider_revisions) != identity["provider_revisions"]
        ):
            raise ProjectionConflict("capability snapshot artifact identity mismatch")
        connection.execute(
            "INSERT INTO capability_snapshots VALUES (?, ?, ?, ?, ?)",
            (
                snapshot.snapshot_id, snapshot.schema_version, snapshot.created_at,
                snapshot.runtime_fingerprint, canonical_json(document),
            ),
        )
        for capability in snapshot.capabilities:
            availability = {item.risk: item.result for item in capability.availability_by_risk}
            reasons = {
                risk.value: list(availability[risk].reasons)
                for risk in RiskLevel
            }
            connection.execute(
                "INSERT INTO capabilities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    snapshot.snapshot_id, capability.canonical_id,
                    capability.capability_fingerprint,
                    availability[RiskLevel.R0].primary.value,
                    availability[RiskLevel.R1].primary.value,
                    availability[RiskLevel.R2].primary.value,
                    availability[RiskLevel.R3].primary.value,
                    canonical_json(reasons),
                    canonical_json(encode_capability(capability).to_dict()),
                ),
            )


class WorkflowProjection:
    def __init__(self, database: Path) -> None:
        self._database = database

    def get_workflow(self, workflow_run_id: str) -> WorkflowRun | None:
        with closing(sqlite3.connect(self._database)) as connection:
            row = connection.execute(
                "SELECT payload_json FROM workflow_runs WHERE workflow_run_id=?",
                (workflow_run_id,),
            ).fetchone()
        if row is None:
            return None
        value = json.loads(row[0])
        return WorkflowRun(
            value["workflow_run_id"], value["parent_workflow_run_id"], value["objective"],
            value["objective_digest"], tuple(value["scope"]), tuple(value["constraints"]),
            RoutingEnvelope(value["envelope"]), WorkflowStatus(value["status"]),
            int(value["plan_revision"]), value["capability_snapshot_id"],
            value["current_phase_id"],
            WorkflowStatus(value["paused_from_status"]) if value["paused_from_status"] else None,
            WorkflowStatus(value["awaiting_from_status"]) if value["awaiting_from_status"] else None,
            value["pause_reason"], int(value["state_version"]),
        )

    def get_phase(self, phase_id: str):
        with closing(sqlite3.connect(self._database)) as connection:
            row = connection.execute(
                "SELECT payload_json FROM phase_runs WHERE phase_id=?", (phase_id,)
            ).fetchone()
        return None if row is None else json.loads(row[0])


class CapabilitySnapshotProjection:
    def __init__(self, database: Path) -> None:
        self._database = database

    def require(self, snapshot_id: str) -> CapabilitySnapshot:
        with closing(sqlite3.connect(self._database)) as connection:
            row = connection.execute(
                "SELECT payload_json FROM capability_snapshots WHERE snapshot_id=?",
                (snapshot_id,),
            ).fetchone()
        if row is None:
            raise LookupError(snapshot_id)
        return decode_snapshot(json.loads(row[0]))

    def canonical_rows(self, snapshot_id: str) -> dict[str, object]:
        with closing(sqlite3.connect(self._database)) as connection:
            connection.row_factory = sqlite3.Row
            parent = connection.execute(
                "SELECT * FROM capability_snapshots WHERE snapshot_id=?", (snapshot_id,)
            ).fetchone()
            children = connection.execute(
                "SELECT * FROM capabilities WHERE snapshot_id=? ORDER BY capability_id",
                (snapshot_id,),
            ).fetchall()
        if parent is None:
            raise LookupError(snapshot_id)
        return {
            "snapshot": dict(parent),
            "capabilities": [dict(item) for item in children],
        }
