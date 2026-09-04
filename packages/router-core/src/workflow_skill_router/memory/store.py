from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from typing import Any

from workflow_skill_router.schemas.artifacts import canonical_json

from .migrator import MemoryMigrationError, migrate_memory_store
from .models import MemoryFeatures, MemoryMode, MemoryPolicyError
from .policy import decode_memory_policy
from .policy_resolver import EffectiveMemoryPolicy


SNAPSHOT_SCHEMA_ID = "workflow-skill-router/memory-policy-snapshot"
SNAPSHOT_SCHEMA_VERSION = "1.0.0"
SNAPSHOT_ARTIFACT_KIND = "memory-policy-snapshot"
MEMORY_DATABASE_NAME = "workflow-memory.sqlite3"

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SAFE_CODE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_MODES = ("disabled", "observe", "reviewed", "automatic")
_MODE_RANK = {name: index for index, name in enumerate(_MODES)}
_TARGETS = (
    "managed-personal",
    "managed-workspace-local",
    "user-personal",
    "workspace-file",
)
_PROMOTION_MODES = ("disabled", "review-required", "automatic-managed")
_TOP_LEVEL_FIELDS = frozenset({
    "schema_id",
    "schema_version",
    "artifact_kind",
    "snapshot_id",
    "policy_digest",
    "mode",
    "personal_mode",
    "workspace_requested_mode",
    "policy_source",
    "capture_enabled",
    "candidate_generation_enabled",
    "profile_promotion",
    "allowed_targets",
    "features",
    "reason_codes",
})
_FEATURE_FIELDS = {
    "remember_this_workflow": frozenset(
        {"mode", "eligible_event", "default_target"}
    ),
    "route_feedback": frozenset(
        {"mode", "allow_standard_reason_codes", "allow_free_text"}
    ),
    "history_analytics": frozenset({"mode", "run"}),
    "candidate_generation": frozenset(
        {"mode", "confidence_required", "backtest_required"}
    ),
    "profile_promotion": frozenset({
        "mode",
        "target",
        "conflict_policy",
        "require_profile_lint",
        "require_backtest",
    }),
    "profile_versioning": frozenset(
        {"mode", "diff", "rollback", "write_strategy"}
    ),
}


class MemoryPolicySnapshotError(ValueError):
    """Raised when a sanitized effective-policy snapshot is invalid."""


class MemoryStoreError(RuntimeError):
    """Raised when the optional Memory Store cannot be opened safely."""


class MemoryCommandConflict(MemoryStoreError):
    """Raised when an idempotency key is reused for a different command."""


def _snapshot_error(
    code: str,
    field: str | None = None,
) -> MemoryPolicySnapshotError:
    return MemoryPolicySnapshotError(code if field is None else f"{code}:{field}")


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _snapshot_error("invalid-object", field)
    if any(not isinstance(key, str) for key in value):
        raise _snapshot_error("invalid-object-key", field)
    return value


def _exact_fields(
    document: Mapping[str, object],
    expected: frozenset[str],
    field: str = "",
) -> None:
    unknown = sorted(set(document) - expected)
    if unknown:
        name = unknown[0] if not field else f"{field}.{unknown[0]}"
        raise _snapshot_error("unknown-field", name)
    missing = sorted(expected - set(document))
    if missing:
        name = missing[0] if not field else f"{field}.{missing[0]}"
        raise _snapshot_error("missing-field", name)


def _enum(value: object, allowed: tuple[str, ...], field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise _snapshot_error("invalid-enum", field)
    return value


def _boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise _snapshot_error("invalid-boolean", field)
    return value


def _feature_document(value: object) -> dict[str, dict[str, object]]:
    try:
        document = _mapping(value, "features")
        _exact_fields(document, frozenset(_FEATURE_FIELDS), "features")
        result: dict[str, dict[str, object]] = {}
        for name, fields in _FEATURE_FIELDS.items():
            nested = _mapping(document[name], f"features.{name}")
            _exact_fields(nested, fields, f"features.{name}")
            result[name] = dict(nested)
        return result
    except MemoryPolicySnapshotError as error:
        raise MemoryPolicySnapshotError("invalid-features") from error


def _decode_features(
    document: Mapping[str, Mapping[str, object]],
    mode: str,
) -> MemoryFeatures:
    try:
        policy = decode_memory_policy({
            "schema_id": "workflow-skill-router/memory-policy",
            "schema_version": "1.0.0",
            "artifact_kind": "memory-policy",
            "policy_id": "personal:snapshot-validation",
            "scope": "personal",
            "mode": mode,
            "privacy": {
                "free_text_feedback": (
                    "explicit-opt-in"
                    if bool(document["route_feedback"]["allow_free_text"])
                    else "never"
                )
            },
            "features": {
                name: dict(value)
                for name, value in document.items()
            },
        })
    except MemoryPolicyError as error:
        raise MemoryPolicySnapshotError("invalid-features") from error
    actual = policy.features.to_dict()
    expected = {name: dict(value) for name, value in document.items()}
    if actual != expected:
        raise MemoryPolicySnapshotError("invalid-features")
    return policy.features


def _snapshot_identity(document: Mapping[str, object]) -> str:
    payload = {key: value for key, value in document.items() if key != "snapshot_id"}
    try:
        encoded = canonical_json(payload).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise MemoryPolicySnapshotError(
            "invalid-memory-policy-snapshot-document"
        ) from error
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _canonical_value(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


@dataclass(frozen=True, slots=True)
class MemoryPolicySnapshot:
    snapshot_id: str
    policy_digest: str
    mode: MemoryMode
    personal_mode: MemoryMode
    workspace_requested_mode: MemoryMode | None
    policy_source: str
    capture_enabled: bool
    candidate_generation_enabled: bool
    profile_promotion: str
    allowed_targets: tuple[str, ...]
    features: MemoryFeatures
    reason_codes: tuple[str, ...]

    @classmethod
    def from_effective_policy(
        cls,
        policy: EffectiveMemoryPolicy,
    ) -> "MemoryPolicySnapshot":
        document: dict[str, object] = {
            "schema_id": SNAPSHOT_SCHEMA_ID,
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "artifact_kind": SNAPSHOT_ARTIFACT_KIND,
            "snapshot_id": "",
            "policy_digest": policy.policy_digest,
            "mode": policy.mode.value,
            "personal_mode": policy.personal_mode.value,
            "workspace_requested_mode": (
                None
                if policy.workspace_requested_mode is None
                else policy.workspace_requested_mode.value
            ),
            "policy_source": policy.policy_source,
            "capture_enabled": policy.capture_enabled,
            "candidate_generation_enabled": policy.candidate_generation_enabled,
            "profile_promotion": policy.profile_promotion,
            "allowed_targets": list(policy.allowed_targets),
            "features": policy.policy.features.to_dict(),
            "reason_codes": list(policy.reason_codes),
        }
        document["snapshot_id"] = _snapshot_identity(document)
        return decode_memory_policy_snapshot(document)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": SNAPSHOT_SCHEMA_ID,
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "artifact_kind": SNAPSHOT_ARTIFACT_KIND,
            "snapshot_id": self.snapshot_id,
            "policy_digest": self.policy_digest,
            "mode": self.mode.value,
            "personal_mode": self.personal_mode.value,
            "workspace_requested_mode": (
                None
                if self.workspace_requested_mode is None
                else self.workspace_requested_mode.value
            ),
            "policy_source": self.policy_source,
            "capture_enabled": self.capture_enabled,
            "candidate_generation_enabled": self.candidate_generation_enabled,
            "profile_promotion": self.profile_promotion,
            "allowed_targets": list(self.allowed_targets),
            "features": self.features.to_dict(),
            "reason_codes": list(self.reason_codes),
        }

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())


def decode_memory_policy_snapshot(
    value: Mapping[str, object],
) -> MemoryPolicySnapshot:
    document = _mapping(value, "snapshot")
    _exact_fields(document, _TOP_LEVEL_FIELDS)

    if document["schema_id"] != SNAPSHOT_SCHEMA_ID:
        raise _snapshot_error("invalid-schema-id")
    if document["schema_version"] != SNAPSHOT_SCHEMA_VERSION:
        raise _snapshot_error("unsupported-schema-version")
    if document["artifact_kind"] != SNAPSHOT_ARTIFACT_KIND:
        raise _snapshot_error("invalid-artifact-kind")

    snapshot_id = document["snapshot_id"]
    policy_digest = document["policy_digest"]
    if not isinstance(snapshot_id, str) or not _DIGEST.fullmatch(snapshot_id):
        raise _snapshot_error("invalid-snapshot-id")
    if not isinstance(policy_digest, str) or not _DIGEST.fullmatch(policy_digest):
        raise _snapshot_error("invalid-policy-digest")

    mode = _enum(document["mode"], _MODES, "mode")
    personal_mode = _enum(document["personal_mode"], _MODES, "personal_mode")
    workspace_mode = document["workspace_requested_mode"]
    if workspace_mode is not None:
        workspace_mode = _enum(
            workspace_mode,
            _MODES,
            "workspace_requested_mode",
        )

    policy_source = document["policy_source"]
    if not isinstance(policy_source, str) or not _SAFE_CODE.fullmatch(policy_source):
        raise _snapshot_error("invalid-policy-source")

    capture_enabled = _boolean(document["capture_enabled"], "capture_enabled")
    candidate_enabled = _boolean(
        document["candidate_generation_enabled"],
        "candidate_generation_enabled",
    )
    promotion = _enum(
        document["profile_promotion"],
        _PROMOTION_MODES,
        "profile_promotion",
    )

    raw_targets = document["allowed_targets"]
    if not isinstance(raw_targets, list) or len(raw_targets) > len(_TARGETS):
        raise _snapshot_error("invalid-allowed-targets")
    targets = tuple(_enum(item, _TARGETS, "allowed_targets") for item in raw_targets)
    if len(set(targets)) != len(targets):
        raise _snapshot_error("duplicate-allowed-target")
    canonical_targets = tuple(item for item in _TARGETS if item in set(targets))
    if targets != canonical_targets:
        raise _snapshot_error("noncanonical-allowed-targets")

    raw_reasons = document["reason_codes"]
    if not isinstance(raw_reasons, list) or len(raw_reasons) > 32:
        raise _snapshot_error("invalid-reason-codes")
    reasons: list[str] = []
    for item in raw_reasons:
        if not isinstance(item, str) or not _SAFE_CODE.fullmatch(item):
            raise _snapshot_error("invalid-reason-code")
        if item in reasons:
            raise _snapshot_error("duplicate-reason-code")
        reasons.append(item)

    feature_values = _feature_document(document["features"])

    # Identity is checked before semantic mode/feature compatibility so any
    # post-creation mutation is reported as tampering, not reinterpreted.
    if snapshot_id != _snapshot_identity(document):
        raise _snapshot_error("memory-policy-snapshot-id-mismatch")

    features = _decode_features(feature_values, mode)
    if _MODE_RANK[mode] > _MODE_RANK[personal_mode]:
        raise _snapshot_error("effective-mode-exceeds-personal-mode")
    if capture_enabled != (mode != "disabled"):
        raise _snapshot_error("capture-decision-mismatch")
    if candidate_enabled != (
        features.candidate_generation.mode != "disabled"
    ):
        raise _snapshot_error("candidate-decision-mismatch")
    if promotion != features.profile_promotion.mode:
        raise _snapshot_error("promotion-decision-mismatch")

    expected_targets: set[str] = set()
    if features.remember_this_workflow.mode != "disabled":
        expected_targets.add(features.remember_this_workflow.default_target)
    if features.profile_promotion.mode != "disabled":
        expected_targets.add(features.profile_promotion.target)
    if targets != tuple(item for item in _TARGETS if item in expected_targets):
        raise _snapshot_error("target-decision-mismatch")

    return MemoryPolicySnapshot(
        snapshot_id=snapshot_id,
        policy_digest=policy_digest,
        mode=MemoryMode(mode),
        personal_mode=MemoryMode(personal_mode),
        workspace_requested_mode=(
            None if workspace_mode is None else MemoryMode(workspace_mode)
        ),
        policy_source=policy_source,
        capture_enabled=capture_enabled,
        candidate_generation_enabled=candidate_enabled,
        profile_promotion=promotion,
        allowed_targets=targets,
        features=features,
        reason_codes=tuple(reasons),
    )


def _is_link_or_reparse(metadata: os.stat_result) -> bool:
    if stat.S_ISLNK(metadata.st_mode):
        return True
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return bool(attributes & flag)


def _directory_metadata(
    path: Path,
    *,
    link_code: str,
    type_code: str,
) -> os.stat_result | None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise MemoryStoreError("memory-store-path-unavailable") from error
    if _is_link_or_reparse(metadata):
        raise MemoryStoreError(link_code)
    if not stat.S_ISDIR(metadata.st_mode):
        raise MemoryStoreError(type_code)
    return metadata


def _ensure_directory(
    path: Path,
    *,
    link_code: str,
    type_code: str,
) -> None:
    if _directory_metadata(
        path,
        link_code=link_code,
        type_code=type_code,
    ) is None:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise MemoryStoreError("memory-store-directory-create-failed") from error
    if _directory_metadata(
        path,
        link_code=link_code,
        type_code=type_code,
    ) is None:
        raise MemoryStoreError("memory-store-directory-create-failed")


def _validate_database_file(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    except OSError as error:
        raise MemoryStoreError("memory-store-file-unavailable") from error
    if _is_link_or_reparse(metadata):
        raise MemoryStoreError("memory-store-file-link-forbidden")
    if not stat.S_ISREG(metadata.st_mode):
        raise MemoryStoreError("memory-store-file-not-regular")


def _digest_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


class MemoryStore:
    """Bounded repository for the optional, local Memory History Store."""

    def __init__(
        self,
        database_path: Path,
        connection: sqlite3.Connection,
        current_policy_snapshot: MemoryPolicySnapshot,
    ) -> None:
        self._database_path = database_path
        self._connection = connection
        self._current_policy_snapshot = current_policy_snapshot
        self._closed = False

    @classmethod
    def open_if_enabled(
        cls,
        data_dir: Path,
        policy: EffectiveMemoryPolicy,
    ) -> "MemoryStore | None":
        if policy.mode is MemoryMode.DISABLED:
            return None

        data_root = Path(data_dir).expanduser()
        if not data_root.is_absolute():
            data_root = Path.cwd() / data_root
        data_root = data_root.absolute()
        _ensure_directory(
            data_root,
            link_code="memory-data-root-link-forbidden",
            type_code="memory-data-root-not-directory",
        )
        memory_dir = data_root / "memory"
        _ensure_directory(
            memory_dir,
            link_code="memory-store-parent-link-forbidden",
            type_code="memory-store-parent-not-directory",
        )
        database_path = memory_dir / MEMORY_DATABASE_NAME
        _validate_database_file(database_path)

        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(
                database_path,
                isolation_level=None,
                timeout=5.0,
            )
            _validate_database_file(database_path)
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA busy_timeout = 5000")
            migrate_memory_store(connection)
            snapshot = MemoryPolicySnapshot.from_effective_policy(policy)
            store = cls(database_path, connection, snapshot)
            store._record_policy_snapshot(snapshot)
            return store
        except MemoryStoreError:
            if connection is not None:
                connection.close()
            raise
        except MemoryPolicySnapshotError as error:
            if connection is not None:
                connection.close()
            raise MemoryStoreError("memory-policy-snapshot-invalid") from error
        except MemoryMigrationError as error:
            if connection is not None:
                connection.close()
            raise MemoryStoreError("memory-store-migration-failed") from error
        except (OSError, sqlite3.Error) as error:
            if connection is not None:
                connection.close()
            raise MemoryStoreError("memory-store-open-failed") from error

    @classmethod
    def open_existing(cls, data_dir: Path) -> "MemoryStore | None":
        """Open an existing Memory Store without creating any path or snapshot.

        This boundary exists for explicit privacy operations, such as purge,
        after the effective Memory Policy has been disabled.
        """

        data_root = Path(data_dir).expanduser()
        if not data_root.is_absolute():
            data_root = Path.cwd() / data_root
        data_root = data_root.absolute()
        if _directory_metadata(
            data_root,
            link_code="memory-data-root-link-forbidden",
            type_code="memory-data-root-not-directory",
        ) is None:
            return None
        memory_dir = data_root / "memory"
        if _directory_metadata(
            memory_dir,
            link_code="memory-store-parent-link-forbidden",
            type_code="memory-store-parent-not-directory",
        ) is None:
            return None
        database_path = memory_dir / MEMORY_DATABASE_NAME
        try:
            database_metadata = database_path.lstat()
        except FileNotFoundError:
            return None
        except OSError as error:
            raise MemoryStoreError("memory-store-file-unavailable") from error
        if _is_link_or_reparse(database_metadata):
            raise MemoryStoreError("memory-store-file-link-forbidden")
        if not stat.S_ISREG(database_metadata.st_mode):
            raise MemoryStoreError("memory-store-file-not-regular")

        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(
                database_path.as_uri() + "?mode=rw",
                uri=True,
                isolation_level=None,
                timeout=5.0,
            )
            _validate_database_file(database_path)
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA busy_timeout = 5000")
            migrate_memory_store(connection)
            row = connection.execute(
                "SELECT snapshot_id FROM memory_policy_snapshots "
                "ORDER BY recorded_at DESC, snapshot_id DESC LIMIT 1"
            ).fetchone()
            if row is None:
                raise MemoryStoreError("memory-policy-snapshot-missing")
            # Construct a temporary bounded store only to reuse the strict
            # snapshot decoder; no new snapshot is recorded here.
            placeholder = object.__new__(cls)
            placeholder._database_path = database_path
            placeholder._connection = connection
            placeholder._closed = False
            placeholder._current_policy_snapshot = None
            snapshot = placeholder.load_policy_snapshot(str(row[0]))
            if snapshot is None:
                raise MemoryStoreError("memory-policy-snapshot-missing")
            placeholder._current_policy_snapshot = snapshot
            return placeholder
        except (MemoryStoreError, MemoryCommandConflict):
            if connection is not None:
                connection.close()
            raise
        except MemoryMigrationError as error:
            if connection is not None:
                connection.close()
            raise MemoryStoreError("memory-store-migration-failed") from error
        except (OSError, sqlite3.Error) as error:
            if connection is not None:
                connection.close()
            raise MemoryStoreError("memory-store-open-failed") from error

    @property
    def database_path(self) -> Path:
        return self._database_path

    @property
    def current_policy_snapshot(self) -> MemoryPolicySnapshot:
        return self._current_policy_snapshot

    @property
    def closed(self) -> bool:
        return self._closed

    def _require_open(self) -> sqlite3.Connection:
        if self._closed:
            raise MemoryStoreError("memory-store-closed")
        return self._connection

    def _record_policy_snapshot(self, snapshot: MemoryPolicySnapshot) -> None:
        connection = self._require_open()
        document = snapshot.to_dict()
        expected = (
            snapshot.policy_digest,
            snapshot.mode.value,
            snapshot.personal_mode.value,
            (
                None
                if snapshot.workspace_requested_mode is None
                else snapshot.workspace_requested_mode.value
            ),
            snapshot.policy_source,
            int(snapshot.capture_enabled),
            int(snapshot.candidate_generation_enabled),
            snapshot.profile_promotion,
            _canonical_value(document["allowed_targets"]),
            _canonical_value(document["features"]),
            _canonical_value(document["reason_codes"]),
        )
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT OR IGNORE INTO memory_policy_snapshots(
                    snapshot_id,
                    policy_digest,
                    mode,
                    personal_mode,
                    workspace_requested_mode,
                    policy_source,
                    capture_enabled,
                    candidate_generation_enabled,
                    profile_promotion,
                    allowed_targets_json,
                    features_json,
                    reason_codes_json,
                    recorded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (snapshot.snapshot_id, *expected, _utc_now()),
            )
            actual = connection.execute(
                """
                SELECT
                    policy_digest,
                    mode,
                    personal_mode,
                    workspace_requested_mode,
                    policy_source,
                    capture_enabled,
                    candidate_generation_enabled,
                    profile_promotion,
                    allowed_targets_json,
                    features_json,
                    reason_codes_json
                FROM memory_policy_snapshots
                WHERE snapshot_id = ?
                """,
                (snapshot.snapshot_id,),
            ).fetchone()
            if actual is None or tuple(actual) != expected:
                raise MemoryStoreError("memory-policy-snapshot-conflict")
            connection.execute("COMMIT")
        except MemoryStoreError:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        except sqlite3.Error as error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise MemoryStoreError(
                "memory-policy-snapshot-write-failed"
            ) from error

    def load_policy_snapshot(
        self,
        snapshot_id: str,
    ) -> MemoryPolicySnapshot | None:
        if not isinstance(snapshot_id, str) or not _DIGEST.fullmatch(snapshot_id):
            raise MemoryStoreError("invalid-memory-policy-snapshot-id")
        connection = self._require_open()
        try:
            row = connection.execute(
                """
                SELECT
                    snapshot_id,
                    policy_digest,
                    mode,
                    personal_mode,
                    workspace_requested_mode,
                    policy_source,
                    capture_enabled,
                    candidate_generation_enabled,
                    profile_promotion,
                    allowed_targets_json,
                    features_json,
                    reason_codes_json
                FROM memory_policy_snapshots
                WHERE snapshot_id = ?
                """,
                (snapshot_id,),
            ).fetchone()
        except sqlite3.Error as error:
            raise MemoryStoreError("memory-policy-snapshot-read-failed") from error
        if row is None:
            return None
        try:
            return decode_memory_policy_snapshot({
                "schema_id": SNAPSHOT_SCHEMA_ID,
                "schema_version": SNAPSHOT_SCHEMA_VERSION,
                "artifact_kind": SNAPSHOT_ARTIFACT_KIND,
                "snapshot_id": str(row[0]),
                "policy_digest": str(row[1]),
                "mode": str(row[2]),
                "personal_mode": str(row[3]),
                "workspace_requested_mode": (
                    None if row[4] is None else str(row[4])
                ),
                "policy_source": str(row[5]),
                "capture_enabled": bool(row[6]),
                "candidate_generation_enabled": bool(row[7]),
                "profile_promotion": str(row[8]),
                "allowed_targets": json.loads(str(row[9])),
                "features": json.loads(str(row[10])),
                "reason_codes": json.loads(str(row[11])),
            })
        except (json.JSONDecodeError, MemoryPolicySnapshotError) as error:
            raise MemoryStoreError("memory-policy-snapshot-corrupt") from error

    def policy_snapshot_count(self) -> int:
        connection = self._require_open()
        try:
            row = connection.execute(
                "SELECT COUNT(*) FROM memory_policy_snapshots"
            ).fetchone()
        except sqlite3.Error as error:
            raise MemoryStoreError("memory-policy-snapshot-count-failed") from error
        return 0 if row is None else int(row[0])

    def applied_migration_versions(self) -> tuple[int, ...]:
        connection = self._require_open()
        try:
            rows = connection.execute(
                "SELECT version FROM memory_schema_migrations ORDER BY version"
            ).fetchall()
        except sqlite3.Error as error:
            raise MemoryStoreError("memory-migration-read-failed") from error
        return tuple(int(row[0]) for row in rows)

    def purge_history(self) -> dict[str, int]:
        connection = self._require_open()
        counts: dict[str, int] = {}
        try:
            connection.execute("BEGIN IMMEDIATE")
            # Delete explicit feedback before observations/snapshots so the
            # RESTRICT policy-snapshot relationship remains valid.
            for table in (
                "route_feedback_events",
                "route_feedback",
                "route_observation_documents",
                "route_observations",
                "memory_command_results",
                "memory_command_receipts",
                "memory_admin_commands",
                "memory_policy_snapshots",
            ):
                cursor = connection.execute(f"DELETE FROM {table}")
                counts[table] = max(0, int(cursor.rowcount))
            connection.execute("COMMIT")
        except sqlite3.Error as error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise MemoryStoreError("memory-history-purge-failed") from error
        return {
            "memory_command_receipts": counts["memory_command_receipts"],
            "route_feedback": (
                counts["route_feedback"] + counts["route_feedback_events"]
            ),
            "route_observations": counts["route_observations"],
            "memory_policy_snapshots": counts["memory_policy_snapshots"],
        }


    def record_route_observation(
        self,
        *,
        observation_document: Mapping[str, object],
        result_document: Mapping[str, object],
        idempotency_key: str,
        command_digest: str,
    ) -> tuple[dict[str, object], bool]:
        """Persist one sanitized Observation and an idempotent result receipt."""

        if (
            not isinstance(idempotency_key, str)
            or not idempotency_key
            or len(idempotency_key) > 160
        ):
            raise MemoryStoreError("invalid-memory-idempotency-key")
        if not isinstance(command_digest, str) or not _DIGEST.fullmatch(command_digest):
            raise MemoryStoreError("invalid-memory-command-digest")
        from .observations import decode_route_observation

        observation = decode_route_observation(observation_document)
        connection = self._require_open()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing_receipt = connection.execute(
                "SELECT command_digest,result_digest FROM memory_command_receipts "
                "WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if existing_receipt is not None:
                if str(existing_receipt[0]) != command_digest:
                    raise MemoryCommandConflict("memory-idempotency-conflict")
                result_row = connection.execute(
                    "SELECT result_json FROM memory_command_results WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
                if result_row is None:
                    raise MemoryStoreError("memory-command-result-corrupt")
                stored_json = str(result_row[0])
                if "sha256:" + hashlib.sha256(stored_json.encode("utf-8")).hexdigest() != str(existing_receipt[1]):
                    raise MemoryStoreError("memory-command-result-corrupt")
                stored = json.loads(stored_json)
                if not isinstance(stored, dict) or canonical_json(stored) != stored_json:
                    raise MemoryStoreError("memory-command-result-corrupt")
                connection.execute("COMMIT")
                return stored, True

            existing_observation = connection.execute(
                "SELECT observation_json FROM route_observation_documents "
                "WHERE workflow_run_digest=?",
                (observation.workflow_run_digest,),
            ).fetchone()
            replayed_workflow = existing_observation is not None
            if existing_observation is not None:
                stored_observation_json = str(existing_observation[0])
                stored_observation = decode_route_observation(json.loads(stored_observation_json))
                if canonical_json(stored_observation.to_dict()) != stored_observation_json:
                    raise MemoryStoreError("route-observation-corrupt")
                result = dict(result_document)
                result["observation_id"] = stored_observation.observation_id
                result["observation_digest"] = stored_observation.observation_digest
                result["route_signature_digest"] = stored_observation.route_signature_digest
            else:
                side_effect_status = (
                    "none"
                    if observation.side_effect_outcome == "none"
                    else "unknown"
                    if observation.side_effect_outcome == "unknown"
                    else "known"
                )
                connection.execute(
                    """
                    INSERT INTO route_observations(
                        observation_id,workflow_fingerprint,workspace_identity_digest,
                        work_mode,route_digest,terminal_status,required_gates_passed,
                        side_effect_status,risk_level,policy_snapshot_id,source_event_ref,observed_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        observation.observation_id,
                        observation.workflow_fingerprint,
                        observation.workspace_identity_digest,
                        observation.work_mode,
                        observation.route_signature_digest,
                        observation.terminal_status,
                        int(observation.required_gates_passed),
                        side_effect_status,
                        observation.risk_class,
                        observation.policy_snapshot_id,
                        observation.workflow_run_digest,
                        observation.observed_at,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO route_observation_documents(
                        observation_id,observation_digest,workflow_run_digest,
                        matcher_source,target_profile_class,automatic_promotion_eligible,
                        observation_json
                    ) VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        observation.observation_id,
                        observation.observation_digest,
                        observation.workflow_run_digest,
                        observation.matcher_seed.source,
                        observation.target_profile_class,
                        int(observation.automatic_promotion_eligible),
                        observation.canonical_json(),
                    ),
                )
                result = dict(result_document)

            result_json = canonical_json(result)
            result_digest = "sha256:" + hashlib.sha256(result_json.encode("utf-8")).hexdigest()
            connection.execute(
                """
                INSERT INTO memory_command_receipts(
                    idempotency_key,command_kind,command_digest,result_digest,created_at
                ) VALUES (?,?,?,?,?)
                """,
                (idempotency_key, "remember-workflow", command_digest, result_digest, _utc_now()),
            )
            connection.execute(
                "INSERT INTO memory_command_results(idempotency_key,result_json) VALUES (?,?)",
                (idempotency_key, result_json),
            )
            connection.execute("COMMIT")
            return result, replayed_workflow
        except MemoryCommandConflict:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        except MemoryStoreError:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        except (json.JSONDecodeError, sqlite3.Error, ValueError, TypeError) as error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise MemoryStoreError("route-observation-write-failed") from error

    def load_route_observation(self, observation_id: str):
        from .observations import decode_route_observation

        connection = self._require_open()
        try:
            row = connection.execute(
                "SELECT observation_json FROM route_observation_documents WHERE observation_id=?",
                (observation_id,),
            ).fetchone()
        except sqlite3.Error as error:
            raise MemoryStoreError("route-observation-read-failed") from error
        if row is None:
            return None
        try:
            document = json.loads(str(row[0]))
            observation = decode_route_observation(document)
            if observation.canonical_json() != str(row[0]):
                raise MemoryStoreError("route-observation-corrupt")
            return observation
        except (json.JSONDecodeError, ValueError, TypeError) as error:
            raise MemoryStoreError("route-observation-corrupt") from error

    def observation_count(self) -> int:
        connection = self._require_open()
        try:
            row = connection.execute("SELECT COUNT(*) FROM route_observations").fetchone()
        except sqlite3.Error as error:
            raise MemoryStoreError("route-observation-count-failed") from error
        return 0 if row is None else int(row[0])


    def record_route_feedback(
        self,
        *,
        feedback_document: Mapping[str, object],
        result_document: Mapping[str, object],
        idempotency_key: str,
        command_digest: str,
    ) -> tuple[dict[str, object], bool]:
        """Persist one strict feedback artifact and an idempotent result."""

        from .feedback import decode_route_feedback

        if not isinstance(idempotency_key, str) or not idempotency_key or len(idempotency_key) > 160:
            raise MemoryStoreError("invalid-memory-idempotency-key")
        if not isinstance(command_digest, str) or not _DIGEST.fullmatch(command_digest):
            raise MemoryStoreError("invalid-memory-command-digest")
        feedback = decode_route_feedback(feedback_document)
        connection = self._require_open()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT command_kind,command_digest,result_digest FROM memory_command_receipts "
                "WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                if str(existing[0]) != "record-route-feedback" or str(existing[1]) != command_digest:
                    raise MemoryCommandConflict("memory-idempotency-conflict")
                result_row = connection.execute(
                    "SELECT result_json FROM memory_command_results WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
                if result_row is None:
                    raise MemoryStoreError("memory-command-result-corrupt")
                result_json = str(result_row[0])
                if _digest_text(result_json) != str(existing[2]):
                    raise MemoryStoreError("memory-command-result-corrupt")
                result = json.loads(result_json)
                if not isinstance(result, dict) or canonical_json(result) != result_json:
                    raise MemoryStoreError("memory-command-result-corrupt")
                connection.execute("COMMIT")
                return result, True

            observation_row = connection.execute(
                "SELECT observation_json FROM route_observation_documents WHERE observation_id=?",
                (feedback.observation_id,),
            ).fetchone()
            if observation_row is None:
                raise MemoryStoreError("feedback-observation-not-found")
            from .observations import decode_route_observation
            observation = decode_route_observation(json.loads(str(observation_row[0])))
            if (
                observation.observation_digest != feedback.observation_digest
                or observation.workflow_run_digest != feedback.workflow_run_digest
            ):
                raise MemoryStoreError("feedback-observation-binding-mismatch")
            snapshot = self.load_policy_snapshot(feedback.policy_snapshot_id)
            if snapshot is None or snapshot.policy_digest != feedback.policy_digest:
                raise MemoryStoreError("feedback-policy-binding-mismatch")

            connection.execute(
                """
                INSERT INTO route_feedback_events(
                    feedback_id,feedback_digest,observation_id,observation_digest,
                    workflow_run_digest,policy_snapshot_id,policy_digest,feedback_type,
                    reason_code,recorded_at,feedback_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    feedback.feedback_id,
                    feedback.feedback_digest,
                    feedback.observation_id,
                    feedback.observation_digest,
                    feedback.workflow_run_digest,
                    feedback.policy_snapshot_id,
                    feedback.policy_digest,
                    feedback.feedback_type,
                    feedback.reason_code,
                    feedback.recorded_at,
                    feedback.canonical_json(),
                ),
            )
            result_json = canonical_json(dict(result_document))
            result_digest = _digest_text(result_json)
            connection.execute(
                "INSERT INTO memory_command_receipts("
                "idempotency_key,command_kind,command_digest,result_digest,created_at"
                ") VALUES (?,?,?,?,?)",
                (idempotency_key, "record-route-feedback", command_digest, result_digest, _utc_now()),
            )
            connection.execute(
                "INSERT INTO memory_command_results(idempotency_key,result_json) VALUES (?,?)",
                (idempotency_key, result_json),
            )
            connection.execute("COMMIT")
            return dict(result_document), False
        except (MemoryCommandConflict, MemoryStoreError):
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        except (json.JSONDecodeError, sqlite3.Error, TypeError, ValueError) as error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise MemoryStoreError("route-feedback-write-failed") from error

    def load_route_feedback(self, feedback_id: str):
        from .feedback import decode_route_feedback

        if not isinstance(feedback_id, str) or not feedback_id.startswith("feedback:"):
            raise MemoryStoreError("invalid-feedback-id")
        connection = self._require_open()
        try:
            row = connection.execute(
                "SELECT feedback_json FROM route_feedback_events WHERE feedback_id=?",
                (feedback_id,),
            ).fetchone()
        except sqlite3.Error as error:
            raise MemoryStoreError("route-feedback-read-failed") from error
        if row is None:
            return None
        try:
            feedback = decode_route_feedback(json.loads(str(row[0])))
            if feedback.canonical_json() != str(row[0]):
                raise MemoryStoreError("route-feedback-corrupt")
            return feedback
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise MemoryStoreError("route-feedback-corrupt") from error

    def list_route_observations(self):
        from .observations import decode_route_observation

        connection = self._require_open()
        try:
            rows = connection.execute(
                "SELECT observation_json FROM route_observation_documents "
                "ORDER BY json_extract(observation_json,'$.observed_at'), observation_id"
            ).fetchall()
        except sqlite3.Error as error:
            raise MemoryStoreError("route-observation-list-failed") from error
        observations = []
        for row in rows:
            try:
                value = str(row[0])
                observation = decode_route_observation(json.loads(value))
                if observation.canonical_json() != value:
                    raise MemoryStoreError("route-observation-corrupt")
                observations.append(observation)
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                raise MemoryStoreError("route-observation-corrupt") from error
        return tuple(observations)

    def list_route_feedback(self):
        from .feedback import decode_route_feedback

        connection = self._require_open()
        try:
            rows = connection.execute(
                "SELECT feedback_json FROM route_feedback_events ORDER BY recorded_at,feedback_id"
            ).fetchall()
        except sqlite3.Error as error:
            raise MemoryStoreError("route-feedback-list-failed") from error
        feedback = []
        for row in rows:
            try:
                value = str(row[0])
                item = decode_route_feedback(json.loads(value))
                if item.canonical_json() != value:
                    raise MemoryStoreError("route-feedback-corrupt")
                feedback.append(item)
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                raise MemoryStoreError("route-feedback-corrupt") from error
        return tuple(feedback)

    def enforce_retention(
        self,
        *,
        retention_days: int,
        max_observations: int,
        now: str,
    ) -> dict[str, int]:
        if isinstance(retention_days, bool) or not isinstance(retention_days, int) or retention_days < 1:
            raise MemoryStoreError("invalid-retention-days")
        if isinstance(max_observations, bool) or not isinstance(max_observations, int) or max_observations < 1:
            raise MemoryStoreError("invalid-max-observations")
        try:
            instant = datetime.fromisoformat(now.replace("Z", "+00:00"))
            if instant.tzinfo is None:
                raise ValueError
        except (TypeError, ValueError) as error:
            raise MemoryStoreError("invalid-retention-time") from error
        cutoff = (instant.astimezone(timezone.utc) - timedelta(days=retention_days)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        connection = self._require_open()
        try:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT observation_id,observed_at FROM route_observations ORDER BY observed_at,observation_id"
            ).fetchall()
            delete_ids = [str(row[0]) for row in rows if str(row[1]) < cutoff]
            remaining = [str(row[0]) for row in rows if str(row[0]) not in set(delete_ids)]
            excess = max(0, len(remaining) - max_observations)
            delete_ids.extend(remaining[:excess])
            delete_ids = list(dict.fromkeys(delete_ids))
            feedback_before = int(connection.execute("SELECT COUNT(*) FROM route_feedback_events").fetchone()[0])
            if delete_ids:
                placeholders = ",".join("?" for _ in delete_ids)
                connection.execute(
                    f"DELETE FROM route_observations WHERE observation_id IN ({placeholders})",
                    tuple(delete_ids),
                )
                # Receipts may otherwise replay results that point at retained-away rows.
                connection.execute("DELETE FROM memory_command_results")
                connection.execute("DELETE FROM memory_command_receipts")
            feedback_after = int(connection.execute("SELECT COUNT(*) FROM route_feedback_events").fetchone()[0])
            connection.execute(
                "DELETE FROM memory_policy_snapshots WHERE snapshot_id<>? "
                "AND snapshot_id NOT IN (SELECT DISTINCT policy_snapshot_id FROM route_observations) "
                "AND snapshot_id NOT IN (SELECT DISTINCT policy_snapshot_id FROM route_feedback_events)",
                (self._current_policy_snapshot.snapshot_id,),
            )
            remaining_count = int(connection.execute("SELECT COUNT(*) FROM route_observations").fetchone()[0])
            connection.execute("COMMIT")
            return {
                "deleted_observations": len(delete_ids),
                "deleted_feedback": feedback_before - feedback_after,
                "remaining_observations": remaining_count,
            }
        except MemoryStoreError:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        except sqlite3.Error as error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise MemoryStoreError("memory-retention-failed") from error

    def load_admin_result(
        self,
        *,
        idempotency_key: str,
        command_kind: str,
        command_digest: str,
    ) -> dict[str, object] | None:
        connection = self._require_open()
        try:
            row = connection.execute(
                "SELECT command_kind,command_digest,result_digest,result_json "
                "FROM memory_admin_commands WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
        except sqlite3.Error as error:
            raise MemoryStoreError("memory-admin-receipt-read-failed") from error
        if row is None:
            return None
        if str(row[0]) != command_kind or str(row[1]) != command_digest:
            raise MemoryCommandConflict("memory-idempotency-conflict")
        result_json = str(row[3])
        if _digest_text(result_json) != str(row[2]):
            raise MemoryStoreError("memory-admin-result-corrupt")
        try:
            result = json.loads(result_json)
        except json.JSONDecodeError as error:
            raise MemoryStoreError("memory-admin-result-corrupt") from error
        if not isinstance(result, dict) or canonical_json(result) != result_json:
            raise MemoryStoreError("memory-admin-result-corrupt")
        return result

    def execute_purge_command(
        self,
        *,
        idempotency_key: str,
        command_digest: str,
        scope: str,
        summary_digest_before: str,
        summary_digest_after: str,
        managed_profiles_requested: bool = False,
    ) -> tuple[dict[str, object], bool]:
        existing = self.load_admin_result(
            idempotency_key=idempotency_key,
            command_kind="purge-workflow-memory",
            command_digest=command_digest,
        )
        if existing is not None:
            return existing, True
        connection = self._require_open()
        try:
            connection.execute("BEGIN IMMEDIATE")
            if managed_profiles_requested:
                result = {
                    "status": "scope-not-available",
                    "scope": scope,
                    "deleted_observations": 0,
                    "deleted_feedback": 0,
                    "deleted_command_receipts": 0,
                    "summary_digest_before": summary_digest_before,
                    "summary_digest_after": summary_digest_before,
                    "replayed": False,
                    "reason_codes": ["managed-profile-purge-not-available"],
                    "authority_mode": "router-local",
                }
            elif scope not in {"history-only", "analytics-only"}:
                result = {
                    "status": "scope-not-available",
                    "scope": scope,
                    "deleted_observations": 0,
                    "deleted_feedback": 0,
                    "deleted_command_receipts": 0,
                    "summary_digest_before": summary_digest_before,
                    "summary_digest_after": summary_digest_before,
                    "replayed": False,
                    "reason_codes": ["scope-not-available"],
                    "authority_mode": "router-local",
                }
            else:
                observation_count = int(connection.execute("SELECT COUNT(*) FROM route_observations").fetchone()[0])
                feedback_count = int(connection.execute("SELECT COUNT(*) FROM route_feedback_events").fetchone()[0])
                receipt_count = int(connection.execute("SELECT COUNT(*) FROM memory_command_receipts").fetchone()[0])
                if scope == "history-only":
                    connection.execute("DELETE FROM route_feedback_events")
                    connection.execute("DELETE FROM route_feedback")
                    connection.execute("DELETE FROM route_observation_documents")
                    connection.execute("DELETE FROM route_observations")
                    connection.execute("DELETE FROM memory_command_results")
                    connection.execute("DELETE FROM memory_command_receipts")
                    connection.execute(
                        "DELETE FROM memory_policy_snapshots WHERE snapshot_id<>?",
                        (self._current_policy_snapshot.snapshot_id,),
                    )
                else:
                    observation_count = feedback_count = receipt_count = 0
                result = {
                    "status": "purged",
                    "scope": scope,
                    "deleted_observations": observation_count,
                    "deleted_feedback": feedback_count,
                    "deleted_command_receipts": receipt_count,
                    "summary_digest_before": summary_digest_before,
                    "summary_digest_after": summary_digest_after if scope == "history-only" else summary_digest_before,
                    "replayed": False,
                    "reason_codes": [],
                    "authority_mode": "router-local",
                }
            result_json = canonical_json(result)
            connection.execute(
                "INSERT INTO memory_admin_commands("
                "idempotency_key,command_kind,command_digest,result_digest,result_json,created_at"
                ") VALUES (?,?,?,?,?,?)",
                (
                    idempotency_key,
                    "purge-workflow-memory",
                    command_digest,
                    _digest_text(result_json),
                    result_json,
                    _utc_now(),
                ),
            )
            connection.execute("COMMIT")
            return result, False
        except (MemoryCommandConflict, MemoryStoreError):
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        except sqlite3.Error as error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise MemoryStoreError("memory-purge-command-failed") from error

    def save_workflow_pattern(self, pattern) -> None:
        from .candidates import WorkflowPattern

        if not isinstance(pattern, WorkflowPattern):
            raise TypeError("pattern must be WorkflowPattern")
        document = pattern.canonical_json()
        connection = self._require_open()
        try:
            connection.execute(
                "INSERT INTO workflow_patterns(pattern_id,scope,material_evidence_digest,pattern_json,updated_at) "
                "VALUES (?,?,?,?,?) ON CONFLICT(pattern_id) DO UPDATE SET "
                "scope=excluded.scope,material_evidence_digest=excluded.material_evidence_digest,"
                "pattern_json=excluded.pattern_json,updated_at=excluded.updated_at",
                (pattern.pattern_id, pattern.scope.value, pattern.material_evidence_digest, document, pattern.updated_at),
            )
        except sqlite3.Error as error:
            raise MemoryStoreError("workflow-pattern-write-failed") from error

    def save_workflow_candidate(self, candidate):
        from .candidates import WorkflowCandidate, decode_workflow_candidate

        if not isinstance(candidate, WorkflowCandidate):
            raise TypeError("candidate must be WorkflowCandidate")
        connection = self._require_open()
        try:
            row = connection.execute(
                "SELECT candidate_digest,candidate_json FROM workflow_candidates WHERE candidate_id=?",
                (candidate.candidate_id,),
            ).fetchone()
            if row is not None:
                if str(row[0]) != candidate.candidate_digest:
                    raise MemoryCommandConflict("workflow-candidate-id-conflict")
                return decode_workflow_candidate(json.loads(str(row[1])))
            document = candidate.canonical_json()
            connection.execute(
                "INSERT INTO workflow_candidates(candidate_id,pattern_id,status,material_evidence_digest,candidate_digest,candidate_json,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    candidate.candidate_id, candidate.pattern_id, candidate.status,
                    candidate.material_evidence_digest, candidate.candidate_digest,
                    document, candidate.created_at, candidate.created_at,
                ),
            )
            return candidate
        except MemoryCommandConflict:
            raise
        except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError) as error:
            raise MemoryStoreError("workflow-candidate-write-failed") from error

    def load_workflow_candidate(self, candidate_id: str):
        from .candidates import decode_workflow_candidate

        if not isinstance(candidate_id, str) or not candidate_id.startswith("candidate:"):
            raise MemoryStoreError("invalid-candidate-id")
        connection = self._require_open()
        try:
            row = connection.execute(
                "SELECT candidate_json FROM workflow_candidates WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
        except sqlite3.Error as error:
            raise MemoryStoreError("workflow-candidate-read-failed") from error
        if row is None:
            return None
        try:
            candidate = decode_workflow_candidate(json.loads(str(row[0])))
            if candidate.canonical_json() != str(row[0]):
                raise MemoryStoreError("workflow-candidate-corrupt")
            return candidate
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise MemoryStoreError("workflow-candidate-corrupt") from error

    def list_workflow_candidates(self, status: str | None = None):
        from .candidates import decode_workflow_candidate

        connection = self._require_open()
        try:
            if status is None:
                rows = connection.execute(
                    "SELECT candidate_json FROM workflow_candidates ORDER BY created_at,candidate_id"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT candidate_json FROM workflow_candidates WHERE status=? ORDER BY created_at,candidate_id",
                    (status,),
                ).fetchall()
        except sqlite3.Error as error:
            raise MemoryStoreError("workflow-candidate-list-failed") from error
        result = []
        for row in rows:
            try:
                result.append(decode_workflow_candidate(json.loads(str(row[0]))))
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                raise MemoryStoreError("workflow-candidate-corrupt") from error
        return tuple(result)

    def reject_workflow_candidate(
        self,
        candidate_id: str,
        *,
        reason_code: str,
        rejected_at: str,
        suppression_days: int = 30,
    ):
        from datetime import datetime, timedelta, timezone
        from .candidates import candidate_with_status

        if not isinstance(reason_code, str) or _SAFE_CODE.fullmatch(reason_code) is None:
            raise MemoryStoreError("invalid-candidate-rejection-reason")
        if isinstance(suppression_days, bool) or not isinstance(suppression_days, int) or suppression_days < 1:
            raise MemoryStoreError("invalid-candidate-suppression-days")
        try:
            instant = datetime.fromisoformat(rejected_at.replace("Z", "+00:00"))
            if instant.tzinfo is None:
                raise ValueError
        except (TypeError, ValueError) as error:
            raise MemoryStoreError("invalid-candidate-rejected-at") from error
        candidate = self.load_workflow_candidate(candidate_id)
        if candidate is None:
            raise MemoryStoreError("workflow-candidate-not-found")
        rejected = candidate_with_status(candidate, "rejected")
        rejected_json = rejected.canonical_json()
        suppressed_until = (
            instant.astimezone(timezone.utc) + timedelta(days=suppression_days)
        ).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        connection = self._require_open()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE workflow_candidates SET status='rejected',candidate_json=?,updated_at=? WHERE candidate_id=?",
                (rejected_json, rejected_at, candidate_id),
            )
            connection.execute(
                "INSERT INTO candidate_suppressions(pattern_id,material_evidence_digest,reason_code,rejected_at,suppressed_until) "
                "VALUES (?,?,?,?,?) ON CONFLICT(pattern_id,material_evidence_digest) DO UPDATE SET "
                "reason_code=excluded.reason_code,rejected_at=excluded.rejected_at,suppressed_until=excluded.suppressed_until",
                (
                    candidate.pattern_id, candidate.material_evidence_digest, reason_code,
                    rejected_at, suppressed_until,
                ),
            )
            connection.execute("COMMIT")
            return rejected
        except sqlite3.Error as error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise MemoryStoreError("workflow-candidate-reject-failed") from error

    def is_candidate_suppressed(self, pattern_id: str, material_evidence_digest: str, now: str) -> bool:
        connection = self._require_open()
        try:
            row = connection.execute(
                "SELECT suppressed_until FROM candidate_suppressions WHERE pattern_id=? AND material_evidence_digest=?",
                (pattern_id, material_evidence_digest),
            ).fetchone()
        except sqlite3.Error as error:
            raise MemoryStoreError("candidate-suppression-read-failed") from error
        return row is not None and str(row[0]) >= now

    def close(self) -> None:
        if self._closed:
            return
        self._connection.close()
        self._closed = True

    def __enter__(self) -> "MemoryStore":
        self._require_open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: Any,
    ) -> bool:
        self.close()
        return False


__all__ = [
    "MEMORY_DATABASE_NAME",
    "MemoryPolicySnapshot",
    "MemoryPolicySnapshotError",
    "MemoryCommandConflict",
    "MemoryStore",
    "MemoryStoreError",
    "decode_memory_policy_snapshot",
]
