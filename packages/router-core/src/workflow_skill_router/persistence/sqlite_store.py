from __future__ import annotations

from collections.abc import Sequence
from contextlib import closing
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3

from workflow_skill_router.runtime import Clock, IdFactory
from workflow_skill_router.workflow.events import EventDraft, WorkflowEvent


class ConcurrencyConflict(RuntimeError):
    pass


class IdempotencyConflict(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AppendResult:
    events: tuple[WorkflowEvent, ...]
    resulting_state_version: int
    replayed: bool


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class SQLiteEventStore:
    def __init__(self, database: Path, clock: Clock, id_factory: IdFactory) -> None:
        self._database = database
        self._clock = clock
        self._id_factory = id_factory

    @staticmethod
    def _draft_document(item: EventDraft) -> dict[str, object]:
        return {
            "workflow_run_id": item.workflow_run_id,
            "event_type": item.event_type,
            "actor": item.actor,
            "plan_revision": item.plan_revision,
            "inline_payload": dict(item.inline_payload),
            "payload_ref": item.payload_ref,
            "correlation_id": item.correlation_id,
            "causation_id": item.causation_id,
        }

    def append(
        self,
        aggregate_type: str,
        aggregate_id: str,
        drafts: Sequence[EventDraft],
        expected_state_version: int,
        idempotency_key: str,
    ) -> AppendResult:
        if not drafts:
            raise ValueError("至少需要一個 EventDraft")
        if not aggregate_type or not aggregate_id or not idempotency_key:
            raise ValueError("aggregate 與 idempotency key 不可為空")
        if expected_state_version < 0:
            raise ValueError("expected_state_version 不可小於 0")
        if aggregate_type == "workflow":
            if any(item.workflow_run_id != aggregate_id for item in drafts):
                raise ValueError("workflow stream 必須綁定相同 workflow_run_id")
        elif any(item.workflow_run_id is not None for item in drafts):
            raise ValueError("非 workflow stream 不可帶 workflow_run_id")

        request_json = _canonical_json([
            self._draft_document(item) for item in drafts
        ])
        request_digest = "sha256:" + hashlib.sha256(request_json.encode("utf-8")).hexdigest()
        with closing(sqlite3.connect(self._database, timeout=30.0)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("BEGIN IMMEDIATE")
            receipt = connection.execute(
                "SELECT request_digest, event_ids_json, resulting_state_version "
                "FROM command_receipts WHERE aggregate_type=? AND aggregate_id=? "
                "AND idempotency_key=?",
                (aggregate_type, aggregate_id, idempotency_key),
            ).fetchone()
            if receipt is not None:
                if receipt["request_digest"] != request_digest:
                    connection.rollback()
                    raise IdempotencyConflict("相同 idempotency key 對應不同 command")
                event_ids = json.loads(receipt["event_ids_json"])
                events = tuple(self._read_event(connection, item) for item in event_ids)
                connection.commit()
                return AppendResult(events, int(receipt["resulting_state_version"]), True)

            row = connection.execute(
                "SELECT state_version FROM aggregate_versions "
                "WHERE aggregate_type=? AND aggregate_id=?",
                (aggregate_type, aggregate_id),
            ).fetchone()
            current = 0 if row is None else int(row["state_version"])
            if current != expected_state_version:
                connection.rollback()
                raise ConcurrencyConflict(
                    f"expected={expected_state_version}, actual={current}"
                )

            events = []
            for draft in drafts:
                before = current
                current += 1
                payload_json = _canonical_json(dict(draft.inline_payload))
                event_id = self._id_factory.new_event_id()
                occurred = self._clock.now_utc()
                if occurred.tzinfo is None or occurred.utcoffset() is None:
                    raise ValueError("Clock 必須回傳 timezone-aware datetime")
                occurred_at = occurred.isoformat()
                payload_digest = "sha256:" + hashlib.sha256(
                    payload_json.encode("utf-8")
                ).hexdigest()
                connection.execute(
                    "INSERT INTO workflow_events("
                    "schema_id,schema_version,artifact_kind,event_id,workflow_run_id,"
                    "aggregate_id,aggregate_type,event_type,actor,occurred_at,"
                    "state_version_before,state_version_after,plan_revision,payload_digest,"
                    "payload_ref,inline_payload,idempotency_key,correlation_id,causation_id) "
                    "VALUES ('workflow-skill-router/workflow-event','2.0.0-alpha.1',"
                    "'workflow-event',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        event_id, draft.workflow_run_id, aggregate_id, aggregate_type,
                        draft.event_type, draft.actor, occurred_at, before, current,
                        draft.plan_revision, payload_digest, draft.payload_ref, payload_json,
                        idempotency_key, draft.correlation_id, draft.causation_id,
                    ),
                )
                events.append(self._read_event(connection, event_id))

            connection.execute(
                "INSERT INTO aggregate_versions(aggregate_type,aggregate_id,state_version) "
                "VALUES (?, ?, ?) ON CONFLICT(aggregate_type,aggregate_id) "
                "DO UPDATE SET state_version=excluded.state_version",
                (aggregate_type, aggregate_id, current),
            )
            connection.execute(
                "INSERT INTO command_receipts(aggregate_type,aggregate_id,idempotency_key,"
                "request_digest,event_ids_json,resulting_state_version) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    aggregate_type, aggregate_id, idempotency_key, request_digest,
                    _canonical_json([event.event_id for event in events]), current,
                ),
            )
            connection.commit()
            return AppendResult(tuple(events), current, False)

    def read_stream(
        self,
        aggregate_type: str,
        aggregate_id: str,
        after_version: int = 0,
    ) -> tuple[WorkflowEvent, ...]:
        with closing(sqlite3.connect(self._database)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT * FROM workflow_events WHERE aggregate_type=? AND aggregate_id=? "
                "AND state_version_after>? ORDER BY state_version_after",
                (aggregate_type, aggregate_id, after_version),
            ).fetchall()
            return tuple(self._from_row(row) for row in rows)

    def read_all(self, after_sequence: int = 0) -> tuple[WorkflowEvent, ...]:
        with closing(sqlite3.connect(self._database)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT * FROM workflow_events WHERE sequence>? ORDER BY sequence",
                (after_sequence,),
            ).fetchall()
            return tuple(self._from_row(row) for row in rows)

    def _read_event(self, connection: sqlite3.Connection, event_id: str) -> WorkflowEvent:
        row = connection.execute(
            "SELECT * FROM workflow_events WHERE event_id=?", (event_id,)
        ).fetchone()
        if row is None:
            raise LookupError(event_id)
        return self._from_row(row)

    @staticmethod
    def _from_row(row: sqlite3.Row) -> WorkflowEvent:
        return WorkflowEvent(
            sequence=int(row["sequence"]),
            schema_id=row["schema_id"],
            schema_version=row["schema_version"],
            artifact_kind=row["artifact_kind"],
            event_id=row["event_id"],
            workflow_run_id=row["workflow_run_id"],
            aggregate_id=row["aggregate_id"],
            aggregate_type=row["aggregate_type"],
            event_type=row["event_type"],
            actor=row["actor"],
            occurred_at=row["occurred_at"],
            state_version_before=int(row["state_version_before"]),
            state_version_after=int(row["state_version_after"]),
            plan_revision=int(row["plan_revision"]),
            payload_digest=row["payload_digest"],
            payload_ref=row["payload_ref"],
            inline_payload=json.loads(row["inline_payload"]),
            idempotency_key=row["idempotency_key"],
            correlation_id=row["correlation_id"],
            causation_id=row["causation_id"],
        )
