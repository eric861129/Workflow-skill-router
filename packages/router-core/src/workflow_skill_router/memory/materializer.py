from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sqlite3
import stat
from typing import Mapping

from workflow_skill_router.profiles.atomic_io import (
    ProfileIOError,
    atomic_write_canonical_json,
    current_json_digest,
    secure_read_json,
)
from workflow_skill_router.profiles.contract import decode_routing_profile
from workflow_skill_router.profiles.resolver import lint_profile
from workflow_skill_router.schemas.artifacts import canonical_json

from .backtest import backtest_profile_update
from .models import MemoryMode
from .profile_diff import diff_profiles
from .proposals import (
    ProfileUpdateProposal,
    create_profile_update_proposal_from_document,
    decode_profile_update_proposal,
)
from .revisions import (
    ProfileRevision,
    ProfileRevisionError,
    ProfileRevisionStore,
    ProfileTarget,
    ProfileWriteAuthority,
    create_profile_revision,
    decode_profile_revision,
)
from .store import MemoryCommandConflict, MemoryStoreError


class ProfileMaterializationError(RuntimeError):
    """Raised when an approved Profile proposal cannot be safely materialized."""


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _is_link_or_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    reparse = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse)


class ProfileMaterializer:
    """CAS materializer for approved, digest-bound Profile proposals."""

    def __init__(self, store, data_dir: Path, policy) -> None:
        self.store = store
        self.data_dir = Path(data_dir).expanduser().absolute()
        self.policy = policy
        self.revisions = ProfileRevisionStore(self.data_dir, store)

    def target_path(
        self,
        proposal: ProfileUpdateProposal,
        authority: ProfileWriteAuthority,
    ) -> tuple[Path, Path]:
        profile = decode_routing_profile(proposal.proposed_profile)
        target = proposal.target_profile_class
        if self.policy.mode is MemoryMode.AUTOMATIC and target in {"user-personal", "workspace-file"}:
            raise ProfileMaterializationError("automatic-user-profile-forbidden")
        if target == "managed-personal":
            if authority.write_authority != "router-local-managed":
                raise ProfileMaterializationError("profile-authority-mismatch")
            if profile.scope != "personal":
                raise ProfileMaterializationError("profile-target-scope-mismatch")
            return (
                self.data_dir / "profiles" / "managed" / "personal" / "adaptive-memory.json",
                self.data_dir,
            )
        if target == "user-personal":
            if authority.write_authority != "reviewed-user-local":
                raise ProfileMaterializationError("profile-authority-mismatch")
            if profile.scope != "personal":
                raise ProfileMaterializationError("profile-target-scope-mismatch")
            name = profile.profile_id.split(":", 1)[1]
            return self.data_dir / "profiles" / "personal" / f"{name}.json", self.data_dir
        if target == "managed-workspace-local":
            raise ProfileMaterializationError("target-not-available")
        if target == "workspace-file":
            if authority.write_authority != "verified-host-workspace" or authority.workspace_root is None:
                raise ProfileMaterializationError("profile-authority-mismatch")
            root = authority.workspace_root.expanduser().absolute()
            if not root.is_dir() or _is_link_or_reparse(root):
                raise ProfileMaterializationError("workspace-authority-root-invalid")
            if profile.scope != "workspace" or proposal.workspace_identity_digest is None:
                raise ProfileMaterializationError("profile-target-scope-mismatch")
            return root / ".codex" / "workflow-skill-router.json", root
        raise ProfileMaterializationError("profile-target-unsupported")

    def _load_receipt(self, idempotency_key: str, command_digest: str) -> ProfileRevision | None:
        connection = self.store._require_open()
        row = connection.execute(
            "SELECT command_digest,result_json FROM profile_materialization_receipts WHERE idempotency_key=?",
            (idempotency_key,),
        ).fetchone()
        if row is None:
            return None
        if str(row[0]) != command_digest:
            raise ProfileMaterializationError("idempotency-conflict")
        try:
            return decode_profile_revision(json.loads(str(row[1])))
        except (json.JSONDecodeError, TypeError, ValueError, ProfileRevisionError) as error:
            raise ProfileMaterializationError("profile-materialization-receipt-corrupt") from error

    def _load_marker(self, proposal_id: str) -> dict[str, object] | None:
        connection = self.store._require_open()
        row = connection.execute(
            "SELECT marker_digest,marker_json FROM profile_recovery_markers WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            return None
        try:
            marker = json.loads(str(row[1]))
        except json.JSONDecodeError as error:
            raise ProfileMaterializationError("profile-recovery-marker-corrupt") from error
        if not isinstance(marker, dict) or _digest(marker) != str(row[0]):
            raise ProfileMaterializationError("profile-recovery-marker-corrupt")
        return marker

    def _begin(self, revision: ProfileRevision, marker: Mapping[str, object]) -> None:
        connection = self.store._require_open()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self.revisions.record(revision)
            connection.execute(
                "INSERT INTO profile_recovery_markers(proposal_id,revision_id,marker_digest,marker_json,created_at) "
                "VALUES (?,?,?,?,?)",
                (
                    revision.proposal_id,
                    revision.revision_id,
                    _digest(marker),
                    canonical_json(marker),
                    revision.created_at,
                ),
            )
            connection.execute("COMMIT")
        except (sqlite3.Error, ProfileRevisionError) as error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise ProfileMaterializationError("profile-materialization-begin-failed") from error

    def _finalize(
        self,
        revision: ProfileRevision,
        proposal: ProfileUpdateProposal,
        *,
        idempotency_key: str,
        command_digest: str,
        completed_at: str,
    ) -> ProfileRevision:
        final_status = "rollback" if revision.rollback_source_revision_id is not None else "applied"
        completed = replace(revision, status=final_status, completed_at=completed_at)
        updated_proposal = replace(
            proposal,
            status="applied",
            state_version=proposal.state_version + 1,
        )
        connection = self.store._require_open()
        try:
            connection.execute("BEGIN IMMEDIATE")
            revision_cursor = connection.execute(
                "UPDATE profile_revisions SET status=?,revision_json=?,completed_at=? "
                "WHERE revision_id=? AND status='pending' AND revision_digest=?",
                (
                    completed.status,
                    completed.canonical_json(),
                    completed.completed_at,
                    completed.revision_id,
                    completed.revision_digest,
                ),
            )
            if revision_cursor.rowcount != 1:
                existing = self.revisions.load(completed.revision_id)
                if existing != completed:
                    raise ProfileMaterializationError("profile-revision-state-conflict")
            proposal_cursor = connection.execute(
                "UPDATE profile_update_proposals SET status='applied',state_version=?,proposal_json=?,updated_at=? "
                "WHERE proposal_id=? AND state_version=? AND status='approved'",
                (
                    updated_proposal.state_version,
                    updated_proposal.canonical_json(),
                    completed_at,
                    proposal.proposal_id,
                    proposal.state_version,
                ),
            )
            if proposal_cursor.rowcount != 1:
                row = connection.execute(
                    "SELECT proposal_json FROM profile_update_proposals WHERE proposal_id=?",
                    (proposal.proposal_id,),
                ).fetchone()
                if row is None or decode_profile_update_proposal(json.loads(str(row[0]))) != updated_proposal:
                    raise ProfileMaterializationError("profile-proposal-state-conflict")
            connection.execute(
                "INSERT INTO profile_materialization_receipts("
                "idempotency_key,proposal_id,command_digest,revision_id,result_json,created_at"
                ") VALUES (?,?,?,?,?,?)",
                (
                    idempotency_key,
                    proposal.proposal_id,
                    command_digest,
                    completed.revision_id,
                    completed.canonical_json(),
                    completed_at,
                ),
            )
            connection.execute(
                "DELETE FROM profile_recovery_markers WHERE proposal_id=?",
                (proposal.proposal_id,),
            )
            connection.execute("COMMIT")
            return completed
        except ProfileMaterializationError:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError, ProfileRevisionError) as error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise ProfileMaterializationError("profile-materialization-finalize-failed") from error

    def _mark_failed(
        self,
        revision: ProfileRevision,
        proposal: ProfileUpdateProposal,
        *,
        failed_at: str,
    ) -> None:
        failed_revision = replace(revision, status="failed", completed_at=failed_at)
        failed_proposal = replace(
            proposal,
            status="failed",
            state_version=proposal.state_version + 1,
        )
        connection = self.store._require_open()
        try:
            connection.execute("BEGIN IMMEDIATE")
            revision_cursor = connection.execute(
                "UPDATE profile_revisions SET status='failed',revision_json=?,completed_at=? "
                "WHERE revision_id=? AND status='pending' AND revision_digest=?",
                (
                    failed_revision.canonical_json(),
                    failed_at,
                    failed_revision.revision_id,
                    failed_revision.revision_digest,
                ),
            )
            if revision_cursor.rowcount != 1:
                raise ProfileMaterializationError("profile-revision-state-conflict")
            proposal_cursor = connection.execute(
                "UPDATE profile_update_proposals SET status='failed',state_version=?,proposal_json=?,updated_at=? "
                "WHERE proposal_id=? AND state_version=? AND status='approved'",
                (
                    failed_proposal.state_version,
                    failed_proposal.canonical_json(),
                    failed_at,
                    proposal.proposal_id,
                    proposal.state_version,
                ),
            )
            if proposal_cursor.rowcount != 1:
                raise ProfileMaterializationError("profile-proposal-state-conflict")
            connection.execute(
                "DELETE FROM profile_recovery_markers WHERE proposal_id=?",
                (proposal.proposal_id,),
            )
            connection.execute("COMMIT")
        except ProfileMaterializationError:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        except sqlite3.Error as error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise ProfileMaterializationError(
                "profile-materialization-failure-record-failed"
            ) from error

    def _mark_stale(self, proposal: ProfileUpdateProposal) -> None:
        try:
            self.store.set_profile_update_proposal_status(
                proposal.proposal_id,
                "stale",
                expected_state_version=proposal.state_version,
            )
        except (MemoryStoreError, MemoryCommandConflict) as error:
            raise ProfileMaterializationError("profile-proposal-state-conflict") from error

    def _preflight(
        self,
        proposal: ProfileUpdateProposal,
        authority: ProfileWriteAuthority,
    ) -> tuple[Path, Path, object, object]:
        # User-owned targets are forbidden under automatic mode before any
        # digest or filesystem processing.
        target_path, fixed_root = self.target_path(proposal, authority)
        if proposal.policy_digest != self.policy.policy_digest:
            raise ProfileMaterializationError("profile-policy-drift")
        candidate = self.store.load_workflow_candidate(proposal.candidate_id)
        if candidate is None or candidate.candidate_digest != proposal.candidate_digest:
            raise ProfileMaterializationError("profile-candidate-drift")
        proposed = decode_routing_profile(proposal.proposed_profile)
        if proposed.profile_digest != proposal.proposed_profile_digest:
            raise ProfileMaterializationError("proposed-profile-digest-mismatch")
        if any(item.severity == "error" for item in lint_profile(proposed)):
            raise ProfileMaterializationError("profile-lint-failed")
        try:
            current_document = secure_read_json(target_path, fixed_root)
        except ProfileIOError as error:
            if str(error) == "profile-directory-missing":
                current_document = None
            else:
                raise ProfileMaterializationError(str(error)) from error
        current = None if current_document is None else decode_routing_profile(current_document)
        current_digest = "missing" if current is None else current.profile_digest
        if current_digest != proposal.expected_profile_digest:
            self._mark_stale(proposal)
            raise ProfileMaterializationError("profile-drift")
        rerun_diff = diff_profiles(current, proposed)
        if rerun_diff.semantic_diff_digest != proposal.semantic_diff_digest:
            self._mark_stale(proposal)
            raise ProfileMaterializationError("profile-diff-drift")
        observations = tuple(self.store.list_route_observations())
        current_profiles = () if current is None else (current,)
        rerun_backtest = backtest_profile_update(current_profiles, proposed, observations, candidate)
        if not rerun_backtest.acceptable or rerun_backtest.backtest_digest != proposal.backtest_digest:
            self._mark_stale(proposal)
            raise ProfileMaterializationError("profile-backtest-drift")
        return target_path, fixed_root, proposed, candidate

    def _rollback_source(self, proposal_id: str) -> str | None:
        row = self.store._require_open().execute(
            "SELECT source_revision_id FROM rollback_proposal_sources WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()
        return None if row is None else str(row[0])

    def create_rollback_proposal(
        self,
        source_revision_id: str,
        *,
        authority: ProfileWriteAuthority,
        expected_profile_digest: str,
        now: str,
        ttl_days: int = 7,
    ) -> ProfileUpdateProposal:
        source_revision = self.revisions.load(source_revision_id)
        if source_revision is None or source_revision.status not in {"applied", "rollback"}:
            raise ProfileMaterializationError("rollback-source-revision-unavailable")
        source_proposal = self.store.load_profile_update_proposal(source_revision.proposal_id)
        if source_proposal is None:
            raise ProfileMaterializationError("rollback-source-proposal-missing")
        candidate = self.store.load_workflow_candidate(source_revision.candidate_id)
        if candidate is None or candidate.candidate_digest != source_revision.candidate_digest:
            raise ProfileMaterializationError("rollback-source-candidate-drift")
        target_path, fixed_root = self.target_path(source_proposal, authority)
        try:
            current_document = secure_read_json(target_path, fixed_root)
        except ProfileIOError as error:
            raise ProfileMaterializationError(str(error)) from error
        if current_document is None:
            raise ProfileMaterializationError("rollback-current-profile-missing")
        current_profile = decode_routing_profile(current_document)
        if current_profile.profile_digest != expected_profile_digest:
            raise ProfileMaterializationError("profile-drift")
        snapshot = self.revisions.load_snapshot(source_revision_id)
        proposal = create_profile_update_proposal_from_document(
            self.store,
            candidate,
            current_profile=current_profile,
            proposed_profile_document=snapshot,
            target_profile_class=source_revision.target_profile_class,
            workspace_identity_digest=source_revision.workspace_identity_digest,
            policy=self.policy,
            now=now,
            ttl_days=ttl_days,
        )
        connection = self.store._require_open()
        try:
            connection.execute(
                "INSERT INTO rollback_proposal_sources(proposal_id,source_revision_id,created_at) VALUES (?,?,?)",
                (proposal.proposal_id, source_revision_id, now),
            )
        except sqlite3.IntegrityError:
            row = connection.execute(
                "SELECT source_revision_id FROM rollback_proposal_sources WHERE proposal_id=?",
                (proposal.proposal_id,),
            ).fetchone()
            if row is None or str(row[0]) != source_revision_id:
                raise ProfileMaterializationError("rollback-proposal-source-conflict")
        return proposal

    def apply_approved(
        self,
        proposal_id: str,
        *,
        authority: ProfileWriteAuthority,
        expected_state_version: int,
        idempotency_key: str,
        correlation_id: str,
        now: str,
        rollback_source_revision_id: str | None = None,
    ) -> ProfileRevision:
        bound_rollback_source = self._rollback_source(proposal_id)
        if rollback_source_revision_id is not None and rollback_source_revision_id != bound_rollback_source:
            raise ProfileMaterializationError("rollback-proposal-source-conflict")
        rollback_source_revision_id = bound_rollback_source
        command = {
            "proposal_id": proposal_id,
            "expected_state_version": expected_state_version,
            "write_authority": authority.write_authority,
            "actor_id": authority.actor_id,
            "session_id": authority.session_id,
            "correlation_id": correlation_id,
            "rollback_source_revision_id": rollback_source_revision_id,
            "now": now,
        }
        command_digest = _digest(command)
        replay = self._load_receipt(idempotency_key, command_digest)
        if replay is not None:
            return replay
        proposal = self.store.load_profile_update_proposal(proposal_id)
        if proposal is None:
            raise ProfileMaterializationError("profile-proposal-not-found")
        if proposal.state_version != expected_state_version:
            raise ProfileMaterializationError("profile-proposal-state-conflict")
        if proposal.status != "approved":
            raise ProfileMaterializationError("profile-proposal-not-approved")

        marker = self._load_marker(proposal_id)
        if marker is not None:
            if marker.get("command_digest") != command_digest or marker.get("idempotency_key") != idempotency_key:
                raise ProfileMaterializationError("profile-recovery-command-conflict")
            revision = self.revisions.load(str(marker.get("revision_id")))
            if revision is None:
                raise ProfileMaterializationError("profile-recovery-revision-missing")
            target_path, fixed_root = self.target_path(proposal, authority)
            if current_json_digest(target_path, fixed_root) != revision.new_profile_digest:
                raise ProfileMaterializationError("profile-recovery-state-mismatch")
            self.revisions.load_snapshot(revision.revision_id)
            return self._finalize(
                revision,
                proposal,
                idempotency_key=idempotency_key,
                command_digest=command_digest,
                completed_at=now,
            )

        target_path, fixed_root, proposed, candidate = self._preflight(proposal, authority)
        profile_id = proposed.profile_id
        target = ProfileTarget(
            proposal.target_profile_class,
            profile_id,
            proposal.workspace_identity_digest,
        )
        revision = create_profile_revision(
            profile_id=profile_id,
            target=target,
            previous_profile_digest=proposal.expected_profile_digest,
            new_profile_digest=proposal.proposed_profile_digest,
            proposal_id=proposal.proposal_id,
            proposal_digest=proposal.proposal_digest,
            candidate_id=candidate.candidate_id,
            candidate_digest=candidate.candidate_digest,
            policy_digest=proposal.policy_digest,
            semantic_diff_digest=proposal.semantic_diff_digest,
            backtest_digest=proposal.backtest_digest,
            authority=authority,
            snapshot_digest=proposal.proposed_profile_digest,
            status="pending",
            created_at=now,
            rollback_source_revision_id=rollback_source_revision_id,
        )
        self.revisions.write_snapshot(revision, proposal.proposed_profile)
        marker_document = {
            "proposal_id": proposal.proposal_id,
            "revision_id": revision.revision_id,
            "idempotency_key": idempotency_key,
            "command_digest": command_digest,
            "new_profile_digest": revision.new_profile_digest,
            "snapshot_digest": revision.snapshot_digest,
        }
        self._begin(revision, marker_document)
        try:
            atomic_write_canonical_json(
                target_path,
                fixed_root,
                proposal.proposed_profile,
                proposal.expected_profile_digest,
            )
        except Exception as error:
            self._mark_failed(revision, proposal, failed_at=now)
            raise ProfileMaterializationError("profile-atomic-write-failed") from error
        return self._finalize(
            revision,
            proposal,
            idempotency_key=idempotency_key,
            command_digest=command_digest,
            completed_at=now,
        )


__all__ = ["ProfileMaterializationError", "ProfileMaterializer"]
