from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from workflow_skill_router.profiles.atomic_io import (
    ProfileIOError,
    atomic_write_canonical_json,
    secure_read_json,
)
from workflow_skill_router.profiles.contract import decode_routing_profile
from workflow_skill_router.schemas.artifacts import canonical_json


SCHEMA_ID = "workflow-skill-router/profile-revision"
SCHEMA_VERSION = "1.0.0"
ARTIFACT_KIND = "profile-revision"
_TARGETS = frozenset({"managed-personal", "managed-workspace-local", "user-personal", "workspace-file"})
_AUTHORITIES = frozenset({"router-local-managed", "reviewed-user-local", "verified-host-workspace"})
_STATUSES = frozenset({"pending", "applied", "rollback", "failed"})
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_PROFILE_ID = re.compile(r"^(personal|workspace):[a-z0-9][a-z0-9._-]{0,63}$")
_REVISION_ID = re.compile(r"^revision:[0-9a-f]{32}$")
_PROPOSAL_ID = re.compile(r"^proposal:[0-9a-f]{32}$")
_CANDIDATE_ID = re.compile(r"^candidate:[0-9a-f]{32}$")
_SAFE_COMPONENT = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class ProfileRevisionError(RuntimeError):
    """Raised when a Profile Revision or immutable snapshot is unsafe."""


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _parse_time(value: object, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str):
        raise ProfileRevisionError("invalid-revision-time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ProfileRevisionError("invalid-revision-time") from error
    if parsed.tzinfo is None:
        raise ProfileRevisionError("invalid-revision-time")
    return value


def _valid_digest(value: object, *, missing: bool = False) -> str:
    if missing and value == "missing":
        return "missing"
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise ProfileRevisionError("invalid-revision-digest")
    return value


@dataclass(frozen=True, slots=True)
class ProfileTarget:
    target_profile_class: str
    profile_id: str
    workspace_identity_digest: str | None

    def __post_init__(self) -> None:
        if self.target_profile_class not in _TARGETS:
            raise ProfileRevisionError("invalid-profile-target")
        if _PROFILE_ID.fullmatch(self.profile_id) is None:
            raise ProfileRevisionError("invalid-profile-id")
        expected_scope = "personal" if self.target_profile_class in {"managed-personal", "user-personal"} else "workspace"
        if self.profile_id.split(":", 1)[0] != expected_scope:
            raise ProfileRevisionError("profile-target-scope-mismatch")
        if expected_scope == "workspace":
            _valid_digest(self.workspace_identity_digest)
        elif self.workspace_identity_digest is not None:
            raise ProfileRevisionError("personal-target-workspace-digest-forbidden")


@dataclass(frozen=True, slots=True)
class ProfileWriteAuthority:
    write_authority: str
    actor_id: str
    session_id: str
    workspace_root: Path | None = None

    def __post_init__(self) -> None:
        if self.write_authority not in _AUTHORITIES:
            raise ProfileRevisionError("invalid-profile-write-authority")
        if not isinstance(self.actor_id, str) or not self.actor_id or len(self.actor_id) > 128:
            raise ProfileRevisionError("invalid-profile-write-actor")
        if not isinstance(self.session_id, str) or not self.session_id or len(self.session_id) > 128:
            raise ProfileRevisionError("invalid-profile-write-session")
        if self.write_authority != "verified-host-workspace" and self.workspace_root is not None:
            raise ProfileRevisionError("workspace-root-not-allowed")

    @classmethod
    def router_local_managed(cls, actor_id: str, session_id: str) -> "ProfileWriteAuthority":
        return cls("router-local-managed", actor_id, session_id)

    @classmethod
    def reviewed_user_local(cls, actor_id: str, session_id: str) -> "ProfileWriteAuthority":
        return cls("reviewed-user-local", actor_id, session_id)

    @classmethod
    def verified_host_workspace(
        cls, actor_id: str, session_id: str, workspace_root: Path
    ) -> "ProfileWriteAuthority":
        return cls("verified-host-workspace", actor_id, session_id, Path(workspace_root))


@dataclass(frozen=True, slots=True)
class ProfileRevision:
    revision_id: str
    revision_digest: str
    profile_id: str
    target_profile_class: str
    previous_profile_digest: str
    new_profile_digest: str
    proposal_id: str
    proposal_digest: str
    candidate_id: str
    candidate_digest: str
    policy_digest: str
    semantic_diff_digest: str
    backtest_digest: str
    actor_id: str
    session_id: str
    write_authority: str
    workspace_identity_digest: str | None
    snapshot_digest: str
    status: str
    rollback_source_revision_id: str | None
    created_at: str
    completed_at: str | None

    def immutable_document(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "target_profile_class": self.target_profile_class,
            "previous_profile_digest": self.previous_profile_digest,
            "new_profile_digest": self.new_profile_digest,
            "proposal_id": self.proposal_id,
            "proposal_digest": self.proposal_digest,
            "candidate_id": self.candidate_id,
            "candidate_digest": self.candidate_digest,
            "policy_digest": self.policy_digest,
            "semantic_diff_digest": self.semantic_diff_digest,
            "backtest_digest": self.backtest_digest,
            "actor_id": self.actor_id,
            "session_id": self.session_id,
            "write_authority": self.write_authority,
            "workspace_identity_digest": self.workspace_identity_digest,
            "snapshot_digest": self.snapshot_digest,
            "rollback_source_revision_id": self.rollback_source_revision_id,
            "created_at": self.created_at,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": SCHEMA_ID,
            "schema_version": SCHEMA_VERSION,
            "artifact_kind": ARTIFACT_KIND,
            "revision_id": self.revision_id,
            "revision_digest": self.revision_digest,
            **self.immutable_document(),
            "status": self.status,
            "completed_at": self.completed_at,
        }

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())


def _revision_identity(immutable: Mapping[str, object]) -> tuple[str, str]:
    digest = _digest(dict(immutable))
    return "revision:" + digest.removeprefix("sha256:")[:32], digest


def create_profile_revision(
    *,
    profile_id: str,
    target: ProfileTarget,
    previous_profile_digest: str,
    new_profile_digest: str,
    proposal_id: str,
    proposal_digest: str,
    candidate_id: str,
    candidate_digest: str,
    policy_digest: str,
    semantic_diff_digest: str,
    backtest_digest: str,
    authority: ProfileWriteAuthority,
    snapshot_digest: str,
    status: str,
    created_at: str,
    rollback_source_revision_id: str | None = None,
    completed_at: str | None = None,
) -> ProfileRevision:
    if profile_id != target.profile_id:
        raise ProfileRevisionError("profile-target-id-mismatch")
    immutable: dict[str, object] = {
        "profile_id": profile_id,
        "target_profile_class": target.target_profile_class,
        "previous_profile_digest": _valid_digest(previous_profile_digest, missing=True),
        "new_profile_digest": _valid_digest(new_profile_digest),
        "proposal_id": proposal_id,
        "proposal_digest": _valid_digest(proposal_digest),
        "candidate_id": candidate_id,
        "candidate_digest": _valid_digest(candidate_digest),
        "policy_digest": _valid_digest(policy_digest),
        "semantic_diff_digest": _valid_digest(semantic_diff_digest),
        "backtest_digest": _valid_digest(backtest_digest),
        "actor_id": authority.actor_id,
        "session_id": authority.session_id,
        "write_authority": authority.write_authority,
        "workspace_identity_digest": target.workspace_identity_digest,
        "snapshot_digest": _valid_digest(snapshot_digest),
        "rollback_source_revision_id": rollback_source_revision_id,
        "created_at": _parse_time(created_at),
    }
    if _PROPOSAL_ID.fullmatch(proposal_id) is None:
        raise ProfileRevisionError("invalid-proposal-id")
    if _CANDIDATE_ID.fullmatch(candidate_id) is None:
        raise ProfileRevisionError("invalid-candidate-id")
    if status not in _STATUSES:
        raise ProfileRevisionError("invalid-revision-status")
    if rollback_source_revision_id is not None and _REVISION_ID.fullmatch(rollback_source_revision_id) is None:
        raise ProfileRevisionError("invalid-rollback-source-revision")
    revision_id, revision_digest = _revision_identity(immutable)
    return ProfileRevision(
        revision_id=revision_id,
        revision_digest=revision_digest,
        status=status,
        completed_at=_parse_time(completed_at, nullable=True),
        **immutable,  # type: ignore[arg-type]
    )


def decode_profile_revision(value: object) -> ProfileRevision:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ProfileRevisionError("invalid-revision-document")
    expected = {
        "schema_id", "schema_version", "artifact_kind", "revision_id", "revision_digest",
        "profile_id", "target_profile_class", "previous_profile_digest", "new_profile_digest",
        "proposal_id", "proposal_digest", "candidate_id", "candidate_digest", "policy_digest",
        "semantic_diff_digest", "backtest_digest", "actor_id", "session_id", "write_authority",
        "workspace_identity_digest", "snapshot_digest", "status", "rollback_source_revision_id",
        "created_at", "completed_at",
    }
    if set(value) != expected:
        raise ProfileRevisionError("revision-fields-mismatch")
    if value["schema_id"] != SCHEMA_ID or value["schema_version"] != SCHEMA_VERSION or value["artifact_kind"] != ARTIFACT_KIND:
        raise ProfileRevisionError("revision-contract-unsupported")
    authority = ProfileWriteAuthority(
        str(value["write_authority"]), str(value["actor_id"]), str(value["session_id"])
    )
    target = ProfileTarget(
        str(value["target_profile_class"]),
        str(value["profile_id"]),
        None if value["workspace_identity_digest"] is None else str(value["workspace_identity_digest"]),
    )
    revision = create_profile_revision(
        profile_id=target.profile_id,
        target=target,
        previous_profile_digest=str(value["previous_profile_digest"]),
        new_profile_digest=str(value["new_profile_digest"]),
        proposal_id=str(value["proposal_id"]),
        proposal_digest=str(value["proposal_digest"]),
        candidate_id=str(value["candidate_id"]),
        candidate_digest=str(value["candidate_digest"]),
        policy_digest=str(value["policy_digest"]),
        semantic_diff_digest=str(value["semantic_diff_digest"]),
        backtest_digest=str(value["backtest_digest"]),
        authority=authority,
        snapshot_digest=str(value["snapshot_digest"]),
        status=str(value["status"]),
        created_at=str(value["created_at"]),
        rollback_source_revision_id=(None if value["rollback_source_revision_id"] is None else str(value["rollback_source_revision_id"])),
        completed_at=(None if value["completed_at"] is None else str(value["completed_at"])),
    )
    if value["revision_id"] != revision.revision_id or value["revision_digest"] != revision.revision_digest:
        raise ProfileRevisionError("revision-digest-mismatch")
    return revision


class ProfileRevisionStore:
    """Bounded revision metadata and immutable snapshot repository."""

    def __init__(self, data_dir: Path, memory_store: Any) -> None:
        self.data_dir = Path(data_dir).expanduser().absolute()
        self.memory_store = memory_store

    @staticmethod
    def snapshot_digest(document: Mapping[str, object]) -> str:
        decoded = decode_routing_profile(document)
        return decoded.profile_digest

    def snapshot_path(self, revision: ProfileRevision) -> Path:
        target = revision.target_profile_class
        profile_name = revision.profile_id.split(":", 1)[1]
        revision_name = revision.revision_id.split(":", 1)[1]
        if _SAFE_COMPONENT.fullmatch(target) is None or _SAFE_COMPONENT.fullmatch(profile_name) is None:
            raise ProfileRevisionError("invalid-revision-snapshot-component")
        return self.data_dir / "profiles" / "revisions" / target / profile_name / f"{revision_name}.json"

    def write_snapshot(self, revision: ProfileRevision, document: Mapping[str, object]) -> str:
        path = self.snapshot_path(revision)
        try:
            try:
                existing = secure_read_json(path, self.data_dir)
            except ProfileIOError as error:
                if str(error) != "profile-directory-missing":
                    raise
                existing = None
            if existing is not None:
                if canonical_json(existing) != canonical_json(document):
                    raise ProfileRevisionError("revision-snapshot-already-exists")
                decoded_existing = decode_routing_profile(existing)
                if decoded_existing.profile_id != revision.profile_id or decoded_existing.profile_digest != revision.snapshot_digest:
                    raise ProfileRevisionError("revision-snapshot-corrupt")
                return revision.snapshot_digest
            decoded = decode_routing_profile(document)
            if decoded.profile_id != revision.profile_id or decoded.profile_digest != revision.snapshot_digest:
                raise ProfileRevisionError("revision-snapshot-digest-mismatch")
            return atomic_write_canonical_json(path, self.data_dir, document, "missing")
        except ProfileIOError as error:
            raise ProfileRevisionError(str(error)) from error

    def load_snapshot(self, revision_id: str) -> dict[str, object]:
        revision = self.load(revision_id)
        if revision is None:
            raise ProfileRevisionError("profile-revision-not-found")
        try:
            document = secure_read_json(self.snapshot_path(revision), self.data_dir)
        except ProfileIOError as error:
            raise ProfileRevisionError(str(error)) from error
        if document is None:
            raise ProfileRevisionError("revision-snapshot-missing")
        decoded = decode_routing_profile(document)
        if decoded.profile_id != revision.profile_id or decoded.profile_digest != revision.snapshot_digest:
            raise ProfileRevisionError("revision-snapshot-corrupt")
        return dict(document)

    def record(self, revision: ProfileRevision) -> ProfileRevision:
        connection = self.memory_store._require_open()
        payload = revision.canonical_json()
        try:
            row = connection.execute(
                "SELECT revision_digest,revision_json FROM profile_revisions WHERE revision_id=?",
                (revision.revision_id,),
            ).fetchone()
            if row is not None:
                if str(row[0]) != revision.revision_digest:
                    raise ProfileRevisionError("profile-revision-id-conflict")
                return decode_profile_revision(json.loads(str(row[1])))
            connection.execute(
                "INSERT INTO profile_revisions("
                "revision_id,profile_id,target_profile_class,status,previous_profile_digest,new_profile_digest,"
                "proposal_id,proposal_digest,candidate_id,candidate_digest,policy_digest,semantic_diff_digest,"
                "backtest_digest,actor_id,session_id,write_authority,workspace_identity_digest,snapshot_digest,"
                "rollback_source_revision_id,revision_digest,revision_json,created_at,completed_at"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    revision.revision_id, revision.profile_id, revision.target_profile_class, revision.status,
                    revision.previous_profile_digest, revision.new_profile_digest, revision.proposal_id,
                    revision.proposal_digest, revision.candidate_id, revision.candidate_digest,
                    revision.policy_digest, revision.semantic_diff_digest, revision.backtest_digest,
                    revision.actor_id, revision.session_id, revision.write_authority,
                    revision.workspace_identity_digest, revision.snapshot_digest,
                    revision.rollback_source_revision_id, revision.revision_digest, payload,
                    revision.created_at, revision.completed_at,
                ),
            )
            return revision
        except ProfileRevisionError:
            raise
        except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError) as error:
            raise ProfileRevisionError("profile-revision-write-failed") from error

    def load(self, revision_id: str) -> ProfileRevision | None:
        connection = self.memory_store._require_open()
        try:
            row = connection.execute(
                "SELECT revision_json FROM profile_revisions WHERE revision_id=?", (revision_id,)
            ).fetchone()
            if row is None:
                return None
            revision = decode_profile_revision(json.loads(str(row[0])))
            if revision.canonical_json() != str(row[0]):
                raise ProfileRevisionError("profile-revision-corrupt")
            return revision
        except ProfileRevisionError:
            raise
        except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError) as error:
            raise ProfileRevisionError("profile-revision-corrupt") from error

    def list(self, profile_id: str) -> tuple[ProfileRevision, ...]:
        connection = self.memory_store._require_open()
        try:
            rows = connection.execute(
                "SELECT revision_json FROM profile_revisions WHERE profile_id=? ORDER BY created_at,revision_id",
                (profile_id,),
            ).fetchall()
            return tuple(decode_profile_revision(json.loads(str(row[0]))) for row in rows)
        except ProfileRevisionError:
            raise
        except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError) as error:
            raise ProfileRevisionError("profile-revision-list-failed") from error

    def update(self, revision: ProfileRevision) -> ProfileRevision:
        connection = self.memory_store._require_open()
        try:
            cursor = connection.execute(
                "UPDATE profile_revisions SET status=?,revision_json=?,completed_at=? WHERE revision_id=? AND revision_digest=?",
                (revision.status, revision.canonical_json(), revision.completed_at, revision.revision_id, revision.revision_digest),
            )
            if cursor.rowcount != 1:
                raise ProfileRevisionError("profile-revision-state-conflict")
            return revision
        except ProfileRevisionError:
            raise
        except sqlite3.Error as error:
            raise ProfileRevisionError("profile-revision-update-failed") from error


__all__ = [
    "ProfileRevision", "ProfileRevisionError", "ProfileRevisionStore", "ProfileTarget",
    "ProfileWriteAuthority", "create_profile_revision", "decode_profile_revision",
]
