"""Typed MCP adapter over the local Memory service; no caller-provided authority.

Preview is a pure, deterministic projection of retained Candidate evidence. The
mutating transition reconstructs that projection and compares its full Digest
before storing a Proposal. A changed Profile, Policy or Backtest cannot silently
turn a reviewed preview into a different write.
"""
from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from workflow_skill_router.profiles.atomic_io import ProfileIOError, secure_read_json
from workflow_skill_router.profiles.contract import decode_routing_profile
from workflow_skill_router.runtime_readiness import CapabilityUnavailable
from workflow_skill_router.schemas.artifacts import canonical_json
from workflow_skill_router.service_models import (
    MemoryCandidatesResult, MemoryProfileResult, MemoryStatusResult,
)

from .analytics import HistorySummary, PurgeMemoryCommand, PurgeMemoryResult
from .backtest import _same_pattern
from .candidates import _material_digest, _metrics, _passes
from .feedback import RecordRouteFeedbackCommand
from .managed_profiles import verify_workspace_root
from .materializer import ProfileMaterializer
from .models import MemoryMode, MemoryScope
from .proposals import create_profile_update_proposal, transition_profile_update
from .revisions import ProfileRevisionStore, ProfileWriteAuthority, decode_profile_revision
from .service import RememberWorkflowCommand, WorkflowMemoryService
from .store import MemoryCommandConflict, MemoryStore, MemoryStoreError
from .workflow_reader import MemoryRequestContext


# Only these bounded reasons cross the MCP boundary. Filesystem or decoder
# exception text is never passed through as an error message or reason.
MEMORY_REASON_CODES = (
    "memory-disabled", "personal-policy-missing", "workspace-policy-missing",
    "invalid-memory-policy", "ambiguous-memory-policy", "workspace-policy-exceeds-ceiling",
    "workspace-root-unverified", "explicit-no-memory", "workflow-not-terminal",
    "required-gate-not-passed", "unknown-side-effect-outcome", "sensitive-route-excluded",
    "insufficient-evidence", "candidate-conflict", "candidate-suppressed",
    "candidate-not-proposed", "workflow-candidate-not-found", "profile-preview-stale",
    "profile-policy-drift", "profile-drift", "profile-candidate-drift",
    "profile-proposal-state-conflict", "profile-proposal-expired", "profile-promotion-disabled",
    "profile-target-not-allowed", "profile-backtest-failed", "profile-backtest-drift",
    "profile-lint-failed", "profile-authority-mismatch", "profile-proposal-not-found",
    "memory-store-unavailable", "memory-operation-failed", "idempotency-conflict",
    "memory-idempotency-conflict", "stale-summary-digest", "scope-not-available",
    "managed-profile-purge-not-available", "rollback-source-revision-unavailable",
    "automatic-user-profile-write-forbidden", "explicit-route-requires-review",
    "workflow-context-mismatch", "workflow-run-not-found", "workflow-not-completed",
    "no-matchable-routing-context", "matcher-seed-required", "unresolved-skill-identity",
    "risk-class-excluded", "profile-versioning-required", "candidate-evidence-drift",
)


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _reasons(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value if value in MEMORY_REASON_CODES else "memory-operation-failed" for value in values))


def _context(command) -> MemoryRequestContext:
    return MemoryRequestContext(command.context.session_id, command.context.actor, command.context.runtime_policy_snapshot_id)


def _root(command) -> Path | None:
    value = getattr(command, "workspace_root", None)
    return None if value is None else Path(value)


def _view(proposal) -> dict[str, object]:
    # JSON strings are canonical, server-compiled routing structures, never an
    # untyped caller patch. Inputs cannot send these values back as replacements.
    return {
        name: getattr(proposal, name)
        for name in (
            "proposal_id", "proposal_digest", "candidate_id", "candidate_digest",
            "status", "state_version", "target_profile_class", "expected_profile_digest",
            "proposed_profile_digest", "semantic_diff_digest", "backtest_digest",
            "policy_digest", "workspace_identity_digest", "created_at", "expires_at",
        )
    } | {
        "proposed_profile_json": canonical_json(proposal.proposed_profile),
        "semantic_diff_json": canonical_json(proposal.semantic_diff),
        "backtest": proposal.backtest,
    }


class MemoryToolAdapter:
    def __init__(self, memory: WorkflowMemoryService) -> None:
        self.memory = memory
        self.data_dir = memory._data_dir

    def require_local_capability(self, name, command) -> None:
        # Conditional tools validate the bound target again immediately before
        # mutation. No flag in a model-supplied command can grant Host authority.
        store = MemoryStore.open_existing(self.data_dir, read_only=True)
        if store is None:
            return
        with store:
            if name == "rollback_profile_revision":
                record = ProfileRevisionStore(self.data_dir, store).load(command.source_revision_id)
            else:
                record = store.load_profile_update_proposal(command.proposal_id)
            if record is not None and record.target_profile_class == "workspace-file":
                self._host_required(name)

    @staticmethod
    def _host_required(name):
        raise CapabilityUnavailable.for_local_condition(
            name, required_capabilities=("verified-host-file-write-authority",),
            fallback_action="Review the bound Proposal using a verified Host integration; MCP Client roots alone do not grant Workspace file-write authority.",
        )

    def get_memory_status(self, command) -> MemoryStatusResult:
        repository, effective = self.memory._effective_policy(_root(command))
        summary = HistorySummary.empty()
        store = MemoryStore.open_existing(self.data_dir, read_only=True)
        exists = store is not None
        if store is not None:
            with store:
                # Deliberately global: purge has an explicit scope, not an
                # ambiguous Workspace selector. No raw history is returned.
                summary = HistorySummary.create(store.list_route_observations(), store.list_route_feedback())
        return MemoryStatusResult(
            effective.mode.value, effective.personal_mode.value,
            None if effective.workspace_requested_mode is None else effective.workspace_requested_mode.value,
            effective.policy_digest, effective.capture_enabled, effective.candidate_generation_enabled,
            effective.profile_promotion, effective.allowed_targets, exists, _reasons(effective.reason_codes),
            summary.summary_digest, summary.eligible_workflow_count,
        )

    def remember_workflow(self, command):
        result = self.memory.remember_workflow(RememberWorkflowCommand(
            _context(command), command.workflow_run_id, _root(command), None,
            command.target_profile_class, command.risk_class, command.side_effect_outcome,
            command.one_shot, command.idempotency_key, command.correlation_id,
        ))
        if result.status != "recorded":
            return replace(result, reason_codes=_reasons(result.reason_codes))
        scope = MemoryScope.WORKSPACE if command.target_profile_class in {"managed-workspace-local", "workspace-file"} else MemoryScope.PERSONAL
        if not result.replayed:
            self.memory.rebuild_candidates(scope, workspace_root=_root(command))
        store = MemoryStore.open_existing(self.data_dir, read_only=True)
        if store is not None:
            with store:
                observation = store.load_route_observation(result.observation_id)
                candidates = [item for item in store.list_workflow_candidates() if observation is not None and _same_pattern(observation, item)]
                if candidates:
                    result = replace(result, candidate_id=candidates[-1].candidate_id)
        return result

    def record_route_feedback(self, command):
        result = self.memory.record_route_feedback(RecordRouteFeedbackCommand(
            _context(command), command.workflow_run_id, _root(command), command.observation_id,
            command.feedback_type, command.reason_code, command.correction_dimensions,
            command.original_route_digest, command.corrected_route_digest, None,
            command.idempotency_key, command.correlation_id,
        ))
        return replace(result, reason_codes=_reasons(result.reason_codes))

    def _in_scope(self, record, root: Path | None) -> bool:
        if record.workspace_identity_digest is None:
            return record.target_profile_class in {"managed-personal", "user-personal"}
        return root is not None and verify_workspace_root(root).digest == record.workspace_identity_digest

    def list_workflow_candidates(self, command) -> MemoryCandidatesResult:
        store = MemoryStore.open_existing(self.data_dir, read_only=True)
        if store is None:
            return MemoryCandidatesResult((), False)
        with store:
            candidates = [item for item in store.list_workflow_candidates(command.status) if self._in_scope(item, _root(command))]
        summaries = tuple({
            name: getattr(candidate, name)
            for name in ("candidate_id", "candidate_digest", "pattern_id", "status", "recommendation_mode", "confidence", "target_profile_class", "workspace_identity_digest", "material_evidence_digest", "policy_digest", "created_at")
        } | {"scope": candidate.scope.value, "metrics": candidate.metrics.to_dict(), "reason_codes": list(_reasons(candidate.reason_codes))}
            for candidate in candidates[:command.limit])
        return MemoryCandidatesResult(summaries, len(candidates) > command.limit)

    @staticmethod
    def _promotion_enabled(effective):
        if effective.mode not in {MemoryMode.REVIEWED, MemoryMode.AUTOMATIC} or effective.profile_promotion == "disabled":
            raise MemoryStoreError("profile-promotion-disabled")
        if effective.policy.features.profile_versioning.mode != "required":
            raise MemoryStoreError("profile-versioning-required")

    def _current_profile(self, candidate, root):
        if not self._in_scope(candidate, root):
            raise MemoryStoreError("workspace-root-unverified")
        target = candidate.target_profile_class
        if target.startswith("managed-"):
            return self.memory._load_current_managed_profile(candidate)
        if target == "user-personal":
            # Candidate compilation for a new user profile uses this fixed ID;
            # the caller never supplies a filename or Profile ID.
            path, fixed = self.data_dir / "profiles/personal/adaptive-memory.json", self.data_dir
        elif target == "workspace-file" and root is not None:
            path, fixed = root / ".codex/workflow-skill-router.json", root
        else:
            raise MemoryStoreError("profile-target-not-allowed")
        try:
            document = secure_read_json(path, fixed)
        except ProfileIOError as error:
            if str(error) != "profile-directory-missing":
                raise
            document = None
        if document is None:
            return None
        profile = decode_routing_profile(document, expected_scope=candidate.scope.value)
        if target == "user-personal" and profile.profile_id != "personal:adaptive-memory":
            raise MemoryStoreError("profile-target-not-allowed")
        return profile

    @staticmethod
    def _assert_candidate_evidence(store, candidate, effective):
        if candidate is None or candidate.status != "proposed":
            raise MemoryStoreError("candidate-not-proposed")
        observations = tuple(item for item in store.list_route_observations()
            if _same_pattern(item, candidate) and item.route_source == candidate.profile_source_class)
        feedback = tuple(store.list_route_feedback())
        if _material_digest(observations, feedback) != candidate.material_evidence_digest:
            raise MemoryStoreError("candidate-evidence-drift")
        if not _passes(_metrics(observations, feedback), effective, "reviewed"):
            raise MemoryStoreError("insufficient-evidence")

    def _preview(self, store, candidate, effective, root):
        self._promotion_enabled(effective)
        self._assert_candidate_evidence(store, candidate, effective)
        if candidate.policy_digest != effective.policy_digest:
            raise MemoryStoreError("profile-policy-drift")
        current = self._current_profile(candidate, root)
        # A stable instant makes the view reproducible without a write/cache.
        # The full Proposal Digest binds Profile, Policy, Candidate and Backtest.
        return create_profile_update_proposal(
            store, candidate, current_profile=current, policy=effective,
            now=candidate.created_at, persist=False,
        )

    def preview_profile_update(self, command) -> MemoryProfileResult:
        try:
            _, effective = self.memory._effective_policy(_root(command))
            self._promotion_enabled(effective)
            store = MemoryStore.open_existing(self.data_dir, read_only=True)
            if store is None:
                return MemoryProfileResult("not-found", None, reason_codes=("workflow-candidate-not-found",))
            with store:
                candidate = store.load_workflow_candidate(command.candidate_id)
                if candidate is None:
                    return MemoryProfileResult("not-found", None, reason_codes=("workflow-candidate-not-found",))
                proposal = self._preview(store, candidate, effective, _root(command))
            return MemoryProfileResult("previewed", _view(proposal))
        except (ValueError, RuntimeError, OSError, sqlite3.Error) as error:
            return MemoryProfileResult("blocked", None, reason_codes=_reasons((str(error),)))

    @staticmethod
    def _receipt_key(command) -> str:
        return "mcp-memory:" + hashlib.sha256(command.idempotency_key.encode()).hexdigest()

    def _read_receipt(self, store, command, kind):
        return store.load_admin_result(idempotency_key=self._receipt_key(command), command_kind=kind, command_digest=_digest(asdict(command)))

    @staticmethod
    def _replay(store, receipt):
        proposal = store.load_profile_update_proposal(receipt["proposal_id"])
        if proposal is None:
            raise MemoryStoreError("profile-proposal-not-found")
        proposal = replace(proposal, status=receipt["proposal_status"], state_version=receipt["state_version"])
        return MemoryProfileResult(receipt["status"], _view(proposal), receipt["revision_id"], receipt["revision_digest"], True)

    def _save_receipt(self, store, command, kind, result):
        document = {
            "proposal_id": result.proposal["proposal_id"], "proposal_status": result.proposal["status"],
            "state_version": result.proposal["state_version"], "status": result.status,
            "revision_id": result.revision_id, "revision_digest": result.revision_digest,
        }
        payload = canonical_json(document)
        store._require_open().execute(
            "INSERT INTO memory_admin_commands(idempotency_key,command_kind,command_digest,result_digest,result_json,created_at) VALUES (?,?,?,?,?,?)",
            (self._receipt_key(command), kind, _digest(asdict(command)), _digest(document), payload, _now()),
        )
        return result

    def _resolve_bound_preview(self, store, command, effective):
        existing = store.load_profile_update_proposal(command.proposal_id)
        if existing is not None:
            if not self._in_scope(existing, _root(command)):
                raise MemoryStoreError("workspace-root-unverified")
            return existing
        for candidate in store.list_workflow_candidates("proposed"):
            if not self._in_scope(candidate, _root(command)):
                continue
            try:
                proposed = self._preview(store, candidate, effective, _root(command))
            except (ValueError, RuntimeError, OSError):
                continue
            if proposed.proposal_id == command.proposal_id:
                return proposed
        raise MemoryStoreError("profile-preview-stale")

    def _authority(self, record, command, effective, tool):
        self._promotion_enabled(effective)
        target = record.target_profile_class
        if target not in effective.allowed_targets:
            raise MemoryStoreError("profile-target-not-allowed")
        if target == "workspace-file":
            self._host_required(tool)
        if target == "user-personal":
            if effective.mode is MemoryMode.AUTOMATIC:
                raise MemoryStoreError("automatic-user-profile-write-forbidden")
            return ProfileWriteAuthority.reviewed_user_local(command.context.actor, command.context.session_id)
        if target in {"managed-personal", "managed-workspace-local"}:
            return ProfileWriteAuthority.router_local_managed(command.context.actor, command.context.session_id)
        raise MemoryStoreError("profile-target-not-allowed")

    def transition_profile_update(self, command) -> MemoryProfileResult:
        try:
            _, effective = self.memory._effective_policy(_root(command))
            self._promotion_enabled(effective)
            store = MemoryStore.open_existing(self.data_dir, read_only=True)
            if store is None:
                raise MemoryStoreError("memory-store-unavailable")
            with store:
                receipt = self._read_receipt(store, command, "mcp-profile-transition")
                if receipt is not None:
                    return self._replay(store, receipt)
                proposal = self._resolve_bound_preview(store, command, effective)
                if proposal.proposal_digest != command.expected_proposal_digest or proposal.expected_profile_digest != command.expected_profile_digest:
                    raise MemoryStoreError("profile-preview-stale")
                if proposal.policy_digest != effective.policy_digest:
                    raise MemoryStoreError("profile-policy-drift")
                authority = self._authority(proposal, command, effective, "transition_profile_update")
                if proposal.status == "pending" and proposal.state_version != command.expected_state_version:
                    raise MemoryStoreError("profile-proposal-state-conflict")
            # Re-resolve before opening the mutation store. Read-only operations
            # above never insert snapshots or lazily apply migrations.
            _, current_policy = self.memory._effective_policy(_root(command))
            if current_policy.policy_digest != effective.policy_digest:
                raise MemoryStoreError("profile-policy-drift")
            store = MemoryStore.open_if_enabled(self.data_dir, current_policy)
            if store is None:
                raise MemoryStoreError("memory-disabled")
            with store:
                proposal = store.save_profile_update_proposal(proposal)
                transition_key = "mcp-decision:" + hashlib.sha256(command.idempotency_key.encode()).hexdigest()
                # The existing transition receipt rejects changed action/context
                # even if an interrupted attempt already approved this Proposal.
                approved = transition_profile_update(
                    store, proposal.proposal_id, action=command.action,
                    expected_state_version=command.expected_state_version,
                    idempotency_key=transition_key,
                    correlation_id=_digest({"context": asdict(command.context), "correlation_id": command.correlation_id}),
                )
                if command.action == "reject":
                    # Rejecting a new recommendation suppresses it until new
                    # evidence arrives. Rejecting a rollback must not change
                    # the original, already-applied Candidate.
                    rollback = ProfileMaterializer(store, self.data_dir, current_policy)._rollback_source(proposal.proposal_id)
                    candidate = store.load_workflow_candidate(proposal.candidate_id)
                    if rollback is None and candidate is not None and candidate.status == "proposed":
                        store.reject_workflow_candidate(candidate.candidate_id,
                            reason_code="user-rejected", rejected_at=_now(),
                            suppression_days=current_policy.policy.storage.rejected_suppression_days)
                    result = MemoryProfileResult("rejected", _view(approved))
                else:
                    materializer = ProfileMaterializer(store, self.data_dir, current_policy)
                    apply_key = "mcp-apply:" + hashlib.sha256(command.idempotency_key.encode()).hexdigest()
                    now = _now()
                    prior = store._require_open().execute("SELECT result_json FROM profile_materialization_receipts WHERE idempotency_key=?", (apply_key,)).fetchone()
                    if prior is not None:
                        now = decode_profile_revision(json.loads(prior[0])).created_at
                    else:
                        marker = materializer._load_marker(proposal.proposal_id)
                        if marker is not None:
                            revision = materializer.revisions.load(str(marker["revision_id"]))
                            if revision is not None:
                                now = revision.created_at
                    if prior is None and materializer._load_marker(proposal.proposal_id) is None and materializer._rollback_source(proposal.proposal_id) is None:
                        self._assert_candidate_evidence(store, store.load_workflow_candidate(proposal.candidate_id), current_policy)
                    revision = materializer.apply_approved(
                        proposal.proposal_id, authority=authority, expected_state_version=approved.state_version,
                        idempotency_key=apply_key, correlation_id=command.correlation_id, now=now,
                    )
                    final = store.load_profile_update_proposal(proposal.proposal_id)
                    result = MemoryProfileResult("applied", _view(final), revision.revision_id, revision.revision_digest)
                return self._save_receipt(store, command, "mcp-profile-transition", result)
        except CapabilityUnavailable:
            raise
        except (ValueError, RuntimeError, OSError, sqlite3.Error) as error:
            return MemoryProfileResult("blocked", None, reason_codes=_reasons((str(error),)))

    def rollback_profile_revision(self, command) -> MemoryProfileResult:
        try:
            _, effective = self.memory._effective_policy(_root(command))
            self._promotion_enabled(effective)
            store = MemoryStore.open_existing(self.data_dir, read_only=True)
            if store is None:
                raise MemoryStoreError("memory-store-unavailable")
            with store:
                receipt = self._read_receipt(store, command, "mcp-profile-rollback")
                if receipt is not None:
                    return self._replay(store, receipt)
                source = ProfileRevisionStore(self.data_dir, store).load(command.source_revision_id)
                if source is None or not self._in_scope(source, _root(command)):
                    raise MemoryStoreError("rollback-source-revision-unavailable")
                authority = self._authority(source, command, effective, "rollback_profile_revision")
            store = MemoryStore.open_if_enabled(self.data_dir, effective)
            if store is None:
                raise MemoryStoreError("memory-disabled")
            with store:
                # A rollback is a new review, not a revival of the source
                # Revision's old review window. Reuse only an existing pending
                # proposal with identical source/target/policy/CAS bindings.
                rows = store._require_open().execute(
                    "SELECT proposal_id FROM rollback_proposal_sources WHERE source_revision_id=?",
                    (command.source_revision_id,),
                ).fetchall()
                proposal = None
                for row in rows:
                    existing = store.load_profile_update_proposal(str(row[0]))
                    if (existing is not None and existing.status == "pending"
                        and existing.expected_profile_digest == command.expected_profile_digest
                        and existing.policy_digest == effective.policy_digest
                        and existing.expires_at > _now()):
                        proposal = existing
                        break
                if proposal is None:
                    proposal = ProfileMaterializer(store, self.data_dir, effective).create_rollback_proposal(
                        command.source_revision_id, authority=authority,
                        expected_profile_digest=command.expected_profile_digest, now=_now(),
                    )
                return self._save_receipt(store, command, "mcp-profile-rollback", MemoryProfileResult("pending", _view(proposal)))
        except CapabilityUnavailable:
            raise
        except (ValueError, RuntimeError, OSError, sqlite3.Error) as error:
            return MemoryProfileResult("blocked", None, reason_codes=_reasons((str(error),)))

    def purge_workflow_memory(self, command):
        # confirmed=True is enforced by the typed command before dispatch.
        try:
            result = self.memory.purge_memory(PurgeMemoryCommand(
                _context(command), command.scope, command.expected_summary_digest,
                command.include_managed_profiles, command.idempotency_key, command.correlation_id,
            ))
            return replace(result, reason_codes=_reasons(result.reason_codes))
        except (ValueError, RuntimeError, OSError, sqlite3.Error) as error:
            return PurgeMemoryResult("blocked", command.scope, 0, 0, 0, command.expected_summary_digest, command.expected_summary_digest, False, _reasons((str(error),)))
