from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
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
            for table in (
                "route_feedback",
                "route_observations",
                "memory_policy_snapshots",
                "memory_command_receipts",
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
            "route_feedback": counts["route_feedback"],
            "route_observations": counts["route_observations"],
            "memory_policy_snapshots": counts["memory_policy_snapshots"],
        }

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
    "MemoryStore",
    "MemoryStoreError",
    "decode_memory_policy_snapshot",
]
