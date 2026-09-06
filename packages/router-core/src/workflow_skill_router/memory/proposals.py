from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import re
from typing import Mapping

from workflow_skill_router.profiles.contract import RoutingPreferenceProfile, decode_routing_profile
from workflow_skill_router.profiles.resolver import lint_profile
from workflow_skill_router.schemas.artifacts import canonical_json

from .backtest import BacktestSummary, backtest_profile_update
from .candidates import WorkflowCandidate
from .policy_resolver import EffectiveMemoryPolicy
from .profile_diff import SemanticProfileDiff, build_profile_document, diff_profiles, profile_document


SCHEMA_ID = "workflow-skill-router/profile-update-proposal"
SCHEMA_VERSION = "1.0.0"
ARTIFACT_KIND = "profile-update-proposal"
_STATUSES = frozenset({"pending", "approved", "rejected", "stale", "expired", "applied", "failed"})
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_PROPOSAL_ID = re.compile(r"^proposal:[0-9a-f]{32}$")


class ProfileProposalError(ValueError):
    """Raised when a Profile proposal is invalid or its transition is unsafe."""


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _parse_time(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ProfileProposalError("invalid-proposal-time") from error


def _time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class ProfileUpdateProposal:
    proposal_id: str
    proposal_digest: str
    candidate_id: str
    candidate_digest: str
    status: str
    state_version: int
    target_profile_class: str
    expected_profile_digest: str
    proposed_profile_digest: str
    proposed_profile: dict[str, object]
    semantic_diff: dict[str, object]
    semantic_diff_digest: str
    backtest: dict[str, object]
    backtest_digest: str
    policy_digest: str
    workspace_identity_digest: str | None
    created_at: str
    expires_at: str

    def immutable_document(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_digest": self.candidate_digest,
            "target_profile_class": self.target_profile_class,
            "expected_profile_digest": self.expected_profile_digest,
            "proposed_profile_digest": self.proposed_profile_digest,
            "proposed_profile": self.proposed_profile,
            "semantic_diff": self.semantic_diff,
            "semantic_diff_digest": self.semantic_diff_digest,
            "backtest": self.backtest,
            "backtest_digest": self.backtest_digest,
            "policy_digest": self.policy_digest,
            "workspace_identity_digest": self.workspace_identity_digest,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": SCHEMA_ID,
            "schema_version": SCHEMA_VERSION,
            "artifact_kind": ARTIFACT_KIND,
            "proposal_id": self.proposal_id,
            "proposal_digest": self.proposal_digest,
            "candidate_id": self.candidate_id,
            "candidate_digest": self.candidate_digest,
            "status": self.status,
            "state_version": self.state_version,
            "target_profile_class": self.target_profile_class,
            "expected_profile_digest": self.expected_profile_digest,
            "proposed_profile_digest": self.proposed_profile_digest,
            "proposed_profile": self.proposed_profile,
            "semantic_diff": self.semantic_diff,
            "semantic_diff_digest": self.semantic_diff_digest,
            "backtest": self.backtest,
            "backtest_digest": self.backtest_digest,
            "policy_digest": self.policy_digest,
            "workspace_identity_digest": self.workspace_identity_digest,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())


def _proposal_identity(immutable: Mapping[str, object]) -> tuple[str, str]:
    digest = _digest(dict(immutable))
    return "proposal:" + digest.removeprefix("sha256:")[:32], digest


def decode_profile_update_proposal(value: object) -> ProfileUpdateProposal:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ProfileProposalError("invalid-proposal-document")
    expected = {
        "schema_id", "schema_version", "artifact_kind", "proposal_id", "proposal_digest",
        "candidate_id", "candidate_digest", "status", "state_version", "target_profile_class",
        "expected_profile_digest", "proposed_profile_digest", "proposed_profile", "semantic_diff",
        "semantic_diff_digest", "backtest", "backtest_digest", "policy_digest",
        "workspace_identity_digest", "created_at", "expires_at",
    }
    if set(value) != expected:
        raise ProfileProposalError("proposal-fields-mismatch")
    if value["schema_id"] != SCHEMA_ID or value["schema_version"] != SCHEMA_VERSION or value["artifact_kind"] != ARTIFACT_KIND:
        raise ProfileProposalError("proposal-contract-unsupported")
    status = value["status"]
    version = value["state_version"]
    if not isinstance(status, str) or status not in _STATUSES:
        raise ProfileProposalError("invalid-proposal-status")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ProfileProposalError("invalid-proposal-state-version")
    proposed = value["proposed_profile"]
    diff = value["semantic_diff"]
    backtest = value["backtest"]
    if not isinstance(proposed, Mapping) or not isinstance(diff, Mapping) or not isinstance(backtest, Mapping):
        raise ProfileProposalError("invalid-proposal-bound-document")
    decoded_profile = decode_routing_profile(proposed)
    proposed_doc = profile_document(decoded_profile) or {}
    proposed_digest = _digest(proposed_doc)
    if value["proposed_profile_digest"] != proposed_digest:
        raise ProfileProposalError("proposed-profile-digest-mismatch")
    if value["semantic_diff_digest"] != diff.get("semantic_diff_digest"):
        raise ProfileProposalError("semantic-diff-digest-mismatch")
    if value["backtest_digest"] != backtest.get("backtest_digest"):
        raise ProfileProposalError("backtest-digest-mismatch")
    proposal = ProfileUpdateProposal(
        proposal_id=str(value["proposal_id"]), proposal_digest=str(value["proposal_digest"]),
        candidate_id=str(value["candidate_id"]), candidate_digest=str(value["candidate_digest"]),
        status=status, state_version=version, target_profile_class=str(value["target_profile_class"]),
        expected_profile_digest=str(value["expected_profile_digest"]), proposed_profile_digest=proposed_digest,
        proposed_profile=proposed_doc, semantic_diff=dict(diff), semantic_diff_digest=str(value["semantic_diff_digest"]),
        backtest=dict(backtest), backtest_digest=str(value["backtest_digest"]), policy_digest=str(value["policy_digest"]),
        workspace_identity_digest=(None if value["workspace_identity_digest"] is None else str(value["workspace_identity_digest"])),
        created_at=str(value["created_at"]), expires_at=str(value["expires_at"]),
    )
    if _PROPOSAL_ID.fullmatch(proposal.proposal_id) is None:
        raise ProfileProposalError("invalid-proposal-id")
    for item in (
        proposal.proposal_digest, proposal.candidate_digest, proposal.proposed_profile_digest,
        proposal.semantic_diff_digest, proposal.backtest_digest, proposal.policy_digest,
    ):
        if _DIGEST.fullmatch(item) is None:
            raise ProfileProposalError("invalid-proposal-digest")
    identity, digest = _proposal_identity(proposal.immutable_document())
    if proposal.proposal_id != identity or proposal.proposal_digest != digest:
        raise ProfileProposalError("proposal-digest-mismatch")
    _parse_time(proposal.created_at)
    _parse_time(proposal.expires_at)
    return proposal


def create_profile_update_proposal_from_document(
    store,
    candidate: WorkflowCandidate,
    *,
    current_profile: RoutingPreferenceProfile | None,
    proposed_profile_document: Mapping[str, object],
    target_profile_class: str,
    workspace_identity_digest: str | None,
    policy: EffectiveMemoryPolicy,
    now: str,
    ttl_days: int = 7,
    manual_profiles: tuple[RoutingPreferenceProfile, ...] | None = None,
    automatic: bool = False,
) -> ProfileUpdateProposal:
    if not isinstance(candidate, WorkflowCandidate):
        raise TypeError("candidate must be WorkflowCandidate")
    if candidate.status != "proposed":
        raise ProfileProposalError("candidate-not-proposed")
    if target_profile_class not in policy.allowed_targets:
        raise ProfileProposalError("proposal-target-not-allowed")
    if policy.profile_promotion == "disabled":
        raise ProfileProposalError("profile-promotion-disabled")
    expected_scope = "personal" if target_profile_class in {"managed-personal", "user-personal"} else "workspace"
    proposed = decode_routing_profile(proposed_profile_document, expected_scope=expected_scope)
    lint_errors = tuple(item for item in lint_profile(proposed) if item.severity == "error")
    if lint_errors:
        raise ProfileProposalError("profile-lint-failed")
    proposed_doc = profile_document(proposed) or {}
    diff: SemanticProfileDiff = diff_profiles(current_profile, proposed_doc)
    observations = tuple(store.list_route_observations())
    current_profiles = () if current_profile is None else (current_profile,)
    backtest: BacktestSummary = backtest_profile_update(
        current_profiles,
        proposed,
        observations,
        candidate,
        manual_profiles=manual_profiles,
    )
    if automatic and target_profile_class not in {
        "managed-personal", "managed-workspace-local"
    }:
        raise ProfileProposalError("automatic-user-profile-write-forbidden")
    if automatic and backtest.manual_precedence:
        raise ProfileProposalError("candidate-conflict")
    if not backtest.acceptable:
        raise ProfileProposalError("profile-backtest-failed")
    created = _parse_time(now)
    immutable: dict[str, object] = {
        "candidate_id": candidate.candidate_id,
        "candidate_digest": candidate.candidate_digest,
        "target_profile_class": target_profile_class,
        "expected_profile_digest": "missing" if current_profile is None else current_profile.profile_digest,
        "proposed_profile_digest": _digest(proposed_doc),
        "proposed_profile": proposed_doc,
        "semantic_diff": diff.to_dict(),
        "semantic_diff_digest": diff.semantic_diff_digest,
        "backtest": backtest.to_dict(),
        "backtest_digest": backtest.backtest_digest,
        "policy_digest": policy.policy_digest,
        "workspace_identity_digest": workspace_identity_digest,
        "created_at": _time(created),
        "expires_at": _time(created + timedelta(days=ttl_days)),
    }
    proposal_id, proposal_digest = _proposal_identity(immutable)
    proposal = ProfileUpdateProposal(
        proposal_id=proposal_id, proposal_digest=proposal_digest,
        status="pending", state_version=1, **immutable,  # type: ignore[arg-type]
    )
    return store.save_profile_update_proposal(proposal)


def create_profile_update_proposal(
    store,
    candidate: WorkflowCandidate,
    *,
    current_profile: RoutingPreferenceProfile | None,
    policy: EffectiveMemoryPolicy,
    now: str,
    ttl_days: int = 7,
    manual_profiles: tuple[RoutingPreferenceProfile, ...] | None = None,
    automatic: bool = False,
) -> ProfileUpdateProposal:
    proposed_doc = build_profile_document(candidate, current_profile)
    return create_profile_update_proposal_from_document(
        store,
        candidate,
        current_profile=current_profile,
        proposed_profile_document=proposed_doc,
        target_profile_class=candidate.target_profile_class,
        workspace_identity_digest=candidate.workspace_identity_digest,
        policy=policy,
        now=now,
        ttl_days=ttl_days,
        manual_profiles=manual_profiles,
        automatic=automatic,
    )


def transition_profile_update(
    store,
    proposal_id: str,
    *,
    action: str,
    expected_state_version: int,
    idempotency_key: str,
    correlation_id: str,
    now: str | None = None,
) -> ProfileUpdateProposal:
    if action not in {"approve", "reject"}:
        raise ProfileProposalError("unsupported-proposal-action")
    current = store.load_profile_update_proposal(proposal_id)
    if current is None:
        raise ProfileProposalError("profile-proposal-not-found")
    instant = _parse_time(now) if now is not None else datetime.now(timezone.utc)
    if current.status == "pending" and instant >= _parse_time(current.expires_at):
        store.set_profile_update_proposal_status(proposal_id, "expired", expected_state_version=current.state_version)
        raise ProfileProposalError("profile-proposal-expired")
    target = "approved" if action == "approve" else "rejected"
    try:
        return store.transition_profile_update_proposal(
            proposal_id,
            target_status=target,
            expected_state_version=expected_state_version,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
    except Exception as error:
        from .store import MemoryCommandConflict, MemoryStoreError
        if isinstance(error, MemoryCommandConflict):
            raise ProfileProposalError("idempotency-conflict") from error
        if isinstance(error, MemoryStoreError):
            raise ProfileProposalError(str(error)) from error
        raise


__all__ = [
    "ProfileProposalError", "ProfileUpdateProposal", "create_profile_update_proposal",
    "create_profile_update_proposal_from_document",
    "decode_profile_update_proposal", "transition_profile_update",
]
