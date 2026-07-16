# Workflow Skill Router V2 State、Goal 與 Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可從 append-only event 恢復、具 optimistic concurrency 與 idempotency 的 Phase／Workflow state machine，並以 host-owned Goal Binding、Work Graph 與候選狀態支援 Codex Goal 模式。

**Architecture:** Python core 以 SQLite event stream 作唯一 semantic mutation 真相，projection 只負責查詢並可由 event 重建；Phase gate 以 state version、plan revision 與 evidence digest 做 CAS。Native Goal 只投影成 Goal Binding，Router 只產生 complete／blocked candidate，不呼叫或偽造 host Goal 狀態。

**Tech Stack:** Python 3.11+、標準函式庫 `sqlite3`／`dataclasses`／`enum`／`hashlib`／`json`、`unittest`、SQLite WAL。

## Global Constraints

- Core 固定放在 `packages/router-core/src/workflow_skill_router/`，Python import namespace 固定為 `workflow_skill_router.*`。
- Runtime 只使用 Python 3.11+ 標準函式庫；不得把 MCP SDK 或 Node dependency 引入 core。
- `workflow_events` 是 append-only；client 不可指定 event ID、任意 event type、state after 或跳過 transition。
- 每個 semantic mutation 都要保存 actor、時間、state version、plan revision、idempotency key、correlation 與 causation。
- Completed Phase 不可覆寫或 reopen；修正只能建立帶 `supersedes_phase_id` 的 correction／revalidation Phase。
- Native Goal 由 Codex host 擁有；Router 只保存 projection 與狀態候選，不能建立、完成、阻塞、暫停、恢復或清除 native Goal。
- `status`、`side-question` 與 `unrelated` 不得改變 Goal semantic revision；`GOAL_SIDE_QUERY_OBSERVED` 只可追加 audit event。
- R2／R3 副作用必須有 intent 與 outcome；`unknown` outcome 不得自動 retry。
- 所有文字、資料、schema 與測試 fixture 使用 UTF-8；測試資料與註解使用繁體中文。
- SQLite 不得儲存 access token、password、cookie、private key、未清理秘密或不必要的完整 prompt／user content。
- 每次成功 `sync_runtime_context` 都必須先保存 canonical capability snapshot artifact，再 append server-owned `CAPABILITY_SNAPSHOT_CREATED`；若有 drift，再於同一 CAS append batch 追加一筆或多筆 `CAPABILITY_DRIFT_DETECTED`。`capability_snapshots`／`capabilities` 只能由這些 event replay，不能成為第二個真相來源。
- Discovery 不讀 instruction body；只有通過 Explicit Skill Lock／consent 的 capability 才能在 lease activation 計算實際 content digest。該 digest 必須綁定 server-side lease binding 並於每次 invocation 重驗；installer claim 不符或 body 改變立即令 lease 失效。
- `sensitivity=restricted` artifact 必須透過注入的 `ArtifactProtector` 與可驗證 OS-private directory；平台無法保證加密／ACL 時 fail closed，絕不退回一般明文檔案。
- 每個 task 先得到預期的失敗，再寫最小實作、跑 focused tests，最後才 commit；不得順手修改 V1 scripts。

---

## File Structure

```text
packages/router-core/src/workflow_skill_router/
  persistence/
    __init__.py
    migrator.py                 # migration checksum 與順序執行
    sqlite_store.py             # append/read、CAS、idempotency receipt
    artifacts.py                # content-addressed file store 與 digest 驗證
    projections.py              # checkpoint、projection rebuild 與查詢
    migrations/
      __init__.py
      0001_workflow_state.sql   # event、state、Goal 與 policy projection
  workflow/
    __init__.py
    events.py                   # server-owned EventDraft/WorkflowEvent
    models.py                   # WorkflowRun、PhaseRun、Evidence、status enum
    transitions.py              # workflow/phase transition table 與 guards
    gates.py                    # mandatory gate、freshness 與 digest 驗證
    coordinator.py              # command -> event，禁止 raw append
    activation.py               # post-consent content digest 與 lease binding
  goals/
    __init__.py
    models.py                   # GoalBinding、WorkGraph、WorkItem、coverage/candidate
    relations.py                # progress/steer/status/side-question/unrelated/none
    orchestrator.py             # DAG、reconciliation、next work 與 candidate
    candidates.py               # workflow complete 與三-turn blocked contract
  service_models.py             # MCP/CLI 共用 typed command/query/result
  service.py                    # RouterService application facade
packages/router-core/tests/
  persistence/test_sqlite_event_store.py
  persistence/test_artifact_store.py
  persistence/test_projection_rebuild.py
  workflow/test_transitions.py
  workflow/test_gates.py
  workflow/test_coordinator.py
  workflow/test_activation_content.py
  goals/test_goal_orchestrator.py
  goals/test_candidates.py
  integration/test_router_service.py
```

共享上游介面不得改名：

```python
from workflow_skill_router.capabilities.models import CapabilitySnapshot
from workflow_skill_router.routing.models import ExecutionLease, Route
from workflow_skill_router.routing.validator import (
    RouteValidationRequest,
    RouteValidationResult,
    RouteValidator,
    ValidationContext,
)
```

### Task 1: 建立 SQLite migration、append-only event store 與 idempotent CAS

**Files:**
- Modify: `packages/router-core/pyproject.toml`（將 `persistence/migrations/*.sql` 納入 package data）
- Create: `packages/router-core/src/workflow_skill_router/runtime.py`
- Create: `packages/router-core/src/workflow_skill_router/persistence/__init__.py`
- Create: `packages/router-core/src/workflow_skill_router/persistence/migrations/__init__.py`
- Create: `packages/router-core/src/workflow_skill_router/persistence/migrations/0001_workflow_state.sql`
- Create: `packages/router-core/src/workflow_skill_router/persistence/migrator.py`
- Create: `packages/router-core/src/workflow_skill_router/persistence/sqlite_store.py`
- Create: `packages/router-core/src/workflow_skill_router/persistence/artifacts.py`
- Create: `packages/router-core/src/workflow_skill_router/workflow/__init__.py`
- Create: `packages/router-core/src/workflow_skill_router/workflow/events.py`
- Test: `packages/router-core/tests/persistence/test_sqlite_event_store.py`
- Test: `packages/router-core/tests/persistence/test_artifact_store.py`

**Interfaces:**
- Consumes: `ArtifactEnvelope.to_dict() -> dict[str, Any]` from `schemas/artifacts.py` only for later serialization; Task 1 itself has no routing dependency.
- Produces: `Clock`／`IdFactory` protocols and `SystemClock`／`UuidFactory` production adapters；generic stream `EventDraft(...)`/`WorkflowEvent(...)`/`AppendResult` and generic CAS store；`ArtifactRef(digest, media_type, sensitivity, protection_kind, protection_ref)`（no absolute path）；`ArtifactMetadata(status, payload_present, ...)`；`ArtifactLifecycleReceipt(event_type, digest, reason, actor, occurred_at)`；`ArtifactProtector`/lifecycle ports；`ContentAddressedArtifactStore.put_bytes(data, media_type, sensitivity, producer) -> ArtifactRef`、`open_verified(digest)`、`metadata(digest)`、`tombstone(digest, reason, actor)`、`crypto_erase(digest, reason, actor)`。Workflow stream requires workflow_run_id；runtime-context uses None and aggregate identity。Stores require injected clock/ID ports；only composition chooses production adapters。

- [ ] **Step 1: Write failing CAS、idempotency 與 append-only tests**

```python
# packages/router-core/tests/persistence/test_sqlite_event_store.py
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from workflow_skill_router.schemas.artifacts import canonical_json_bytes
from workflow_skill_router.persistence.migrator import migrate
from workflow_skill_router.persistence.sqlite_store import (
    ConcurrencyConflict,
    IdempotencyConflict,
    SQLiteEventStore,
)
from workflow_skill_router.workflow.events import EventDraft


class FixedClock:
    def __init__(self, value: str) -> None:
        self._value = datetime.fromisoformat(value)

    def now_utc(self) -> datetime:
        return self._value


class SequenceIdFactory:
    def __init__(self, prefix: str) -> None:
        self._prefix = prefix
        self._next = 0

    def new_event_id(self) -> str:
        self._next += 1
        return f"{self._prefix}-{self._next:04d}"


class SQLiteEventStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.database = Path(self.directory.name) / "router.db"
        migrate(self.database)
        self.store = SQLiteEventStore(
            self.database,
            clock=FixedClock("2026-07-15T00:00:00+00:00"),
            id_factory=SequenceIdFactory("event"),
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def draft(self, event_type: str = "WORKFLOW_CREATED") -> EventDraft:
        return EventDraft(
            workflow_run_id="wf-1",
            event_type=event_type,
            actor="orchestrator",
            plan_revision=1,
            inline_payload={"objective_digest": "sha256:abc"},
            payload_ref=None,
            correlation_id="corr-1",
            causation_id=None,
        )

    def test_append_assigns_server_event_identity_and_monotonic_version(self) -> None:
        result = self.store.append("workflow", "wf-1", [self.draft()], 0, "create-1")
        self.assertFalse(result.replayed)
        self.assertEqual(1, result.resulting_state_version)
        self.assertEqual(0, result.events[0].state_version_before)
        self.assertEqual(1, result.events[0].state_version_after)
        self.assertTrue(result.events[0].event_id)

    def test_same_idempotency_key_replays_original_receipt(self) -> None:
        first = self.store.append("workflow", "wf-1", [self.draft()], 0, "create-1")
        replay = self.store.append("workflow", "wf-1", [self.draft()], 0, "create-1")
        self.assertTrue(replay.replayed)
        self.assertEqual(first.events[0].event_id, replay.events[0].event_id)
        self.assertEqual(1, len(self.store.read_stream("workflow", "wf-1")))

    def test_fixed_clock_and_id_factory_make_repeated_fresh_exports_byte_identical(self) -> None:
        exports = []
        for suffix in ("a", "b"):
            database = Path(self.directory.name) / f"router-{suffix}.db"
            migrate(database)
            store = SQLiteEventStore(
                database,
                clock=FixedClock("2026-07-15T00:00:00+00:00"),
                id_factory=SequenceIdFactory("event"),
            )
            store.append("workflow", "wf-1", [self.draft()], 0, "create-1")
            exports.append(canonical_json_bytes([item.to_dict() for item in store.read_stream("workflow", "wf-1")]))
        self.assertEqual(exports[0], exports[1])

    def test_same_idempotency_key_with_different_command_is_rejected(self) -> None:
        self.store.append("workflow", "wf-1", [self.draft()], 0, "create-1")
        with self.assertRaises(IdempotencyConflict):
            self.store.append("workflow", "wf-1", [self.draft("WORKFLOW_TRANSITIONED")], 0, "create-1")

    def test_stale_expected_version_is_rejected(self) -> None:
        self.store.append("workflow", "wf-1", [self.draft()], 0, "create-1")
        with self.assertRaises(ConcurrencyConflict):
            self.store.append("workflow", "wf-1", [self.draft("WORKFLOW_TRANSITIONED")], 0, "run-1")

    def test_database_rejects_update_or_delete_of_event(self) -> None:
        event = self.store.append("workflow", "wf-1", [self.draft()], 0, "create-1").events[0]
        with sqlite3.connect(self.database) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE workflow_events SET actor='竄改' WHERE event_id=?", (event.event_id,))
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("DELETE FROM workflow_events WHERE event_id=?", (event.event_id,))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused test and confirm the red state**

Run:

```powershell
$env:PYTHONPATH = "packages/router-core/src"
py -3.11 -m unittest packages/router-core/tests/persistence/test_sqlite_event_store.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'workflow_skill_router.persistence'`.

- [ ] **Step 3: Add the migration with immutable event triggers and all state/Goal projections**

```sql
-- packages/router-core/src/workflow_skill_router/persistence/migrations/0001_workflow_state.sql
PRAGMA foreign_keys = ON;

CREATE TABLE schema_migrations (
    version TEXT PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
CREATE TABLE aggregate_versions (
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version >= 0),
    PRIMARY KEY (aggregate_type, aggregate_id)
);
CREATE TABLE command_receipts (
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_digest TEXT NOT NULL,
    event_ids_json TEXT NOT NULL,
    resulting_state_version INTEGER NOT NULL,
    PRIMARY KEY (aggregate_type, aggregate_id, idempotency_key)
);
CREATE TABLE workflow_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    schema_id TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    artifact_kind TEXT NOT NULL CHECK (artifact_kind = 'workflow-event'),
    event_id TEXT NOT NULL UNIQUE,
    workflow_run_id TEXT,
    aggregate_id TEXT NOT NULL,
    aggregate_type TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    state_version_before INTEGER NOT NULL,
    state_version_after INTEGER NOT NULL,
    plan_revision INTEGER NOT NULL,
    payload_digest TEXT NOT NULL,
    payload_ref TEXT,
    inline_payload TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    causation_id TEXT,
    CHECK (state_version_after = state_version_before + 1),
    CHECK (
      (aggregate_type = 'workflow' AND workflow_run_id IS NOT NULL AND workflow_run_id = aggregate_id)
      OR (aggregate_type <> 'workflow' AND workflow_run_id IS NULL)
    )
);
CREATE INDEX idx_workflow_events_stream
    ON workflow_events (aggregate_type, aggregate_id, state_version_after);
CREATE INDEX idx_workflow_events_workflow
    ON workflow_events (workflow_run_id, sequence);
CREATE TRIGGER workflow_events_no_update
BEFORE UPDATE ON workflow_events BEGIN
    SELECT RAISE(ABORT, 'workflow_events is append-only');
END;
CREATE TRIGGER workflow_events_no_delete
BEFORE DELETE ON workflow_events BEGIN
    SELECT RAISE(ABORT, 'workflow_events is append-only');
END;

CREATE TABLE projection_checkpoints (
    projection_name TEXT PRIMARY KEY,
    last_sequence INTEGER NOT NULL
);
CREATE TABLE capability_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    runtime_fingerprint TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE capabilities (
    snapshot_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    availability_r0 TEXT NOT NULL,
    availability_r1 TEXT NOT NULL,
    availability_r2 TEXT NOT NULL,
    availability_r3 TEXT NOT NULL,
    availability_reasons_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, capability_id),
    FOREIGN KEY (snapshot_id) REFERENCES capability_snapshots(snapshot_id)
);
CREATE TABLE capability_drifts (
    drift_id TEXT PRIMARY KEY,
    previous_snapshot_id TEXT NOT NULL,
    current_snapshot_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    drift_kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY (previous_snapshot_id) REFERENCES capability_snapshots(snapshot_id),
    FOREIGN KEY (current_snapshot_id) REFERENCES capability_snapshots(snapshot_id)
);
CREATE TABLE workflow_runs (
    workflow_run_id TEXT PRIMARY KEY,
    objective_digest TEXT NOT NULL,
    envelope TEXT NOT NULL,
    status TEXT NOT NULL,
    plan_revision INTEGER NOT NULL,
    capability_snapshot_id TEXT NOT NULL,
    current_phase_id TEXT,
    paused_from_status TEXT,
    awaiting_from_status TEXT,
    pause_reason TEXT,
    state_version INTEGER NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE phase_runs (
    phase_id TEXT PRIMARY KEY,
    workflow_run_id TEXT NOT NULL,
    work_item_id TEXT NOT NULL,
    status TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,
    supersedes_phase_id TEXT,
    state_version INTEGER NOT NULL,
    evidence_digest TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY (workflow_run_id) REFERENCES workflow_runs(workflow_run_id)
);
CREATE UNIQUE INDEX idx_phase_one_active_per_workflow
    ON phase_runs(workflow_run_id) WHERE status = 'active';
CREATE TABLE goal_bindings (
    goal_binding_id TEXT PRIMARY KEY,
    host_goal_id TEXT,
    goal_revision INTEGER NOT NULL,
    host_goal_revision TEXT,
    source TEXT NOT NULL CHECK (source IN ('native', 'managed')),
    objective_digest TEXT NOT NULL,
    status_snapshot TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE goal_revisions (
    goal_binding_id TEXT NOT NULL,
    goal_revision INTEGER NOT NULL,
    objective_digest TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (goal_binding_id, goal_revision),
    FOREIGN KEY (goal_binding_id) REFERENCES goal_bindings(goal_binding_id)
);
CREATE TABLE goal_acceptance_coverage (
    goal_binding_id TEXT NOT NULL,
    goal_revision INTEGER NOT NULL,
    criterion_id TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (goal_binding_id, goal_revision, criterion_id)
);
CREATE TABLE work_graphs (
    work_graph_id TEXT PRIMARY KEY,
    goal_binding_id TEXT NOT NULL,
    plan_revision INTEGER NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE work_items (
    work_item_id TEXT PRIMARY KEY,
    work_graph_id TEXT NOT NULL,
    status TEXT NOT NULL,
    required INTEGER NOT NULL CHECK (required IN (0, 1)),
    envelope TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY (work_graph_id) REFERENCES work_graphs(work_graph_id)
);
CREATE TABLE workflow_completion_candidates (
    candidate_id TEXT PRIMARY KEY,
    workflow_run_id TEXT NOT NULL,
    state_version INTEGER NOT NULL,
    evidence_digest TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE artifact_metadata (
    digest TEXT PRIMARY KEY,
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    media_type TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    producer TEXT NOT NULL,
    relative_path TEXT NOT NULL UNIQUE,
    protection_ref TEXT,
    created_at TEXT NOT NULL,
    tombstoned_at TEXT,
    erased_at TEXT,
    payload_json TEXT NOT NULL
);
CREATE TABLE goal_status_candidates (
    candidate_id TEXT PRIMARY KEY,
    goal_binding_id TEXT NOT NULL,
    candidate_type TEXT NOT NULL CHECK (candidate_type IN ('complete', 'blocked')),
    goal_revision INTEGER NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE evidence_metadata (
    evidence_id TEXT PRIMARY KEY,
    workflow_run_id TEXT NOT NULL,
    phase_id TEXT NOT NULL,
    content_digest TEXT NOT NULL,
    produced_at TEXT NOT NULL,
    workspace_revision TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE consent_grants (
    grant_id TEXT PRIMARY KEY,
    workflow_run_id TEXT NOT NULL,
    scope_anchor_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    context_fingerprint TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE consent_rejections (
    rejection_id TEXT PRIMARY KEY,
    workflow_run_id TEXT NOT NULL,
    scope_anchor_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    context_fingerprint TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE lease_content_bindings (
    lease_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    binding_kind TEXT NOT NULL CHECK (binding_kind IN ('instruction-content','tool-schema','runtime-contract')),
    trusted_binding_digest TEXT NOT NULL,
    observed_binding_digest TEXT NOT NULL,
    binding_receipt_digest TEXT NOT NULL,
    bound_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (lease_id, capability_id)
);
CREATE TABLE lease_activation_consumptions (
    lease_id TEXT PRIMARY KEY,
    capability_id TEXT NOT NULL,
    scope_anchor_id TEXT NOT NULL,
    purpose TEXT NOT NULL,
    invocation_context_digest TEXT NOT NULL,
    invocation_digest TEXT NOT NULL,
    action_digest TEXT NOT NULL,
    runtime_approval_ref TEXT,
    runtime_approval_scope_digest TEXT,
    binding_kind TEXT NOT NULL CHECK (binding_kind IN ('instruction-content','tool-schema','runtime-contract')),
    observed_binding_digest TEXT NOT NULL,
    binding_receipt_digest TEXT NOT NULL,
    state_version INTEGER NOT NULL,
    consumption_version INTEGER NOT NULL CHECK (consumption_version = 1),
    consumed_at TEXT NOT NULL,
    reservation_digest TEXT NOT NULL,
    activation_status TEXT NOT NULL CHECK (activation_status IN ('reserved','activated','failed','unknown')),
    activation_receipt_digest TEXT,
    activated_at TEXT
);
CREATE TABLE resource_locks (
    resource_lock_id TEXT PRIMARY KEY,
    workflow_run_id TEXT NOT NULL,
    resource_digest TEXT NOT NULL,
    mode TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE side_effect_attempts (
    attempt_id TEXT PRIMARY KEY,
    workflow_run_id TEXT NOT NULL,
    phase_id TEXT NOT NULL,
    action_digest TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'confirmed-success', 'confirmed-failure', 'unknown')),
    payload_json TEXT NOT NULL
);
```

- [ ] **Step 4: Implement deterministic migration and server-owned event values**

```python
# packages/router-core/src/workflow_skill_router/workflow/events.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class EventDraft:
    event_type: str
    actor: str
    plan_revision: int
    inline_payload: Mapping[str, Any]
    payload_ref: str | None
    correlation_id: str
    causation_id: str | None
    workflow_run_id: str | None = None


@dataclass(frozen=True, slots=True)
class WorkflowEvent:
    sequence: int
    schema_id: str
    schema_version: str
    artifact_kind: str
    event_id: str
    workflow_run_id: str | None
    aggregate_id: str
    aggregate_type: str
    event_type: str
    actor: str
    occurred_at: str
    state_version_before: int
    state_version_after: int
    plan_revision: int
    payload_digest: str
    payload_ref: str | None
    inline_payload: Mapping[str, Any]
    idempotency_key: str
    correlation_id: str
    causation_id: str | None
```

```python
# packages/router-core/src/workflow_skill_router/persistence/migrator.py
from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path


def migrate(database: Path) -> None:
    database.parent.mkdir(parents=True, exist_ok=True)
    scripts = sorted(files("workflow_skill_router.persistence.migrations").iterdir(), key=lambda item: item.name)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        try:
            for script in scripts:
                if not script.name.endswith(".sql"):
                    continue
                version = script.name.split("_", 1)[0]
                sql = script.read_text(encoding="utf-8")
                checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
                exists = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
                ).fetchone()
                applied = None if not exists else connection.execute(
                    "SELECT checksum FROM schema_migrations WHERE version=?", (version,)
                ).fetchone()
                if applied is not None:
                    if applied[0] != checksum:
                        raise RuntimeError(f"Migration {version} checksum 不一致")
                    continue
                for statement in iter_complete_statements(sql):
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO schema_migrations(version, checksum, applied_at) VALUES (?, ?, ?)",
                    (version, checksum, datetime.now(UTC).isoformat()),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
```

`iter_complete_statements()` must accumulate UTF-8 SQL lines and yield only when `sqlite3.complete_statement(buffer)` is true, so trigger bodies remain one statement。Add a migration test that injects a failing second statement and proves both schema changes and the migration row roll back；run two concurrent migrators and prove the second observes the committed checksum instead of partially reapplying。

Implement `sqlite_store.py` with this exact public surface and transaction order:

```python
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

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
        request_digest = "sha256:" + hashlib.sha256(_canonical_json([
            {
                "workflow_run_id": item.workflow_run_id,
                "event_type": item.event_type,
                "actor": item.actor,
                "plan_revision": item.plan_revision,
                "inline_payload": item.inline_payload,
                "payload_ref": item.payload_ref,
                "correlation_id": item.correlation_id,
                "causation_id": item.causation_id,
            }
            for item in drafts
        ]).encode("utf-8")).hexdigest()
        with sqlite3.connect(self._database) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("BEGIN IMMEDIATE")
            receipt = connection.execute(
                "SELECT request_digest, event_ids_json, resulting_state_version FROM command_receipts "
                "WHERE aggregate_type=? AND aggregate_id=? AND idempotency_key=?",
                (aggregate_type, aggregate_id, idempotency_key),
            ).fetchone()
            if receipt is not None:
                if receipt["request_digest"] != request_digest:
                    connection.rollback()
                    raise IdempotencyConflict("相同 idempotency key 對應不同 command")
                ids = json.loads(receipt["event_ids_json"])
                events = tuple(self._read_event(connection, event_id) for event_id in ids)
                connection.commit()
                return AppendResult(events, receipt["resulting_state_version"], True)
            row = connection.execute(
                "SELECT state_version FROM aggregate_versions WHERE aggregate_type=? AND aggregate_id=?",
                (aggregate_type, aggregate_id),
            ).fetchone()
            current = 0 if row is None else int(row["state_version"])
            if current != expected_state_version:
                connection.rollback()
                raise ConcurrencyConflict(f"expected={expected_state_version}, actual={current}")
            events: list[WorkflowEvent] = []
            for draft in drafts:
                before = current
                current += 1
                payload_json = _canonical_json(draft.inline_payload)
                event_id = self._id_factory.new_event_id()
                occurred_at = self._clock.now_utc().isoformat()
                digest = "sha256:" + hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
                cursor = connection.execute(
                    "INSERT INTO workflow_events(schema_id,schema_version,artifact_kind,event_id,"
                    "workflow_run_id,aggregate_id,aggregate_type,event_type,actor,occurred_at,"
                    "state_version_before,state_version_after,plan_revision,payload_digest,payload_ref,"
                    "inline_payload,idempotency_key,correlation_id,causation_id) "
                    "VALUES ('workflow-skill-router/workflow-event','2.0.0-alpha.1','workflow-event',"
                    "?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (event_id, draft.workflow_run_id, aggregate_id, aggregate_type, draft.event_type,
                     draft.actor, occurred_at, before, current, draft.plan_revision, digest,
                     draft.payload_ref, payload_json, idempotency_key, draft.correlation_id,
                     draft.causation_id),
                )
                events.append(self._read_event(connection, event_id, int(cursor.lastrowid)))
            connection.execute(
                "INSERT INTO aggregate_versions VALUES (?, ?, ?) "
                "ON CONFLICT(aggregate_type,aggregate_id) DO UPDATE SET state_version=excluded.state_version",
                (aggregate_type, aggregate_id, current),
            )
            connection.execute(
                "INSERT INTO command_receipts VALUES (?, ?, ?, ?, ?, ?)",
                (aggregate_type, aggregate_id, idempotency_key, request_digest,
                 _canonical_json([event.event_id for event in events]), current),
            )
            connection.commit()
            return AppendResult(tuple(events), current, False)

    def read_stream(self, aggregate_type: str, aggregate_id: str, after_version: int = 0) -> tuple[WorkflowEvent, ...]:
        with sqlite3.connect(self._database) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT * FROM workflow_events WHERE aggregate_type=? AND aggregate_id=? "
                "AND state_version_after>? ORDER BY state_version_after",
                (aggregate_type, aggregate_id, after_version),
            ).fetchall()
            return tuple(self._from_row(row) for row in rows)

    def _read_event(self, connection: sqlite3.Connection, event_id: str, sequence: int | None = None) -> WorkflowEvent:
        row = connection.execute("SELECT * FROM workflow_events WHERE event_id=?", (event_id,)).fetchone()
        if row is None:
            raise LookupError(event_id)
        return self._from_row(row)

    @staticmethod
    def _from_row(row: sqlite3.Row) -> WorkflowEvent:
        return WorkflowEvent(
            sequence=int(row["sequence"]), schema_id=row["schema_id"], schema_version=row["schema_version"],
            artifact_kind=row["artifact_kind"], event_id=row["event_id"], workflow_run_id=row["workflow_run_id"],
            aggregate_id=row["aggregate_id"], aggregate_type=row["aggregate_type"], event_type=row["event_type"],
            actor=row["actor"], occurred_at=row["occurred_at"], state_version_before=int(row["state_version_before"]),
            state_version_after=int(row["state_version_after"]), plan_revision=int(row["plan_revision"]),
            payload_digest=row["payload_digest"], payload_ref=row["payload_ref"],
            inline_payload=json.loads(row["inline_payload"]), idempotency_key=row["idempotency_key"],
            correlation_id=row["correlation_id"], causation_id=row["causation_id"],
        )
```

Implement `artifacts.py` so every object path is derived only from a validated `sha256:<64 lowercase hex>` digest (`objects/aa/<remaining>`), stores only a relative path in SQLite, and re-hashes logical plaintext bytes on `open_verified()`。All writes use an exclusive same-directory temporary file, flush + `os.fsync()`, atomic `os.replace()`, then directory fsync where supported；failure cleanup may remove only that exact temporary file, never a directory or wildcard。

`ArtifactProtector` is an injected port with `protect(plaintext, digest) -> ProtectedArtifact(stored_bytes, protection_kind, protection_ref)`、`open_verified(path, protection_ref) -> bytes`、`verify_private_directory(root) -> bool`、`verify_effective_permissions(path) -> bool` and optional `destroy_key(protection_ref) -> None`。For `sensitivity="restricted"`, construction requires a protector and a dedicated OS-private root；the store verifies root, writes only `stored_bytes`, atomically publishes, then verifies effective ACL/mode and protector receipt. A permission protector may use identity bytes only when private-directory/file ACL proofs succeed；an encryption protector returns ciphertext plus key receipt。Any unavailable guarantee、protection failure or permission mismatch is a hard error and the object is not registered；there is never an unverified normal-file fallback。`protection_ref` may identify an OS-keystore key but must not contain key material。

`tombstone()` appends server-owned `EVENT_PAYLOAD_TOMBSTONED` through `ArtifactLifecycleEventSink`, marks metadata, and makes future `open_verified()` fail closed；`crypto_erase()` first destroys the referenced key for a restricted object, appends `ARTIFACT_CRYPTO_ERASED`, then marks `erased_at`。If key destruction or audit append fails, it must report an incomplete erase and must not claim success。Projection handlers later scrub payload references without mutating historical events。

`test_artifact_store.py` must prove identical bytes de-duplicate、tampered bytes fail closed、a forged `../` digest is rejected、metadata never stores an absolute user path、restricted writes fail without a protector、root/file permission verification failure does not register an artifact、permission protection verifies exact private ACL/mode、encryption protection never stores plaintext、tombstoned objects cannot reopen、and tombstone/crypto-erase emit the exact lifecycle event。Use injected fake protectors for deterministic tests；platform-specific ACL integration runs only where verifiable。

- [ ] **Step 5: Run the focused tests and migration twice**

Run:

```powershell
$env:PYTHONPATH = "packages/router-core/src"
py -3.11 -m unittest packages/router-core/tests/persistence/test_sqlite_event_store.py packages/router-core/tests/persistence/test_artifact_store.py -v
py -3.11 -c "import tempfile; from pathlib import Path; from workflow_skill_router.persistence.migrator import migrate; d=tempfile.TemporaryDirectory(); p=Path(d.name)/'router.db'; migrate(p); migrate(p); print('migration-ok'); d.cleanup()"
```

Expected: all four tests PASS and the second command prints `migration-ok` without checksum drift.

- [ ] **Step 6: Commit the event-store slice**

```powershell
git add packages/router-core/src/workflow_skill_router/runtime.py packages/router-core/src/workflow_skill_router/persistence packages/router-core/src/workflow_skill_router/workflow packages/router-core/tests/persistence/test_sqlite_event_store.py packages/router-core/tests/persistence/test_artifact_store.py
git commit -m "feat(core): add append-only router event store"
```

### Task 2: 實作 Workflow／Phase state machine 與 evidence gate

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/workflow/models.py`
- Create: `packages/router-core/src/workflow_skill_router/workflow/transitions.py`
- Create: `packages/router-core/src/workflow_skill_router/workflow/gates.py`
- Test: `packages/router-core/tests/workflow/test_transitions.py`
- Test: `packages/router-core/tests/workflow/test_gates.py`

**Interfaces:**
- Consumes: `EventDraft` from Task 1; `ExecutionLease` and `Route` from `routing/models.py`.
- Produces: `WorkflowStatus`; `PhaseStatus`; `WorkflowRun`; `PhaseRun`; `Evidence`; `TransitionRequest`; `TransitionDecision`; `PhaseStateMachine.decide(phase, request, context) -> TransitionDecision`; `WorkflowStateMachine.decide(workflow, request, context) -> TransitionDecision`; `GateEvaluator.evaluate(request: GateEvaluationRequest) -> GateEvaluationResult`.

- [ ] **Step 1: Write transition and gate failure tests**

```python
# packages/router-core/tests/workflow/test_transitions.py
import unittest

from workflow_skill_router.workflow.models import ExitGate, PhaseRun, PhaseStatus, RoutingQuery
from workflow_skill_router.workflow.transitions import (
    InvalidTransition,
    PhaseStateMachine,
    TransitionContext,
    TransitionRequest,
)


def phase(status: PhaseStatus) -> PhaseRun:
    return PhaseRun(
        phase_id="phase-1", workflow_run_id="wf-1", work_item_id="item-1", name="實作",
        status=status, routing_query=RoutingQuery("sha256:objective", "實作", ("可驗證程式碼",), "R1"),
        route=None, capability_snapshot_id="snap-1", risk="R1", entry_conditions=("依賴完成",),
        exit_gate=ExitGate("gate-1", ("tests",), ("test-report",)), evidence_refs=("evidence-1",),
        inserted=False, sequence_source="initial-plan", plan_revision=1,
        state_version=2, evidence_digest="sha256:e1", supersedes_phase_id=None,
        paused_from_status=None, awaiting_from_status=None, pause_reason=None,
    )


class PhaseStateMachineTests(unittest.TestCase):
    def test_completed_phase_cannot_reopen(self) -> None:
        with self.assertRaises(InvalidTransition):
            PhaseStateMachine().decide(
                phase(PhaseStatus.COMPLETED),
                TransitionRequest(PhaseStatus.ACTIVE, "agent", 2, "sha256:e1", 1),
                TransitionContext(True, True, True, False, False),
            )

    def test_unknown_side_effect_cannot_enter_verifying(self) -> None:
        with self.assertRaises(InvalidTransition):
            PhaseStateMachine().decide(
                phase(PhaseStatus.ACTIVE),
                TransitionRequest(PhaseStatus.VERIFYING, "agent", 2, "sha256:e1", 1),
                TransitionContext(True, True, True, True, False),
            )

    def test_pause_preserves_resume_origin(self) -> None:
        decision = PhaseStateMachine().decide(
            phase(PhaseStatus.ACTIVE),
            TransitionRequest(PhaseStatus.PAUSED, "host-adapter", 2, "sha256:e1", 1),
            TransitionContext(True, True, True, False, False),
        )
        self.assertEqual(PhaseStatus.ACTIVE, decision.paused_from_status)
```

```python
# packages/router-core/tests/workflow/test_gates.py
import unittest
from datetime import UTC, datetime, timedelta

from workflow_skill_router.workflow.gates import GateEvaluator, GateEvaluationRequest, GateCheck


class GateEvaluatorTests(unittest.TestCase):
    def test_advisory_pass_cannot_offset_mandatory_failure(self) -> None:
        result = GateEvaluator().evaluate(GateEvaluationRequest(
            workflow_run_id="wf-1", phase_id="phase-1", expected_state_version=3,
            expected_plan_revision=1, expected_evidence_digest="sha256:e1",
            actual_state_version=3, actual_plan_revision=1, actual_evidence_digest="sha256:e1",
            checks=(GateCheck("test", True, False, "測試失敗"), GateCheck("model-assessment", False, True, "外觀良好")),
        ))
        self.assertFalse(result.passed)
        self.assertEqual(("測試失敗",), result.mandatory_failures)

    def test_digest_change_rejects_gate_as_concurrency_conflict(self) -> None:
        result = GateEvaluator().evaluate(GateEvaluationRequest(
            workflow_run_id="wf-1", phase_id="phase-1", expected_state_version=3,
            expected_plan_revision=1, expected_evidence_digest="sha256:old",
            actual_state_version=3, actual_plan_revision=1, actual_evidence_digest="sha256:new",
            checks=(GateCheck("test", True, True, ""),),
        ))
        self.assertEqual("conflict", result.status)
```

- [ ] **Step 2: Run tests and confirm missing state modules**

Run: `py -3.11 -m unittest packages/router-core/tests/workflow/test_transitions.py packages/router-core/tests/workflow/test_gates.py -v`

Expected: FAIL with imports for `state.models`, `state.transitions` and `state.gates` missing.

- [ ] **Step 3: Implement immutable models and explicit transition tables**

```python
# packages/router-core/src/workflow_skill_router/workflow/models.py
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from workflow_skill_router.routing.models import Route, RoutingEnvelope


class WorkflowStatus(StrEnum):
    DRAFT = "draft"
    DISCOVERING = "discovering"
    PLANNED = "planned"
    RUNNING = "running"
    GATE_EVALUATING = "gate-evaluating"
    REROUTING = "rerouting"
    AWAITING_APPROVAL = "awaiting-approval"
    PAUSED = "paused"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class PhaseStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    ACTIVE = "active"
    VERIFYING = "verifying"
    REROUTING = "rerouting"
    AWAITING_APPROVAL = "awaiting-approval"
    PAUSED = "paused"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class WorkflowRun:
    workflow_run_id: str
    parent_workflow_run_id: str | None
    objective: str
    objective_digest: str
    scope: tuple[str, ...]
    constraints: tuple[str, ...]
    envelope: RoutingEnvelope
    status: WorkflowStatus
    plan_revision: int
    capability_snapshot_id: str
    current_phase_id: str | None
    paused_from_status: WorkflowStatus | None
    awaiting_from_status: WorkflowStatus | None
    pause_reason: str | None
    state_version: int


@dataclass(frozen=True, slots=True)
class RoutingQuery:
    objective_digest: str
    phase_purpose: str
    required_outputs: tuple[str, ...]
    risk: str


@dataclass(frozen=True, slots=True)
class ExitGate:
    gate_id: str
    mandatory_checks: tuple[str, ...]
    evidence_requirements: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PhaseRun:
    phase_id: str
    workflow_run_id: str
    work_item_id: str
    name: str
    status: PhaseStatus
    routing_query: RoutingQuery
    route: Route | None
    capability_snapshot_id: str
    risk: str
    entry_conditions: tuple[str, ...]
    exit_gate: ExitGate
    evidence_refs: tuple[str, ...]
    inserted: bool
    sequence_source: str
    plan_revision: int
    state_version: int
    evidence_digest: str
    supersedes_phase_id: str | None
    paused_from_status: PhaseStatus | None
    awaiting_from_status: PhaseStatus | None
    pause_reason: str | None
```

Use these exact allowed edges in `transitions.py`; actor and guards are checked after edge lookup:

```python
WORKFLOW_EDGES = {
    ("draft", "discovering"), ("discovering", "planned"), ("planned", "running"),
    ("running", "gate-evaluating"), ("gate-evaluating", "running"),
    ("gate-evaluating", "completed"), ("awaiting-approval", "rerouting"),
    ("paused", "rerouting"), ("blocked", "rerouting"),
    ("rerouting", "planned"), ("rerouting", "running"),
}
PHASE_EDGES = {
    ("pending", "ready"), ("ready", "active"), ("active", "verifying"),
    ("verifying", "completed"), ("awaiting-approval", "rerouting"),
    ("paused", "rerouting"), ("rerouting", "ready"),
    ("verifying", "active"), ("verifying", "rerouting"), ("verifying", "failed"),
    ("pending", "skipped"), ("ready", "skipped"),
}
WAIT_TARGETS = {"awaiting-approval", "paused", "blocked"}
TERMINAL_TARGETS = {"completed", "cancelled", "failed"}
```

`TransitionRequest` must carry `expected_state_version`, `expected_evidence_digest` and `expected_plan_revision`; `TransitionContext` must carry `entry_conditions_met`, `route_and_lease_valid`, `runtime_approval_valid`, `unknown_side_effect`, `mandatory_gate_failed`. Reject version/digest/revision drift before evaluating the edge. Allow the spec's `any non-terminal` wait/reroute/terminal transitions only for the documented actors, and persist `paused_from_status` or `awaiting_from_status` in `TransitionDecision`.

- [ ] **Step 4: Implement deterministic gate evaluation**

```python
# packages/router-core/src/workflow_skill_router/workflow/gates.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GateCheck:
    check_type: str
    mandatory: bool
    passed: bool
    reason: str


@dataclass(frozen=True, slots=True)
class GateEvaluationRequest:
    workflow_run_id: str
    phase_id: str
    expected_state_version: int
    expected_plan_revision: int
    expected_evidence_digest: str
    actual_state_version: int
    actual_plan_revision: int
    actual_evidence_digest: str
    checks: tuple[GateCheck, ...]


@dataclass(frozen=True, slots=True)
class GateEvaluationResult:
    status: str
    passed: bool
    mandatory_failures: tuple[str, ...]
    evidence_digest: str


class GateEvaluator:
    def evaluate(self, request: GateEvaluationRequest) -> GateEvaluationResult:
        if (
            request.expected_state_version != request.actual_state_version
            or request.expected_plan_revision != request.actual_plan_revision
            or request.expected_evidence_digest != request.actual_evidence_digest
        ):
            return GateEvaluationResult("conflict", False, ("state、plan 或 evidence 已變更",), request.actual_evidence_digest)
        failures = tuple(check.reason for check in request.checks if check.mandatory and not check.passed)
        return GateEvaluationResult("evaluated", not failures, failures, request.actual_evidence_digest)
```

- [ ] **Step 5: Run focused tests**

Run: `py -3.11 -m unittest packages/router-core/tests/workflow/test_transitions.py packages/router-core/tests/workflow/test_gates.py -v`

Expected: all tests PASS; completed reopen、unknown outcome 與 digest drift tests remain green.

- [ ] **Step 6: Commit the state-machine slice**

```powershell
git add packages/router-core/src/workflow_skill_router/workflow packages/router-core/tests/workflow/test_transitions.py packages/router-core/tests/workflow/test_gates.py
git commit -m "feat(core): enforce workflow phase state machine"
```

### Task 3: 建立 projection catch-up、rebuild 與 typed observation coordinator

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/persistence/projections.py`
- Create: `packages/router-core/src/workflow_skill_router/workflow/observations.py`
- Create: `packages/router-core/src/workflow_skill_router/workflow/coordinator.py`
- Test: `packages/router-core/tests/persistence/test_projection_rebuild.py`
- Test: `packages/router-core/tests/persistence/test_capability_snapshot_replay.py`
- Test: `packages/router-core/tests/workflow/test_coordinator.py`

**Interfaces:**
- Consumes: `SQLiteEventStore.append/read_stream` and `ContentAddressedArtifactStore.open_verified()` from Task 1; `CapabilitySnapshot`／risk-aware availability from Plan 01; state decisions from Task 2.
- Produces: `ProjectionRunner.catch_up() -> int`; `rebuild() -> int`; `WorkflowProjection.get_workflow(id) -> WorkflowRun | None`; `get_phase(id) -> PhaseRun | None`; `CapabilitySnapshotProjection.require(id) -> CapabilitySnapshot`; strict frozen `ActivationObservation`、`EvidenceObservation`、`SideEffectIntentObservation`、`SideEffectOutcomeObservation`、`PauseRequestObservation` union；`RecordObservationCommand`; `WorkEventCoordinator.record(command) -> AppendResult`.

- [ ] **Step 1: Write replay and raw-event rejection tests**

```python
# packages/router-core/tests/workflow/test_coordinator.py
import unittest

from workflow_skill_router.workflow.coordinator import RecordObservationCommand, WorkEventCoordinator
from workflow_skill_router.workflow.observations import (
    EvidenceObservation, PauseRequestObservation, SideEffectOutcomeObservation,
)


class CoordinatorTests(unittest.TestCase):
    def test_decoder_rejects_raw_event_actor_plan_status_and_payload(self) -> None:
        for field, value in (
            ("event_type", "PHASE_TRANSITIONED"), ("actor", "client"),
            ("plan_revision", 999), ("status", "completed"), ("payload", {"passed": True}),
        ):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "unknown field"):
                decode_record_observation({**VALID_EVIDENCE_COMMAND_JSON, field: value})

    def test_side_effect_outcome_requires_original_intent_digest(self) -> None:
        command = self.command(SideEffectOutcomeObservation(
            intent_id="intent-1", action_digest="sha256:wrong",
            outcome_receipt_ref="host-outcome-7",
        ))
        with self.assertRaisesRegex(ObservationIntegrityError, "side_effect_receipt_mismatch"):
            self.coordinator.record(command)

    def test_evidence_pass_fail_is_derived_from_verified_receipt(self) -> None:
        command = self.command(EvidenceObservation(
            gate_id="gate-1", evidence_kind="test-result", evidence_receipt_ref="evidence-7",
        ))
        append = self.coordinator.record(command)
        self.assertEqual("EVIDENCE_RECORDED", append.events[0].event_type)
        self.assertEqual("passed", append.events[0].inline_payload["verified_status"])
        self.assertFalse(hasattr(command.observation, "status"))

    def test_pause_request_must_pass_state_machine(self) -> None:
        seed_terminal_phase(self.coordinator, "phase-1")
        command = self.command(PauseRequestObservation(reason_code="dependency-wait", blocker_ref="blocker-1"))
        with self.assertRaisesRegex(InvalidTransition, "terminal"):
            self.coordinator.record(command)
```

```python
# packages/router-core/tests/persistence/test_projection_rebuild.py
import tempfile
import unittest
from pathlib import Path

from workflow_skill_router.persistence.migrator import migrate
from workflow_skill_router.persistence.projections import ProjectionRunner, WorkflowProjection
from workflow_skill_router.persistence.sqlite_store import SQLiteEventStore
from workflow_skill_router.runtime import SystemClock, UuidFactory
from workflow_skill_router.workflow.events import EventDraft


class ProjectionTests(unittest.TestCase):
    def test_rebuild_produces_same_workflow_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "router.db"
            migrate(database)
            store = SQLiteEventStore(database, clock=SystemClock(), id_factory=UuidFactory())
            store.append("workflow", "wf-1", [EventDraft(
                event_type="WORKFLOW_CREATED", actor="orchestrator", plan_revision=1,
                inline_payload={"objective_digest": "sha256:o", "envelope": "phased", "status": "draft",
                                "capability_snapshot_id": "snap-1"},
                payload_ref=None, correlation_id="corr-1", causation_id=None,
                workflow_run_id="wf-1",
            )], 0, "create-1")
            runner = ProjectionRunner(database)
            runner.catch_up()
            before = WorkflowProjection(database).get_workflow("wf-1")
            runner.rebuild()
            after = WorkflowProjection(database).get_workflow("wf-1")
            self.assertEqual(before, after)
```

`test_capability_snapshot_replay.py` must start from an event-only database plus the artifact object store, append one server-owned `CAPABILITY_SNAPSHOT_CREATED` and a typed `CAPABILITY_DRIFT_DETECTED` whose `payload_ref` and digest point to canonical artifacts, run catch-up, delete/rebuild all projections, and compare canonical rows byte-for-byte。It also asserts every capability row has non-null `availability_r0`／`r1`／`r2`／`r3`；a missing、tampered or digest-mismatched artifact makes replay fail closed without advancing the checkpoint；and replaying a newer snapshot with a removed capability does not leave that capability under the new snapshot ID or copy stale rows forward。

- [ ] **Step 2: Run tests and confirm missing coordinator/projection modules**

Run: `py -3.11 -m unittest packages/router-core/tests/workflow/test_coordinator.py packages/router-core/tests/persistence/test_projection_rebuild.py packages/router-core/tests/persistence/test_capability_snapshot_replay.py -v`

Expected: FAIL because `state.coordinator` and `persistence.projections` do not exist.

- [ ] **Step 3: Implement allowlisted observation mapping**

```python
# packages/router-core/src/workflow_skill_router/workflow/coordinator.py
from __future__ import annotations

from dataclasses import dataclass

from workflow_skill_router.persistence.sqlite_store import AppendResult, SQLiteEventStore
from workflow_skill_router.workflow.events import EventDraft
from workflow_skill_router.workflow.observations import (
    ActivationObservation, EvidenceObservation, Observation,
    PauseRequestObservation, SideEffectIntentObservation, SideEffectOutcomeObservation,
)


@dataclass(frozen=True, slots=True)
class RecordObservationCommand:
    workflow_run_id: str
    phase_id: str
    observation: Observation
    expected_state_version: int
    idempotency_key: str
    correlation_id: str


class WorkEventCoordinator:
    def __init__(self, store: SQLiteEventStore, context_repository, activation_verifier,
                 evidence_verifier, side_effect_verifier, transition_coordinator) -> None:
        self._store = store
        self._contexts = context_repository
        self._activations = activation_verifier
        self._evidence = evidence_verifier
        self._side_effects = side_effect_verifier
        self._transitions = transition_coordinator

    def record(self, command: RecordObservationCommand) -> AppendResult:
        context = self._contexts.require(
            command.workflow_run_id, command.phase_id, command.expected_state_version,
        )
        observation = command.observation
        if isinstance(observation, ActivationObservation):
            verified = self._activations.resolve_and_verify(
                observation.activation_receipt_ref, context=context,
            )
            draft = context.event_draft(
                "CAPABILITY_ACTIVATION_OBSERVED", verified.to_event_payload(),
                correlation_id=command.correlation_id,
            )
        elif isinstance(observation, EvidenceObservation):
            verified = self._evidence.resolve_and_verify(
                observation.evidence_receipt_ref,
                expected_gate_id=observation.gate_id,
                expected_kind=observation.evidence_kind,
                context=context,
            )
            draft = context.event_draft(
                "EVIDENCE_RECORDED", verified.to_event_payload(),
                correlation_id=command.correlation_id,
            )
        elif isinstance(observation, SideEffectIntentObservation):
            verified = self._side_effects.verify_intent(observation.intent_receipt_ref, context)
            draft = context.event_draft(
                "SIDE_EFFECT_INTENT_RECORDED", verified.to_event_payload(),
                correlation_id=command.correlation_id,
            )
        elif isinstance(observation, SideEffectOutcomeObservation):
            verified = self._side_effects.verify_outcome(
                observation.outcome_receipt_ref,
                expected_intent_id=observation.intent_id,
                expected_action_digest=observation.action_digest,
                context=context,
            )
            draft = context.event_draft(
                "SIDE_EFFECT_OUTCOME_RECORDED", verified.to_event_payload(),
                correlation_id=command.correlation_id,
            )
        elif isinstance(observation, PauseRequestObservation):
            draft = self._transitions.decide_pause_and_build_draft(
                context=context,
                reason_code=observation.reason_code,
                blocker_ref=observation.blocker_ref,
                correlation_id=command.correlation_id,
            )
        else:
            raise TypeError("unsupported typed observation")
        return self._store.append(
            "workflow", command.workflow_run_id, [draft],
            command.expected_state_version, command.idempotency_key,
        )
```

`observations.py` provides strict discriminated JSON codecs with `additionalProperties:false` semantics。Public DTOs contain only opaque receipt refs and semantic request fields；they contain no actor、event type、status/pass/fail、plan revision、causation、inline payload、lease truth or authority flags。`WorkEventContextRepository` derives authenticated actor、current plan revision、phase/workflow state、causation and expected scope from projections。Receipt verifiers bind phase/workflow、lease/action/gate、producer、artifact digest and status；the coordinator copies only verified payloads。Pause is a request routed through Task 2 transition rules and cannot directly emit a chosen status/event。Any receipt mismatch or illegal transition fails before append。

- [ ] **Step 4: Implement checkpointed projection replay**

`ProjectionRunner.catch_up()` must open `BEGIN IMMEDIATE`, read events after `projection_checkpoints.last_sequence`, apply each event to the relevant table, then update the checkpoint in the same transaction. Implement handlers for every event that changes a persisted projection; unknown schema versions fail closed。`rebuild()` uses the same connection/transaction and an internal `_apply_pending(connection)` helper：clear child tables before parent tables、reset the checkpoint、replay all events、and commit once。It must not call the public `catch_up()` inside an active transaction。

```python
PROJECTION_CLEAR_ORDER = (
    "side_effect_attempts", "resource_locks", "lease_content_bindings", "lease_activation_consumptions",
    "consent_rejections", "consent_grants",
    "evidence_metadata", "goal_status_candidates", "workflow_completion_candidates",
    "work_items", "work_graphs", "goal_acceptance_coverage", "goal_revisions",
    "goal_bindings", "phase_runs", "workflow_runs", "capability_drifts",
    "capabilities", "capability_snapshots",
)
SUPPORTED_EVENT_SCHEMA = ("workflow-skill-router/workflow-event", "2.0.0-alpha.1", "workflow-event")
```

For `WORKFLOW_CREATED`, insert a `workflow_runs` row with `state_version_after`. For `WORKFLOW_TRANSITIONED` and `PHASE_TRANSITIONED`, update only if the stored version equals `state_version_before`; if not, raise `ProjectionConflict`. For `SIDE_EFFECT_OUTCOME_RECORDED`, update the matching attempt only when action digest matches. For `CAPABILITY_CONTENT_BOUND`, insert the server-issued tagged activation binding (`instruction-content|tool-schema|runtime-contract`) and reject duplicates with different kind/trusted/observed/receipt digests。Keep all payload serialization canonical UTF-8 JSON.

For `CAPABILITY_SNAPSHOT_CREATED`, validate the inline identity (`snapshot_id`、schema version、runtime fingerprint、provider revisions、provider failure summary、artifact digest), load `payload_ref` only through `ContentAddressedArtifactStore.open_verified()`, decode a typed `CapabilitySnapshot` through Plan 01 `CAPABILITY_SCHEMA_REGISTRY`, and verify its canonical digest／snapshot ID before insert。Insert the parent `capability_snapshots` row first, then exactly that artifact's `capabilities` children with all four materialized risk availability columns and canonical reasons JSON；never clone rows from the previous snapshot, so removals cannot survive as stale children。The inline event must never contain the full snapshot、raw prompts、credentials or instruction body。`CAPABILITY_DRIFT_DETECTED` has an exact frozen `CapabilityDriftEventIdentity(drift_id, previous_snapshot_id, current_snapshot_id, capability_id, kind, artifact_digest)` encoded with no extra fields；its `payload_ref` addresses the full Plan 01 drift envelope。Projection verifies digest/ref and decodes the typed add／remove／rename／semantic-metadata／instruction-content／tool-schema／auth／policy／runtime-exposure record through that same registry, then confirms every identity field matches before insert；neither event may be client-authored。

Add a rebuild test with a CapabilitySnapshot→Capability、Workflow→Phase and GoalBinding→GoalRevision→WorkGraph→WorkItem chain while `PRAGMA foreign_keys=ON`; the clear order above is child-first (`capabilities` before `capability_snapshots`) and replay is parent-first。It must complete without disabling foreign keys and produce the same canonical read model。

- [ ] **Step 5: Run projection and coordinator tests**

Run: `py -3.11 -m unittest packages/router-core/tests/workflow/test_coordinator.py packages/router-core/tests/persistence/test_projection_rebuild.py packages/router-core/tests/persistence/test_capability_snapshot_replay.py -v`

Expected: all tests PASS；workflow 與 runtime-context stream envelope constraints 皆成立，capability rebuild result 在 canonical JSON 後 byte-for-byte equivalent，removed capability 不殘留。

- [ ] **Step 6: Commit the projection slice**

```powershell
git add packages/router-core/src/workflow_skill_router/persistence/projections.py packages/router-core/src/workflow_skill_router/workflow/observations.py packages/router-core/src/workflow_skill_router/workflow/coordinator.py packages/router-core/tests/persistence/test_projection_rebuild.py packages/router-core/tests/persistence/test_capability_snapshot_replay.py packages/router-core/tests/workflow/test_coordinator.py
git commit -m "feat(core): rebuild router state projections"
```

### Task 4: 建立 Goal Binding、message relation、Work Graph 與 reconciliation

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/goals/__init__.py`
- Create: `packages/router-core/src/workflow_skill_router/goals/models.py`
- Create: `packages/router-core/src/workflow_skill_router/goals/relations.py`
- Create: `packages/router-core/src/workflow_skill_router/goals/orchestrator.py`
- Test: `packages/router-core/tests/goals/test_goal_orchestrator.py`

**Interfaces:**
- Consumes: `EventDraft` and event store from Tasks 1/3; `RoutingEnvelope` from `routing/models.py`.
- Produces: `GoalBinding`; `AcceptanceCoverage`; `WorkGraph`; `WorkItem`; Goal relation constants over the single upstream `routing.models.GoalRelation`; `GoalOrchestrator.bind_native(...)`; `bind_managed(...)`; `classify_relation(...)`; `reconcile(...)`; `get_next_work(...)`.

- [ ] **Step 1: Write Goal authority and semantic-mutation tests**

```python
# packages/router-core/tests/goals/test_goal_orchestrator.py
import unittest

from workflow_skill_router.goals.models import GoalBinding, WorkGraph, WorkItem
from workflow_skill_router.goals.orchestrator import GoalOrchestrator, InvalidWorkGraph
from workflow_skill_router.routing.models import GoalRelation, RoutingEnvelope


class GoalOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orchestrator = GoalOrchestrator()

    def test_native_binding_requires_host_identity(self) -> None:
        with self.assertRaises(ValueError):
            self.orchestrator.bind_native(None, None, "建置 V2", "active", None)

    def test_status_relation_does_not_increment_semantic_revision(self) -> None:
        binding = self.orchestrator.bind_native("goal-7", "host-r3", "建置 V2", "active", None)
        result = self.orchestrator.observe_message(binding, GoalRelation.STATUS, "目前進度？")
        self.assertEqual(binding.goal_revision, result.binding.goal_revision)
        self.assertEqual("GOAL_SIDE_QUERY_OBSERVED", result.audit_event_type)
        self.assertIsNone(result.replacement_graph)

    def test_goal_edit_keeps_completed_items_and_replaces_unstarted_items(self) -> None:
        binding = self.orchestrator.bind_native("goal-7", "host-r3", "建置 V2", "active", None)
        graph = WorkGraph(
            "graph-1", binding.goal_binding_id, binding.objective_digest, 1, "coverage-1",
            (WorkItem("done", "m1", "已完成", True, "completed", RoutingEnvelope.SINGLE, (), (), (), ("goal-scope",), "policy-1", ("phase-done",)),
             WorkItem("next", "m1", "待處理", True, "pending", RoutingEnvelope.PHASED, ("done",), (), ("repo",), ("goal-scope",), "policy-1", ())),
        )
        revised = self.orchestrator.reconcile(binding, graph, "建置 V2 並新增 CLI", "host-r4")
        self.assertEqual("completed", revised.graph.items[0].status)
        self.assertEqual(2, revised.binding.goal_revision)

    def test_cycle_and_overlapping_ready_write_scopes_are_rejected(self) -> None:
        with self.assertRaises(InvalidWorkGraph):
            self.orchestrator.validate_graph((
                WorkItem("a", "m", "A", True, "ready", RoutingEnvelope.SINGLE, ("b",), (), ("repo",), ("goal-scope",), "policy-1", ()),
                WorkItem("b", "m", "B", True, "ready", RoutingEnvelope.SINGLE, ("a",), (), ("repo",), ("goal-scope",), "policy-1", ()),
            ))
```

- [ ] **Step 2: Run tests and confirm missing Goal modules**

Run: `py -3.11 -m unittest packages/router-core/tests/goals/test_goal_orchestrator.py -v`

Expected: FAIL because `workflow_skill_router.goals` is not implemented.

- [ ] **Step 3: Implement immutable Goal contracts**

```python
# packages/router-core/src/workflow_skill_router/goals/models.py
from __future__ import annotations

from dataclasses import dataclass

from workflow_skill_router.routing.models import RoutingEnvelope


@dataclass(frozen=True, slots=True)
class GoalBinding:
    goal_binding_id: str
    host_goal_id: str | None
    goal_revision: int
    host_goal_revision: str | None
    objective_digest: str
    objective_snapshot: str
    status_snapshot: str
    budget_snapshot: str | None
    synced_at: str
    source: str


@dataclass(frozen=True, slots=True)
class AcceptanceCoverage:
    criterion_id: str
    source_digest: str
    mandatory: bool
    work_item_ids: tuple[str, ...]
    gate_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    status: str


@dataclass(frozen=True, slots=True)
class WorkItem:
    work_item_id: str
    milestone_id: str
    title: str
    required: bool
    status: str
    envelope: RoutingEnvelope
    dependency_ids: tuple[str, ...]
    read_resources: tuple[str, ...]
    write_resources: tuple[str, ...]
    scope: tuple[str, ...]
    skill_policy_ref: str
    phase_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkGraph:
    work_graph_id: str
    goal_binding_id: str
    objective_digest: str
    plan_revision: int
    acceptance_coverage_ref: str
    items: tuple[WorkItem, ...]
```

```python
# packages/router-core/src/workflow_skill_router/goals/relations.py
from workflow_skill_router.routing.models import GoalRelation


SEMANTIC_MUTATION_ALLOWED = {GoalRelation.PROGRESS, GoalRelation.STEER}
CONTROL_QUERY_RELATIONS = {GoalRelation.STATUS}
DETACHED_RELATIONS = {GoalRelation.SIDE_QUESTION, GoalRelation.UNRELATED}
```

- [ ] **Step 4: Implement host-safe orchestration and DAG validation**

`GoalOrchestrator` must hash objective text with canonical UTF-8 SHA-256, issue its own UUID binding ID, require both native host IDs, set host fields to `None` for managed bindings, and never accept a host mutation callback. `observe_message` returns a decision object; only `progress`/`steer` can increment revisions. `status` returns `execution_kind="control-query"`; `side-question` returns a read-only detached workflow; `unrelated` returns a new detached workflow. `validate_graph` uses Kahn topological sorting, rejects missing dependencies and cycles, and reports overlapping `write_resources` for concurrently ready items so the scheduler remains sequential until a resource lock exists.

Reconciliation must preserve completed items unchanged, pause active items, replace only pending/ready items, create correction items for invalidated completed evidence, increment both Goal and plan revisions, and emit `GOAL_REVISION_RECONCILED` rather than mutating the old event。Every Work Item persists semantic scope、`skill_policy_ref` and Phase IDs；replan/replay resolves the same Explicit Skill Lock by scope anchor, so managed-goal decomposition cannot drop `required_all`/`allowed_set`/`preferred_primary` coverage。

- [ ] **Step 5: Run Goal tests**

Run: `py -3.11 -m unittest packages/router-core/tests/goals/test_goal_orchestrator.py -v`

Expected: all tests PASS; status keeps semantic revision, native binding cannot exist without host identity, and cycle/resource conflict is detected.

- [ ] **Step 6: Commit the Goal graph slice**

```powershell
git add packages/router-core/src/workflow_skill_router/goals packages/router-core/tests/goals/test_goal_orchestrator.py
git commit -m "feat(core): add host-safe goal work graph"
```

### Task 5: 產生 evidence-bound completion 與三-turn blocked candidates

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/goals/candidates.py`
- Test: `packages/router-core/tests/goals/test_candidates.py`

**Interfaces:**
- Consumes: `GoalBinding`, `AcceptanceCoverage`, `WorkGraph` from Task 4; explicit coverage digest and activation evidence produced by routing plan 02.
- Produces: frozen `AcceptanceCompletionRecord`、`ExplicitCoverageCompletionRecord`、`SideEffectCompletionRecord`、`PendingApprovalRecord`、`CompletionEvidenceSnapshot`、`CandidateRequest`；`CompletionEvidenceRepository.load(request) -> CompletionEvidenceSnapshot`；`WorkflowCompletionCandidate`; `GoalStatusCandidate`; `CandidateFactory.workflow_complete(request)`; `goal_complete(...)`; `BlockedAudit.observe(...)`; `blocked_candidate(...)`.

- [ ] **Step 1: Write hard candidate tests**

```python
# packages/router-core/tests/goals/test_candidates.py
import unittest

from workflow_skill_router.goals.candidates import Blocker, BlockedAudit, CandidateFactory, CandidateRequest
from workflow_skill_router.routing.models import RoutingEnvelope


class CandidateTests(unittest.TestCase):
    def test_complete_candidate_requires_evidence_and_explicit_coverage(self) -> None:
        request = CandidateRequest(
            workflow_run_id="wf-1", objective_digest="sha256:o", envelope=RoutingEnvelope.PHASED,
            plan_revision=2, workflow_state_version=8, capability_snapshot_id="snap-2",
        )
        repository = StubCompletionEvidenceRepository(snapshot_without_acceptance_evidence(request))
        result = CandidateFactory(repository).workflow_complete(request)
        self.assertIsNone(result)

    def test_status_and_side_question_do_not_count_as_blocked_turns(self) -> None:
        blocker = Blocker("auth", "provider", "user-login", "sha256:d")
        audit = BlockedAudit()
        audit = audit.observe(blocker, "progress", True, False)
        audit = audit.observe(blocker, "status", True, False)
        audit = audit.observe(blocker, "side-question", True, False)
        self.assertEqual(1, audit.consecutive_goal_turns)

    def test_non_countable_message_with_new_blocker_does_not_rebind_old_turns(self) -> None:
        first = Blocker("auth", "provider-a", "user-login", "sha256:a")
        second = Blocker("network", "provider-b", "external-change", "sha256:b")
        audit = BlockedAudit().observe(first, "progress", True, False)
        audit = audit.observe(first, "progress", True, False)
        audit = audit.observe(second, "status", True, False)
        audit = audit.observe(second, "progress", True, False)
        self.assertEqual(second.identity, audit.blocker_identity)
        self.assertEqual(1, audit.consecutive_goal_turns)

    def test_blocked_requires_three_same_goal_turns_and_no_runnable_required_item(self) -> None:
        blocker = Blocker("auth", "provider", "user-login", "sha256:d")
        audit = BlockedAudit()
        for _ in range(3):
            audit = audit.observe(blocker, "progress", True, False)
        self.assertTrue(audit.eligible)
        self.assertFalse(audit.observe(blocker, "progress", True, True).eligible)
```

- [ ] **Step 2: Run test and confirm the candidate module is missing**

Run: `py -3.11 -m unittest packages/router-core/tests/goals/test_candidates.py -v`

Expected: FAIL with missing `goals.candidates`.

- [ ] **Step 3: Implement candidate digests and blocked identity**

```python
# packages/router-core/src/workflow_skill_router/goals/candidates.py
from __future__ import annotations

from dataclasses import dataclass, replace

from workflow_skill_router.routing.models import RoutingEnvelope


@dataclass(frozen=True, slots=True)
class CandidateRequest:
    workflow_run_id: str
    objective_digest: str
    envelope: RoutingEnvelope
    plan_revision: int
    workflow_state_version: int
    capability_snapshot_id: str


@dataclass(frozen=True, slots=True)
class AcceptanceCompletionRecord:
    gate_id: str; mandatory: bool; status: str; evidence_refs: tuple[str, ...]
    evidence_digest: str; plan_revision: int; workflow_state_version: int


@dataclass(frozen=True, slots=True)
class ExplicitCoverageCompletionRecord:
    capability_id: str; scope_anchor_id: str; required: bool; status: str
    disposition_refs: tuple[str, ...]; activation_evidence_refs: tuple[str, ...]
    coverage_digest: str; plan_revision: int; workflow_state_version: int


@dataclass(frozen=True, slots=True)
class SideEffectCompletionRecord:
    action_digest: str; status: str; outcome_receipt_ref: str | None
    outcome_digest: str; plan_revision: int; workflow_state_version: int


@dataclass(frozen=True, slots=True)
class PendingApprovalRecord:
    approval_id: str; capability_id: str; scope_anchor_id: str
    action_digest: str; status: str; request_digest: str


@dataclass(frozen=True, slots=True)
class CompletionEvidenceSnapshot:
    request: CandidateRequest
    acceptance_records: tuple[AcceptanceCompletionRecord, ...]
    explicit_coverage_records: tuple[ExplicitCoverageCompletionRecord, ...]
    side_effect_records: tuple[SideEffectCompletionRecord, ...]
    unresolved_blockers: tuple[Blocker, ...]
    pending_approvals: tuple[PendingApprovalRecord, ...]
    acceptance_coverage_digest: str | None
    explicit_skill_coverage_digest: str | None
    evidence_digest: str | None
    side_effect_outcome_digest: str | None


@dataclass(frozen=True, slots=True)
class WorkflowCompletionCandidate:
    candidate_id: str
    input: CompletionEvidenceSnapshot
    generated_at: str


@dataclass(frozen=True, slots=True)
class Blocker:
    category: str
    target: str
    required_authority: str
    dependency_digest: str

    @property
    def identity(self) -> tuple[str, str, str, str]:
        return (self.category, self.target, self.required_authority, self.dependency_digest)


@dataclass(frozen=True, slots=True)
class BlockedAudit:
    blocker_identity: tuple[str, str, str, str] | None = None
    consecutive_goal_turns: int = 0
    alternatives_exhausted: bool = False
    runnable_required_work: bool = False

    def observe(self, blocker: Blocker, relation: str, alternatives_exhausted: bool,
                runnable_required_work: bool) -> "BlockedAudit":
        countable = relation in {"progress", "steer"}
        if not countable:
            return self
        same = self.blocker_identity == blocker.identity
        turns = self.consecutive_goal_turns + 1 if same else 1
        return BlockedAudit(blocker.identity, turns, alternatives_exhausted, runnable_required_work)

    @property
    def eligible(self) -> bool:
        return self.consecutive_goal_turns >= 3 and self.alternatives_exhausted and not self.runnable_required_work


class CandidateFactory:
    def __init__(self, evidence_repository: CompletionEvidenceRepository) -> None:
        self._evidence = evidence_repository

    def workflow_complete(self, request: CandidateRequest) -> WorkflowCompletionCandidate | None:
        snapshot = self._evidence.load(request)
        if snapshot.request != request or not aggregate_digests_match_typed_records(snapshot):
            return None
        if snapshot.unresolved_blockers or snapshot.pending_approvals:
            return None
        if not all_acceptance_records_complete(snapshot.acceptance_records):
            return None
        if not all_explicit_coverage_records_complete(snapshot.explicit_coverage_records):
            return None
        if not all_side_effect_records_terminal_success(snapshot.side_effect_records):
            return None
        return build_content_addressed_candidate(snapshot)
```

`CandidateFactory` accepts only a trusted `CompletionEvidenceRepository` backed by current projections；public commands cannot supply records, counts, pass/fail flags or digests。`workflow_complete(request)` loads one `CompletionEvidenceSnapshot` at the exact workflow state/plan revision, recomputes the four aggregate digests from canonical typed records, and returns `None` unless stored and recomputed digests match and are non-empty。It then verifies every mandatory acceptance record is `passed` with evidence, every required explicit coverage record is `satisfied` or a verified `waived-by-user` with disposition/activation evidence, every record matches the requested plan/state, blockers/approvals are empty, and side-effect outcomes contain no `pending`/`unknown`/missing receipt。A count alone can never satisfy a gate。Generate `GoalStatusCandidate` only from current workflow candidates plus current binding/objective/host revision/snapshot/state/coverage digests。A digest or revision change invalidates the candidate by equality check；do not update it in place。

- [ ] **Step 4: Run candidate tests**

Run: `py -3.11 -m unittest packages/router-core/tests/goals/test_candidates.py -v`

Expected: all tests PASS; no evidence produces no complete candidate and only three qualifying Goal turns produce blocked eligibility.

- [ ] **Step 5: Commit the candidate slice**

```powershell
git add packages/router-core/src/workflow_skill_router/goals/candidates.py packages/router-core/tests/goals/test_candidates.py
git commit -m "feat(core): gate workflow and goal status candidates"
```

### Task 6: 組合 RouterService、resume refresh 與 state/Goal integration gates

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/ports.py`
- Create: `packages/router-core/src/workflow_skill_router/authorization.py`
- Create: `packages/router-core/src/workflow_skill_router/composition.py`
- Create: `packages/router-core/src/workflow_skill_router/service_models.py`
- Create: `packages/router-core/src/workflow_skill_router/service.py`
- Create: `packages/router-core/src/workflow_skill_router/workflow/activation.py`
- Create: `packages/router-core/tests/integration/support.py`
- Test: `packages/router-core/tests/integration/test_router_service.py`
- Test: `packages/router-core/tests/integration/test_service_authority.py`
- Test: `packages/router-core/tests/workflow/test_activation_content.py`

**Interfaces:**
- Consumes: `SyncRuntimeContextResult`／`RuntimeContextSyncRequest`／`CapabilitySnapshot` from Plan 01；`RouteValidator.validate(request, snapshot, policy, context) -> RouteValidationResult`; state/Goal/persistence components from Tasks 1–5；trusted runtime/host、installer content resolver and artifact protector adapters injected through explicit ports。
- Produces the seven control/routing methods: `RouterService.sync_runtime_context(command: SyncRuntimeContext) -> SyncRuntimeContextResult`; `plan_work(command: PlanWork) -> PlanWorkResult`; `get_next_work(query: NextWorkQuery) -> NextWorkResult`; `validate_route(command: ValidateRoute) -> RouteValidationResult`; `record_work_event(command: RecordWorkEvent) -> RecordWorkEventResult`; `evaluate_gate(command: EvaluateGate) -> GateEvaluationResult`; `get_router_status(query: RouterStatusQuery) -> RouterStatusView`；server-internal `ActivationPreflightPort.bind_single_use(...) -> BoundCapabilityHandle` and `verify_consumption_receipt(...)`。Plan 05 extends this same facade with the three evaluation/export methods, yielding the final ten-tool service surface。

- [ ] **Step 1: Write facade integration tests**

```python
# packages/router-core/tests/integration/test_router_service.py
import unittest

from workflow_skill_router.service_models import NextWorkQuery, RequestContext, RouterStatusQuery
from support import build_router_service, seed_complete_native_goal, seed_paused_workflow


CONTEXT = RequestContext("session-1", "agent", "runtime-policy-1")


class RouterServiceTests(unittest.TestCase):
    def test_status_is_read_only_and_does_not_create_work(self) -> None:
        service = build_router_service()
        before = service.diagnostics()
        view = service.get_router_status(RouterStatusQuery(context=CONTEXT, goal_binding_id="goal-1", workflow_run_id=None))
        after = service.diagnostics()
        self.assertEqual(before.semantic_event_count, after.semantic_event_count)
        self.assertEqual(0, view.created_work_items)

    def test_resume_requires_refresh_before_next_work(self) -> None:
        service = build_router_service()
        seed_paused_workflow(service, "wf-1", "snap-old")
        result = service.get_next_work(NextWorkQuery(context=CONTEXT, workflow_run_id="wf-1"))
        self.assertEqual("refresh-required", result.status)
        self.assertEqual(("goal", "workspace", "capabilities", "evidence"), result.refresh_requirements)

    def test_native_goal_candidate_is_returned_but_not_applied_to_host(self) -> None:
        service = build_router_service()
        seed_complete_native_goal(service, "goal-1")
        view = service.get_router_status(RouterStatusQuery(context=CONTEXT, goal_binding_id="goal-1", workflow_run_id=None))
        self.assertEqual("complete", view.goal_status_candidate.candidate_type)
        self.assertFalse(view.host_goal_mutated)
```

- [ ] **Step 2: Run integration tests and confirm the service surface is absent**

Run: `py -3.11 -m unittest packages/router-core/tests/integration/test_router_service.py -v`

Expected: FAIL because `workflow_skill_router.service` and `service_models` do not exist.

- [ ] **Step 3: Define typed service commands and results**

`service_models.py` must use frozen dataclasses。Every request contains a `RequestContext(session_id, actor, runtime_policy_snapshot_id)`；every mutating command additionally contains `expected_state_version`, `idempotency_key`, `correlation_id`。`SyncRuntimeContext` wraps only a client-safe `RuntimeContextSyncIntent(host_snapshot_ref, plugin_handshake_ref, agent_runtime_snapshot)`；client cannot submit inner `session_id`、`runtime_fingerprint`、risk、ready-made snapshot、provider failure list or event type。Service loads the authenticated session fingerprint/risk from `RuntimeAuthorityContextRepository` and constructs plan 01 server-internal `RuntimeContextSyncRequest` itself。`EvaluateGate` contains only expected evidence/plan values and evidence refs；it cannot submit actual values/pass/fail/next state。`ValidateRoute` contains a model proposal plus immutable refs；it cannot submit trusted policy、allowed availability、runtime approval or server validation context。`RecordWorkEvent` wraps only the strict tagged observation union and immutable refs；its codec rejects client-supplied actor、status、event type、plan revision and arbitrary payload fields, while the server derives those authority-bearing values from current state and verified receipts。Results use explicit `to_dict()` codecs。

Use these exact class names:

```python
RequestContext, SyncRuntimeContext, PlanWork, PlanWorkResult, NextWorkQuery, NextWorkResult,
ValidateRoute, RecordWorkEvent, RecordWorkEventResult, EvaluateGate,
RouterStatusQuery, RouterStatusView, RouterDiagnostics
```

- [ ] **Step 4: Implement the application facade without duplicating domain policy**

```python
# packages/router-core/src/workflow_skill_router/service.py
from __future__ import annotations

from dataclasses import dataclass

from workflow_skill_router.capabilities.runtime_context import SyncRuntimeContextResult
from workflow_skill_router.service_models import (
    EvaluateGate, NextWorkQuery, NextWorkResult, PlanWork, PlanWorkResult,
    RecordWorkEvent, RecordWorkEventResult, RouterStatusQuery, RouterStatusView,
    SyncRuntimeContext, ValidateRoute,
)


class RouterService:
    def sync_runtime_context(self, command: SyncRuntimeContext) -> SyncRuntimeContextResult:
        self._authorizer.authorize_mutation(command.context, command.expected_state_version)
        authority = self._runtime_authority.require(command.context)
        request = RuntimeContextSyncRequest(
            authority=authority,
            host_snapshot_ref=command.intent.host_snapshot_ref,
            plugin_handshake_ref=command.intent.plugin_handshake_ref,
            agent_runtime_snapshot=command.intent.agent_runtime_snapshot,
        )
        result = self._runtime_context.sync_verified(request)
        snapshot_ref = self._artifacts.put_bytes(
            self._snapshot_codec.encode(result.snapshot), "application/json", "internal", "runtime-context"
        )
        self._runtime_sync.persist(command, result, snapshot_ref)
        self._projections.catch_up()
        return result

    def plan_work(self, command: PlanWork) -> PlanWorkResult:
        self._authorizer.authorize_mutation(command.context, command.expected_state_version)
        return self._planner.validate_and_persist(command)

    def get_next_work(self, query: NextWorkQuery) -> NextWorkResult:
        self._authorizer.authorize_read(query.context)
        return self._scheduler.next(query, require_resume_refresh=True)

    def validate_route(self, command: ValidateRoute):
        self._authorizer.authorize_mutation(command.context, command.expected_state_version)
        snapshot = self._snapshots.require(command.capability_snapshot_id)
        policy = self._policies.require(command.policy_revision, command.context.runtime_policy_snapshot_id)
        validation = self._validation_context.current_for(command, snapshot, policy)
        result = self._route_validator.validate(command.route_proposal, snapshot, policy, validation)
        return self._activation_preflight.bind_single_use_after_validation(command, result, snapshot)

    def record_work_event(self, command: RecordWorkEvent) -> RecordWorkEventResult:
        self._authorizer.authorize_reporting(command.context, command.observation)
        self._activation_preflight.verify_consumption_receipt(command.observation)
        append = self._coordinator.record(command.observation)
        self._projections.catch_up()
        return RecordWorkEventResult.from_append(append)

    def evaluate_gate(self, command: EvaluateGate):
        self._authorizer.authorize_mutation(command.context, command.expected_state_version)
        request = self._gate_context.build_from_current_projection(command)
        result = self._gate_evaluator.evaluate(request)
        return self._gate_coordinator.persist_result(command, result)

    def get_router_status(self, query: RouterStatusQuery) -> RouterStatusView:
        self._authorizer.authorize_read(query.context)
        return self._status_reader.read(query)
```

Define all underscored dependencies as explicit `Protocol` ports in `ports.py`；there must be no dynamic placeholder object。`RuntimeAuthorityContextRepository.require()` verifies outer session/actor/policy binding and returns the server-observed runtime fingerprint/risk；a mismatch between host/handshake receipt session and outer context fails before discovery。`SnapshotReader` opens snapshot artifacts through the shared store and strict Plan 01 registry；cache rows cannot bypass envelope or nested-field validation。`RuntimeContextSyncCoordinator.persist()` first writes canonical snapshot and drift artifacts, then writes `CAPABILITY_SNAPSHOT_CREATED` plus stable-sorted exact `CAPABILITY_DRIFT_DETECTED` identity/ref drafts in one optimistic-CAS append batch (`aggregate_type="runtime-context"`, aggregate ID = authenticated outer session ID, `workflow_run_id=None`)；event identity、provider failure summary and artifact refs are server-owned。Artifact write failure means no event；event append failure leaves an unreferenced deduplicated object eligible for later single-object GC, never a projected snapshot。

`ActivationPreflightPort` receives injected trusted `InstructionContentResolver`、runtime-contract resolver、a SQLite `LeaseActivationRepository` implementing Plan 02 `LeaseConsumptionPort`, trusted runtime-approval verifier and an optional host `BoundCapabilityConsumer`。It may resolve an activation binding only after route validation accepts every capability, including explicit lock、consent and manifest trust；it never opens rejected/unapproved support。For SKILL it opens one stable instruction handle and hashes those exact bytes；for MCP/plugin/app/host capabilities it resolves only the verified tool-schema/runtime-contract receipt and never opens a SKILL body。It reconstructs the authenticated invocation context, compares scope/purpose/context digest and the tagged observed binding with the lease, revalidates action digest and opaque runtime-approval scope, then calls one `BEGIN IMMEDIATE` transaction that inserts the tagged row in `lease_content_bindings` plus `lease_activation_consumptions(status='reserved', consumption_version=1, reservation_digest=...)`。The `lease_id` primary key is the cross-process CAS：concurrent/repeated activation loses with `lease-consumed` before capability input reaches the model。Only after commit does the port return an opaque `BoundCapabilityHandle` that the host consumes from the same verified handle/contract；the model/client never supplies a path or digest。

Reservation and activation receipt are intentionally two phases。The host signs a receipt bound to reservation digest、lease、capability、action and exact binding digest。A second atomic transaction verifies it, changes `activation_status` from `reserved` to `activated`, stores `activation_receipt_digest`/`activated_at`, and appends `CAPABILITY_ACTIVATION_OBSERVED`；there is no placeholder receipt。If host consumption fails or the process crashes after reservation, the lease remains spent。Startup `ActivationReceiptReconciler` asks the trusted host by reservation digest；a verified receipt completes the transition, a verified non-execution marks a terminal failed observation, and unavailable/ambiguous outcome becomes `unknown` without retry。Handle expiry、reuse、body/file-identity change、installer/schema mismatch、action/approval binding mismatch or missing kind-specific host support rejects activation。`record_work_event` only verifies the already-issued receipt for audit—it is not the preflight boundary。

The public `validate_route` execution path is therefore just-in-time and non-cacheable：it validates the route、creates one lease and binds one handle for the immediately following host activation。Planning/preview calls use the pure `RouteValidator` internally and do not issue an execution lease or open content。A client cannot request a reusable lease or detach the handle from its verified host consumer。

If the runtime lacks the relevant `BoundCapabilityConsumer` operation, the router must report `content-preflight-unavailable` for SKILL or `runtime-contract-preflight-unavailable` for MCP/plugin/app/host capabilities and cannot claim `hybrid-full` or issue an activation-ready lease。R2/R3 fail closed；R0/R1 may continue only through explicitly disclosed `skill-only-fallback`, whose evidence marks content enforcement unobservable and requires a new route validation for each activation。This limitation is documented in Plan 04 fallback and real-model scoring。

`composition.py` owns the only production factory。Its final signature after Plan 05 is `open(database: Path, artifact_root: Path, runtime_adapter, request_authorizer, instruction_content_resolver, artifact_protector, activation_preflight, evaluation_ports: EvaluationCompositionPorts, clock=SystemClock(), id_factory=UuidFactory())`。This plan initially wires concrete repositories、DiscoveryService、RouteValidator、GoalOrchestrator、GateEvaluator、projection runner and content-addressed store；Plan 05 adds the exact required evaluation aggregate and updates every call site before Plugin/Demo work starts。There is no separate attestation parameter: the trusted review verifier lives inside the server-owned evaluation aggregate。Clock/id factory injection exists for deterministic tests/demo but production defaults remain explicit。`authorization.py` validates session/actor/runtime-policy provenance and never accepts a client-supplied trusted flag。Put test seed helpers only in tests。On every start/query, projection catch-up repairs crashes；resume refreshes Goal/workspace/capabilities/evidence。Router never receives a host Goal mutation callback。

`test_service_authority.py` must prove a client cannot widen availability、forge required origin、replay a directive for another capability/purpose/scope、supply actual gates、reuse a session/actor、select verifier、submit runtime fingerprint/risk/inner session、submit capability events or replace server snapshot；all authority is server-owned。`test_activation_content.py` must prove body change before preflight fails、installer/schema mismatch fails、non-SKILL activation never opens a SKILL body、action/approval binding mismatch fails、unapproved support is never opened、same bound bytes reach host、receipt is required、two concurrent consumers yield exactly one reservation、handle/lease reuse fails、and missing kind-specific host support prevents `hybrid-full` before activation。It also injects crashes before host call、after host success and before receipt persistence；recovery never reactivates a spent lease and reconciles only a host-verifiable reservation receipt。

- [ ] **Step 5: Add scale, concurrency and UTF-8 assertions to the integration suite**

Add tests that append/replay 10,000 events, build a 500-item acyclic Work Graph, race two writers at the same state version (exactly one succeeds), and round-trip `"階段驗證：不得出現亂碼"`. Assert warm status and gate median remain below 200 ms locally; report timing rather than making a flaky single-sample assertion.

- [ ] **Step 6: Run the state/Goal suite and legacy suite**

Run:

```powershell
$env:PYTHONPATH = "packages/router-core/src"
py -3.11 -m unittest discover -s packages/router-core/tests -p "test_*.py" -v
py -3.11 -m unittest discover -s tests -p "test_*.py" -v
```

Expected: all V2 tests PASS and all existing V1 tests remain PASS.

- [ ] **Step 7: Commit the integrated state/Goal facade**

```powershell
git add packages/router-core/src/workflow_skill_router/ports.py packages/router-core/src/workflow_skill_router/authorization.py packages/router-core/src/workflow_skill_router/composition.py packages/router-core/src/workflow_skill_router/service.py packages/router-core/src/workflow_skill_router/service_models.py packages/router-core/tests/integration/support.py packages/router-core/tests/integration/test_router_service.py packages/router-core/tests/integration/test_service_authority.py
git commit -m "feat(core): expose goal-aware router service"
```

## Final Verification

- [ ] Run `py -3.11 -m unittest discover -s packages/router-core/tests -p "test_*.py" -v` and confirm zero failures.
- [ ] Run the existing `tests/` suite and confirm V1 remains green.
- [ ] Rebuild every projection from an event-only database and compare canonical read models.
- [ ] Inspect the schema with `PRAGMA table_info` and confirm secrets/user prompt bodies have no storage column.
- [ ] Confirm all native Goal paths end in a `GoalStatusCandidate`; search production code for host Goal mutation calls and expect zero results.
- [ ] Confirm every state mutation passes through `SQLiteEventStore.append` and every repeated idempotency key returns the original receipt.
- [ ] Confirm completed Phase tests only create correction/revalidation children and never mutate completed rows.
- [ ] Confirm candidate invalidation covers binding、objective、host revision、plan、state、snapshot、coverage and evidence digests.

## Self-Review Result

- Spec coverage: Phase/Workflow transition、gate CAS、resume、immutable completion、side-effect intent/outcome、Goal Binding/Work Graph/reconciliation、status short-circuit、completion/blocked candidate、SQLite migration/rebuild/idempotency and host authority are each mapped to a focused task.
- Interface consistency: `RouterService` method names and upstream `CapabilitySnapshot`／`RouteValidator` types match plans 01/02; plan 04 can consume the seven typed methods without reimplementing policy.
- Execution clarity: every task contains exact paths、red/green commands、failure expectation、public signatures and a narrow commit boundary.
