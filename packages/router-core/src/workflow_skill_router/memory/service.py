from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re

from workflow_skill_router.schemas.artifacts import canonical_json
from workflow_skill_router.profiles.atomic_io import ProfileIOError, secure_read_json
from workflow_skill_router.profiles.contract import (
    RoutingPreferenceProfile,
    RoutingProfileContractError,
    decode_routing_profile,
)
from workflow_skill_router.profiles.layers import ProfileSourceClass
from workflow_skill_router.profiles.storage import RoutingProfileRepository

from .candidates import (
    CandidateEngine,
    WorkflowCandidate,
    automatic_promotion_reason_codes,
)
from .models import (
    AutomaticPromotionNotification,
    AutomaticPromotionResult,
    MemoryMode,
    MemoryScope,
)
from .analytics import (
    HistorySummary,
    HistorySummaryQuery,
    PurgeMemoryCommand,
    PurgeMemoryResult,
    RetentionResult,
)
from .feedback import (
    RecordRouteFeedbackCommand,
    RecordRouteFeedbackResult,
    RouteFeedback,
    RouteFeedbackError,
)
from .observations import (
    MatcherSeed,
    build_route_observation,
    evaluate_observation_eligibility,
)
from .policy_io import MemoryPolicyRepository
from .proposals import (
    ProfileProposalError,
    ProfileUpdateProposal,
    create_profile_update_proposal,
    transition_profile_update as transition_profile_update_proposal,
)
from .materializer import ProfileMaterializationError, ProfileMaterializer
from .managed_profiles import (
    ManagedProfilePathError,
    managed_personal_profile_path,
    managed_workspace_profile_path,
    verify_workspace_root,
)
from .backtest import backtest_profile_update
from .profile_diff import build_profile_document, diff_profiles
from .revisions import ProfileRevision, ProfileRevisionStore, ProfileWriteAuthority
from .policy_resolver import resolve_effective_policy
from .store import MemoryCommandConflict, MemoryStore, MemoryStoreError
from .workflow_reader import (
    CompletedWorkflowReader,
    MemoryRequestContext,
    WorkflowReadError,
)


_SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
_TARGETS = (
    "managed-personal",
    "managed-workspace-local",
    "user-personal",
    "workspace-file",
)
_RISKS = ("r0", "r1", "r2", "r3")
_SIDE_EFFECTS = ("none", "known-success", "known-failure", "unknown")
_ONE_SHOT = ("none", "remember-once", "no-memory")
_PROMOTION_REASON = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_AUTOMATIC_PROMOTION_BATCH_LIMIT = 16
_TARGET_LAYER_RANK = {"managed-workspace-local": 1, "managed-personal": 3}


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _validated_time(value: str | None) -> str:
    instant = _utc_now() if value is None else value
    if not isinstance(instant, str) or not instant.endswith("Z"):
        raise ValueError("invalid-automatic-promotion-time")
    try:
        parsed = datetime.fromisoformat(instant[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError("invalid-automatic-promotion-time") from error
    if parsed.tzinfo is None:
        raise ValueError("invalid-automatic-promotion-time")
    return instant


def _promotion_reason(error: BaseException, fallback: str) -> str:
    value = str(error)
    return value if _PROMOTION_REASON.fullmatch(value) is not None else fallback


def _promotion_token(idempotency_key: str, candidate_id: str, purpose: str) -> str:
    return hashlib.sha256(
        canonical_json({
            "idempotency_key": idempotency_key,
            "candidate_id": candidate_id,
            "purpose": purpose,
        }).encode("utf-8")
    ).hexdigest()[:32]


@dataclass(frozen=True, slots=True)
class RememberWorkflowCommand:
    context: MemoryRequestContext
    workflow_run_id: str
    workspace_root: Path | None
    matcher_seed: MatcherSeed | None
    target_profile_class: str
    risk_class: str
    side_effect_outcome: str
    one_shot: str
    idempotency_key: str
    correlation_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.context, MemoryRequestContext):
            raise TypeError("context must be MemoryRequestContext")
        if not isinstance(self.workflow_run_id, str) or not self.workflow_run_id or len(self.workflow_run_id) > 160:
            raise ValueError("invalid-workflow-run-id")
        if self.workspace_root is not None:
            object.__setattr__(self, "workspace_root", Path(self.workspace_root))
        if self.matcher_seed is not None and not isinstance(self.matcher_seed, MatcherSeed):
            raise TypeError("matcher_seed must be MatcherSeed or None")
        if self.target_profile_class not in _TARGETS:
            raise ValueError("invalid-memory-target")
        if self.risk_class not in _RISKS:
            raise ValueError("invalid-memory-risk")
        if self.side_effect_outcome not in _SIDE_EFFECTS:
            raise ValueError("invalid-side-effect-outcome")
        if self.one_shot not in _ONE_SHOT:
            raise ValueError("invalid-one-shot")
        for name, value in (("idempotency_key", self.idempotency_key), ("correlation_id", self.correlation_id)):
            if not isinstance(value, str) or _SAFE_KEY.fullmatch(value) is None:
                raise ValueError(f"invalid-{name}")

    def digest_document(self, workspace_digest: str | None) -> dict[str, object]:
        return {
            "context": {
                "session_id": self.context.session_id,
                "actor": self.context.actor,
                "runtime_policy_snapshot_id": self.context.runtime_policy_snapshot_id,
            },
            "workflow_run_id": self.workflow_run_id,
            "workspace_identity_digest": workspace_digest,
            "matcher_seed": None if self.matcher_seed is None else self.matcher_seed.to_dict(),
            "target_profile_class": self.target_profile_class,
            "risk_class": self.risk_class,
            "side_effect_outcome": self.side_effect_outcome,
            "one_shot": self.one_shot,
            "correlation_id": self.correlation_id,
        }


@dataclass(frozen=True, slots=True)
class RememberWorkflowResult:
    status: str
    observation_id: str | None
    observation_digest: str | None
    route_signature_digest: str | None
    policy_digest: str | None
    target_profile_class: str
    reason_codes: tuple[str, ...]
    replayed: bool
    candidate_id: str | None = None
    authority_mode: str = "router-local"

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "observation_id": self.observation_id,
            "observation_digest": self.observation_digest,
            "route_signature_digest": self.route_signature_digest,
            "policy_digest": self.policy_digest,
            "target_profile_class": self.target_profile_class,
            "reason_codes": list(self.reason_codes),
            "replayed": self.replayed,
            "candidate_id": self.candidate_id,
            "authority_mode": self.authority_mode,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object], *, replayed: bool | None = None) -> "RememberWorkflowResult":
        return cls(
            status=str(value["status"]),
            observation_id=None if value.get("observation_id") is None else str(value["observation_id"]),
            observation_digest=None if value.get("observation_digest") is None else str(value["observation_digest"]),
            route_signature_digest=None if value.get("route_signature_digest") is None else str(value["route_signature_digest"]),
            policy_digest=None if value.get("policy_digest") is None else str(value["policy_digest"]),
            target_profile_class=str(value["target_profile_class"]),
            reason_codes=tuple(str(item) for item in value.get("reason_codes", [])),
            replayed=bool(value.get("replayed", False)) if replayed is None else replayed,
            candidate_id=None if value.get("candidate_id") is None else str(value["candidate_id"]),
            authority_mode=str(value.get("authority_mode", "router-local")),
        )


class WorkflowMemoryService:
    """Local control plane for explicit, policy-bound Workflow observations."""

    def __init__(self, operational_database: Path, *, data_dir: Path | None = None) -> None:
        self._operational_database = Path(operational_database)
        self._data_dir = self._operational_database.parent if data_dir is None else Path(data_dir)

    def remember_workflow(self, command: RememberWorkflowCommand) -> RememberWorkflowResult:
        if not isinstance(command, RememberWorkflowCommand):
            raise TypeError("command must be RememberWorkflowCommand")
        if command.one_shot == "no-memory":
            return self._not_recorded(command, "not-recorded", ("explicit-no-memory",), None)

        repository = MemoryPolicyRepository(self._data_dir)
        personal = repository.inspect_personal()
        workspace = None if command.workspace_root is None else repository.inspect_workspace(command.workspace_root)
        effective = resolve_effective_policy(personal=personal, workspace=workspace)
        if not effective.capture_enabled:
            return self._not_recorded(command, "memory-disabled", effective.reason_codes or ("memory-disabled",), effective.policy_digest)

        try:
            workflow = CompletedWorkflowReader(self._operational_database).read(
                command.context, command.workflow_run_id
            )
        except WorkflowReadError as error:
            return self._not_recorded(command, "not-recorded", (str(error),), effective.policy_digest)

        matcher = command.matcher_seed or self._persisted_matcher(workflow)
        eligibility = evaluate_observation_eligibility(
            workflow,
            effective,
            matcher,
            target_profile_class=command.target_profile_class,
            risk_class=command.risk_class,
            side_effect_outcome=command.side_effect_outcome,
            one_shot=command.one_shot,
        )
        if not eligibility.eligible:
            return self._not_recorded(
                command, "not-recorded", eligibility.reason_codes, effective.policy_digest
            )
        assert matcher is not None

        store = MemoryStore.open_if_enabled(self._data_dir, effective)
        if store is None:
            return self._not_recorded(command, "memory-disabled", ("memory-disabled",), effective.policy_digest)
        with store:
            observation = build_route_observation(
                workflow,
                matcher,
                store.current_policy_snapshot,
                target_profile_class=command.target_profile_class,
                risk_class=command.risk_class,
                side_effect_outcome=command.side_effect_outcome,
                observed_at=_utc_now(),
            )
            result = RememberWorkflowResult(
                status="recorded",
                observation_id=observation.observation_id,
                observation_digest=observation.observation_digest,
                route_signature_digest=observation.route_signature_digest,
                policy_digest=effective.policy_digest,
                target_profile_class=command.target_profile_class,
                reason_codes=(),
                replayed=False,
            )
            command_digest = _digest({
                "command": command.digest_document(workflow.workspace_identity_digest),
                "effective_policy_digest": effective.policy_digest,
                "policy_snapshot_id": store.current_policy_snapshot.snapshot_id,
            })
            stored, replayed = store.record_route_observation(
                observation_document=observation.to_dict(),
                result_document=result.to_dict(),
                idempotency_key=command.idempotency_key,
                command_digest=command_digest,
            )
            return RememberWorkflowResult.from_dict(stored, replayed=replayed)



    def _effective_policy(self, workspace_root: Path | None = None):
        repository = MemoryPolicyRepository(self._data_dir)
        personal = repository.inspect_personal()
        workspace = None if workspace_root is None else repository.inspect_workspace(workspace_root)
        return repository, resolve_effective_policy(personal=personal, workspace=workspace)

    def open_store_for_current_policy(
        self,
        workspace_root: Path | None = None,
    ) -> MemoryStore | None:
        repository, effective = self._effective_policy(workspace_root)
        if not effective.capture_enabled:
            return None
        return MemoryStore.open_if_enabled(self._data_dir, effective)

    def record_route_feedback(
        self,
        command: RecordRouteFeedbackCommand,
    ) -> RecordRouteFeedbackResult:
        if not isinstance(command, RecordRouteFeedbackCommand):
            raise TypeError("command must be RecordRouteFeedbackCommand")
        repository, effective = self._effective_policy(command.workspace_root)
        if not effective.capture_enabled or effective.policy.features.route_feedback.mode == "disabled":
            return RecordRouteFeedbackResult(
                status="memory-disabled",
                feedback_id=None,
                feedback_digest=None,
                observation_id=command.observation_id,
                policy_digest=effective.policy_digest,
                reason_codes=effective.reason_codes or ("memory-disabled",),
                replayed=False,
            )
        if (
            command.reason_code is not None
            and not effective.policy.features.route_feedback.allow_standard_reason_codes
        ):
            raise RouteFeedbackError("reason-code-not-authorized")
        if command.free_text is not None and not (
            effective.policy.privacy.free_text_feedback == "explicit-opt-in"
            and effective.policy.features.route_feedback.allow_free_text
        ):
            raise RouteFeedbackError("free-text-not-authorized")
        store = MemoryStore.open_if_enabled(self._data_dir, effective)
        if store is None:
            return RecordRouteFeedbackResult(
                status="memory-disabled",
                feedback_id=None,
                feedback_digest=None,
                observation_id=command.observation_id,
                policy_digest=effective.policy_digest,
                reason_codes=("memory-disabled",),
                replayed=False,
            )
        with store:
            observation = store.load_route_observation(command.observation_id)
            if observation is None:
                raise RouteFeedbackError("feedback-observation-not-found")
            try:
                workflow = CompletedWorkflowReader(self._operational_database).read(
                    command.context, command.workflow_run_id
                )
            except WorkflowReadError as error:
                raise RouteFeedbackError("feedback-workflow-context-mismatch") from error
            if workflow.workflow_run_digest != observation.workflow_run_digest:
                raise RouteFeedbackError("feedback-workflow-context-mismatch")
            if (
                command.feedback_type == "corrected"
                and command.original_route_digest != observation.route_signature_digest
            ):
                raise RouteFeedbackError("feedback-original-route-mismatch")
            feedback = RouteFeedback.create(
                observation=observation,
                policy_snapshot=store.current_policy_snapshot,
                context=command.context,
                feedback_type=command.feedback_type,
                reason_code=command.reason_code,
                correction_dimensions=command.correction_dimensions,
                original_route_digest=command.original_route_digest,
                corrected_route_digest=command.corrected_route_digest,
                free_text=command.free_text,
                recorded_at=_utc_now(),
            )
            result = RecordRouteFeedbackResult(
                status="recorded",
                feedback_id=feedback.feedback_id,
                feedback_digest=feedback.feedback_digest,
                observation_id=feedback.observation_id,
                policy_digest=effective.policy_digest,
                reason_codes=(),
                replayed=False,
            )
            command_digest = _digest({
                "command": command.digest_document(),
                "effective_policy_digest": effective.policy_digest,
                "policy_snapshot_id": store.current_policy_snapshot.snapshot_id,
                "observation_digest": observation.observation_digest,
            })
            stored, replayed = store.record_route_feedback(
                feedback_document=feedback.to_dict(),
                result_document=result.to_dict(),
                idempotency_key=command.idempotency_key,
                command_digest=command_digest,
            )
            return RecordRouteFeedbackResult.from_dict(stored, replayed=replayed)

    def rebuild_candidates(
        self,
        scope: MemoryScope,
        *,
        workspace_root: Path | None = None,
        now: datetime | None = None,
    ) -> tuple[WorkflowCandidate, ...]:
        repository, effective = self._effective_policy(workspace_root)
        if not effective.candidate_generation_enabled or not repository.memory_store_exists():
            return ()
        store = MemoryStore.open_if_enabled(self._data_dir, effective)
        if store is None:
            return ()
        instant = datetime.now(timezone.utc) if now is None else now
        with store:
            return CandidateEngine(store, effective).rebuild(scope, instant)

    def list_workflow_candidates(
        self,
        *,
        workspace_root: Path | None = None,
        status: str | None = None,
    ) -> tuple[WorkflowCandidate, ...]:
        repository, effective = self._effective_policy(workspace_root)
        if not repository.memory_store_exists():
            return ()
        store = (MemoryStore.open_if_enabled(self._data_dir, effective) if effective.capture_enabled else MemoryStore.open_existing(self._data_dir))
        if store is None:
            return ()
        with store:
            return store.list_workflow_candidates(status)

    def reject_workflow_candidate(
        self,
        candidate_id: str,
        *,
        workspace_root: Path | None = None,
        reason_code: str,
        rejected_at: str | None = None,
    ) -> WorkflowCandidate:
        repository, effective = self._effective_policy(workspace_root)
        if not repository.memory_store_exists():
            raise MemoryStoreError("memory-store-unavailable")
        store = (MemoryStore.open_if_enabled(self._data_dir, effective) if effective.capture_enabled else MemoryStore.open_existing(self._data_dir))
        if store is None:
            raise MemoryStoreError("memory-store-unavailable")
        with store:
            return store.reject_workflow_candidate(
                candidate_id,
                reason_code=reason_code,
                rejected_at=_utc_now() if rejected_at is None else rejected_at,
                suppression_days=effective.policy.storage.rejected_suppression_days,
            )

    def _load_current_managed_profile(
        self, candidate: WorkflowCandidate
    ) -> RoutingPreferenceProfile | None:
        if candidate.target_profile_class == "managed-personal":
            path = managed_personal_profile_path(self._data_dir)
            expected_scope = "personal"
            expected_profile_id = "personal:adaptive-memory"
        elif candidate.target_profile_class == "managed-workspace-local":
            if candidate.workspace_identity_digest is None:
                raise MemoryStoreError("workspace-root-unverified")
            path = managed_workspace_profile_path(
                self._data_dir, candidate.workspace_identity_digest
            )
            expected_scope = "workspace"
            expected_profile_id = "workspace:adaptive-memory"
        else:
            raise MemoryStoreError("automatic-user-profile-write-forbidden")
        try:
            document = secure_read_json(path, self._data_dir)
            if document is None:
                return None
            profile = decode_routing_profile(document, expected_scope=expected_scope)
        except ProfileIOError as error:
            if str(error) == "profile-directory-missing":
                return None
            raise MemoryStoreError("managed-profile-invalid") from error
        except (RoutingProfileContractError, ValueError) as error:
            raise MemoryStoreError("managed-profile-invalid") from error
        if profile.profile_id != expected_profile_id:
            raise MemoryStoreError("managed-profile-invalid")
        return profile

    def _manual_profiles_for_candidate(
        self,
        candidate: WorkflowCandidate,
        workspace_root: Path | None,
    ) -> tuple[RoutingPreferenceProfile, ...]:
        if candidate.target_profile_class not in _TARGET_LAYER_RANK:
            raise MemoryStoreError("automatic-user-profile-write-forbidden")
        try:
            loaded = RoutingProfileRepository(self._data_dir).load_ranked_layers(
                workspace_root=workspace_root
            )
        except (RoutingProfileContractError, OSError, ValueError) as error:
            raise MemoryStoreError("manual-profile-invalid") from error
        if candidate.scope is MemoryScope.WORKSPACE:
            if (
                workspace_root is None
                or loaded.workspace_identity_digest is None
                or loaded.workspace_identity_digest
                != candidate.workspace_identity_digest
            ):
                raise MemoryStoreError("workspace-root-unverified")
        target_rank = _TARGET_LAYER_RANK[candidate.target_profile_class]
        manual_classes = {
            ProfileSourceClass.USER_WORKSPACE,
            ProfileSourceClass.USER_PERSONAL,
        }
        return tuple(
            layer.profile
            for layer in loaded.layers
            if layer.source_class in manual_classes and layer.rank < target_rank
        )

    @staticmethod
    def _automatic_notification(
        candidate: WorkflowCandidate,
        policy_digest: str,
        *,
        status: str,
        reason_codes: tuple[str, ...],
        proposal: ProfileUpdateProposal | None = None,
        revision: ProfileRevision | None = None,
    ) -> AutomaticPromotionNotification:
        return AutomaticPromotionNotification(
            status=status,
            candidate_id=candidate.candidate_id,
            candidate_digest=candidate.candidate_digest,
            policy_digest=policy_digest,
            target_profile_class=candidate.target_profile_class,
            proposal_id=None if proposal is None else proposal.proposal_id,
            proposal_digest=None if proposal is None else proposal.proposal_digest,
            revision_id=None if revision is None else revision.revision_id,
            revision_digest=None if revision is None else revision.revision_digest,
            new_profile_digest=(
                None if revision is None else revision.new_profile_digest
            ),
            reason_codes=reason_codes,
        )

    def promote_eligible_candidates(
        self,
        scope: MemoryScope,
        *,
        workspace_root: Path | None = None,
        actor_id: str,
        session_id: str,
        idempotency_key: str,
        correlation_id: str,
        now: str | None = None,
    ) -> AutomaticPromotionResult:
        """Promote currently proposed high-confidence Candidates locally.

        This method is an explicit local operation. It does not claim or start a
        background scheduler.
        """

        if not isinstance(scope, MemoryScope):
            raise TypeError("scope must be MemoryScope")
        for name, value in (
            ("idempotency_key", idempotency_key),
            ("correlation_id", correlation_id),
        ):
            if not isinstance(value, str) or _SAFE_KEY.fullmatch(value) is None:
                raise ValueError(f"invalid-{name}")
        authority = ProfileWriteAuthority.router_local_managed(actor_id, session_id)
        instant = _validated_time(now)
        workspace = None if workspace_root is None else Path(workspace_root)
        repository, effective = self._effective_policy(workspace)
        if not effective.capture_enabled or not repository.memory_store_exists():
            return AutomaticPromotionResult(
                status="memory-disabled",
                scope=scope,
                promoted_count=0,
                suppressed_count=0,
                skipped_count=0,
                notifications=(),
                reason_codes=effective.reason_codes or ("memory-disabled",),
            )
        if (
            effective.mode is not MemoryMode.AUTOMATIC
            or effective.profile_promotion != "automatic-managed"
        ):
            return AutomaticPromotionResult(
                status="not-automatic",
                scope=scope,
                promoted_count=0,
                suppressed_count=0,
                skipped_count=0,
                notifications=(),
                reason_codes=("memory-mode-not-automatic",),
            )
        if not effective.policy.notifications.show_auto_promotion:
            raise MemoryStoreError("automatic-notification-required")

        workspace_digest = (
            None
            if workspace is None
            else verify_workspace_root(workspace).digest
        )
        command_digest = _digest({
            "operation": "promote-eligible",
            "scope": scope.value,
            "workspace_identity_digest": workspace_digest,
            "policy_digest": effective.policy_digest,
            "actor_id": authority.actor_id,
            "session_id": authority.session_id,
            "correlation_id": correlation_id,
        })
        store = MemoryStore.open_if_enabled(self._data_dir, effective)
        if store is None:
            raise MemoryStoreError("memory-store-unavailable")
        with store:
            existing = store.load_admin_result(
                idempotency_key=idempotency_key,
                command_kind="promote-eligible",
                command_digest=command_digest,
            )
            if existing is not None:
                return AutomaticPromotionResult.from_dict(existing, replayed=True)

            proposed = tuple(
                item
                for item in store.list_workflow_candidates("proposed")
                if item.scope is scope
            )
            truncated = len(proposed) > _AUTOMATIC_PROMOTION_BATCH_LIMIT
            candidates = proposed[:_AUTOMATIC_PROMOTION_BATCH_LIMIT]
            observations = tuple(store.list_route_observations())
            notifications: list[AutomaticPromotionNotification] = []

            for candidate in candidates:
                gate_reasons = automatic_promotion_reason_codes(
                    candidate, effective
                )
                if gate_reasons:
                    notifications.append(self._automatic_notification(
                        candidate,
                        effective.policy_digest,
                        status="blocked",
                        reason_codes=gate_reasons,
                    ))
                    continue

                proposal: ProfileUpdateProposal | None = None
                try:
                    current_profile = self._load_current_managed_profile(candidate)
                    manual_profiles = self._manual_profiles_for_candidate(
                        candidate, workspace
                    )
                    proposed_document = build_profile_document(
                        candidate, current_profile
                    )
                    proposed_profile = decode_routing_profile(proposed_document)
                    current_profiles = (
                        () if current_profile is None else (current_profile,)
                    )
                    preflight = backtest_profile_update(
                        current_profiles,
                        proposed_profile,
                        observations,
                        candidate,
                        manual_profiles=manual_profiles,
                    )
                    if preflight.manual_precedence or preflight.equal_rank_conflicts:
                        store.suppress_workflow_candidate(
                            candidate.candidate_id,
                            reason_code="candidate-conflict",
                            suppressed_at=instant,
                            suppression_days=(
                                effective.policy.storage.rejected_suppression_days
                            ),
                        )
                        notifications.append(self._automatic_notification(
                            candidate,
                            effective.policy_digest,
                            status="suppressed",
                            reason_codes=(
                                "candidate-conflict",
                                "candidate-suppressed",
                            ),
                        ))
                        continue
                    if not preflight.acceptable:
                        notifications.append(self._automatic_notification(
                            candidate,
                            effective.policy_digest,
                            status="blocked",
                            reason_codes=("profile-backtest-failed",),
                        ))
                        continue

                    proposal = create_profile_update_proposal(
                        store,
                        candidate,
                        current_profile=current_profile,
                        policy=effective,
                        now=instant,
                        manual_profiles=manual_profiles,
                        automatic=True,
                    )
                    token = _promotion_token(
                        idempotency_key, candidate.candidate_id, "approve"
                    )
                    approved = transition_profile_update_proposal(
                        store,
                        proposal.proposal_id,
                        action="approve",
                        expected_state_version=proposal.state_version,
                        idempotency_key=f"auto-approve:{token}",
                        correlation_id=correlation_id,
                        now=instant,
                    )
                    fresh_manual_profiles = self._manual_profiles_for_candidate(
                        candidate, workspace
                    )
                    apply_token = _promotion_token(
                        idempotency_key, candidate.candidate_id, "apply"
                    )
                    revision = ProfileMaterializer(
                        store, self._data_dir, effective
                    ).apply_approved(
                        approved.proposal_id,
                        authority=authority,
                        expected_state_version=approved.state_version,
                        idempotency_key=f"auto-apply:{apply_token}",
                        correlation_id=correlation_id,
                        now=instant,
                        manual_profiles=fresh_manual_profiles,
                        candidate_final_status="auto-promoted",
                    )
                    notifications.append(self._automatic_notification(
                        candidate,
                        effective.policy_digest,
                        status="promoted",
                        reason_codes=("automatic-promotion-applied",),
                        proposal=approved,
                        revision=revision,
                    ))
                except ProfileMaterializationError as error:
                    reason = _promotion_reason(
                        error, "profile-materialization-failed"
                    )
                    if reason == "candidate-conflict":
                        current_candidate = store.load_workflow_candidate(
                            candidate.candidate_id
                        )
                        if (
                            current_candidate is not None
                            and current_candidate.status == "proposed"
                        ):
                            store.suppress_workflow_candidate(
                                candidate.candidate_id,
                                reason_code="candidate-conflict",
                                suppressed_at=instant,
                                suppression_days=(
                                    effective.policy.storage.rejected_suppression_days
                                ),
                            )
                        notifications.append(self._automatic_notification(
                            candidate,
                            effective.policy_digest,
                            status="suppressed",
                            reason_codes=(
                                "candidate-conflict",
                                "candidate-suppressed",
                            ),
                            proposal=proposal,
                        ))
                    else:
                        notifications.append(self._automatic_notification(
                            candidate,
                            effective.policy_digest,
                            status="blocked",
                            reason_codes=(reason,),
                            proposal=proposal,
                        ))
                except (
                    ManagedProfilePathError,
                    MemoryStoreError,
                    ProfileIOError,
                    ProfileProposalError,
                    RoutingProfileContractError,
                    ValueError,
                ) as error:
                    notifications.append(self._automatic_notification(
                        candidate,
                        effective.policy_digest,
                        status="blocked",
                        reason_codes=(
                            _promotion_reason(error, "automatic-promotion-failed"),
                        ),
                        proposal=proposal,
                    ))

            result_reasons = ("promotion-batch-truncated",) if truncated else ()
            result = AutomaticPromotionResult(
                status="completed",
                scope=scope,
                promoted_count=sum(
                    item.status == "promoted" for item in notifications
                ),
                suppressed_count=sum(
                    item.status == "suppressed" for item in notifications
                ),
                skipped_count=sum(
                    item.status == "blocked" for item in notifications
                ),
                notifications=tuple(notifications),
                reason_codes=result_reasons,
            )
            stored, replayed = store.save_admin_result(
                idempotency_key=idempotency_key,
                command_kind="promote-eligible",
                command_digest=command_digest,
                result_document=result.to_dict(),
                created_at=instant,
            )
            return AutomaticPromotionResult.from_dict(
                stored, replayed=replayed
            )

    def preview_profile_update(
        self,
        candidate_id: str,
        *,
        current_profile: RoutingPreferenceProfile | None = None,
        workspace_root: Path | None = None,
        now: str | None = None,
    ) -> ProfileUpdateProposal:
        repository, effective = self._effective_policy(workspace_root)
        if not repository.memory_store_exists():
            raise MemoryStoreError("memory-store-unavailable")
        store = MemoryStore.open_if_enabled(self._data_dir, effective)
        if store is None:
            raise MemoryStoreError("memory-store-unavailable")
        with store:
            candidate = store.load_workflow_candidate(candidate_id)
            if candidate is None:
                raise MemoryStoreError("workflow-candidate-not-found")
            return create_profile_update_proposal(
                store, candidate, current_profile=current_profile, policy=effective,
                now=_utc_now() if now is None else now,
            )

    def transition_profile_update(
        self,
        proposal_id: str,
        *,
        action: str,
        expected_state_version: int,
        idempotency_key: str,
        correlation_id: str,
        workspace_root: Path | None = None,
        now: str | None = None,
    ) -> ProfileUpdateProposal:
        repository, effective = self._effective_policy(workspace_root)
        if not repository.memory_store_exists():
            raise MemoryStoreError("memory-store-unavailable")
        store = MemoryStore.open_if_enabled(self._data_dir, effective)
        if store is None:
            raise MemoryStoreError("memory-store-unavailable")
        with store:
            return transition_profile_update_proposal(
                store, proposal_id, action=action,
                expected_state_version=expected_state_version,
                idempotency_key=idempotency_key, correlation_id=correlation_id, now=now,
            )

    def apply_profile_update(
        self,
        proposal_id: str,
        *,
        authority: ProfileWriteAuthority,
        expected_state_version: int,
        idempotency_key: str,
        correlation_id: str,
        workspace_root: Path | None = None,
        now: str | None = None,
    ) -> ProfileRevision:
        repository, effective = self._effective_policy(workspace_root)
        if not repository.memory_store_exists():
            raise MemoryStoreError("memory-store-unavailable")
        store = MemoryStore.open_if_enabled(self._data_dir, effective)
        if store is None:
            raise MemoryStoreError("memory-store-unavailable")
        with store:
            return ProfileMaterializer(store, self._data_dir, effective).apply_approved(
                proposal_id,
                authority=authority,
                expected_state_version=expected_state_version,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
                now=_utc_now() if now is None else now,
            )

    def list_profile_revisions(
        self,
        profile_id: str,
        *,
        workspace_root: Path | None = None,
    ) -> tuple[ProfileRevision, ...]:
        repository, effective = self._effective_policy(workspace_root)
        if not repository.memory_store_exists():
            return ()
        store = (
            MemoryStore.open_if_enabled(self._data_dir, effective)
            if effective.capture_enabled
            else MemoryStore.open_existing(self._data_dir)
        )
        if store is None:
            return ()
        with store:
            return ProfileRevisionStore(self._data_dir, store).list(profile_id)

    def diff_profile_revisions(
        self,
        from_revision_id: str,
        to_revision_id: str,
        *,
        workspace_root: Path | None = None,
    ):
        repository, effective = self._effective_policy(workspace_root)
        if not repository.memory_store_exists():
            raise MemoryStoreError("memory-store-unavailable")
        store = (
            MemoryStore.open_if_enabled(self._data_dir, effective)
            if effective.capture_enabled
            else MemoryStore.open_existing(self._data_dir)
        )
        if store is None:
            raise MemoryStoreError("memory-store-unavailable")
        with store:
            revisions = ProfileRevisionStore(self._data_dir, store)
            before = revisions.load_snapshot(from_revision_id)
            after = revisions.load_snapshot(to_revision_id)
            return diff_profiles(before, after)

    def create_rollback_proposal(
        self,
        source_revision_id: str,
        *,
        authority: ProfileWriteAuthority,
        expected_profile_digest: str,
        workspace_root: Path | None = None,
        now: str | None = None,
    ) -> ProfileUpdateProposal:
        repository, effective = self._effective_policy(workspace_root)
        if not repository.memory_store_exists():
            raise MemoryStoreError("memory-store-unavailable")
        store = MemoryStore.open_if_enabled(self._data_dir, effective)
        if store is None:
            raise MemoryStoreError("memory-store-unavailable")
        with store:
            return ProfileMaterializer(store, self._data_dir, effective).create_rollback_proposal(
                source_revision_id,
                authority=authority,
                expected_profile_digest=expected_profile_digest,
                now=_utc_now() if now is None else now,
            )

    def history_summary(self, query: HistorySummaryQuery) -> HistorySummary:
        if not isinstance(query, HistorySummaryQuery):
            raise TypeError("query must be HistorySummaryQuery")
        repository, effective = self._effective_policy(None)
        if not effective.capture_enabled or not repository.memory_store_exists():
            return HistorySummary.empty()
        store = MemoryStore.open_if_enabled(self._data_dir, effective)
        if store is None:
            return HistorySummary.empty()
        with store:
            observations = tuple(
                item for item in store.list_route_observations()
                if (
                    query.workspace_identity_digest is None
                    or item.workspace_identity_digest == query.workspace_identity_digest
                )
                and (
                    query.route_signature_digest is None
                    or item.route_signature_digest == query.route_signature_digest
                )
            )
            observation_ids = {item.observation_id for item in observations}
            feedback = tuple(
                item for item in store.list_route_feedback()
                if item.observation_id in observation_ids
            )
            return HistorySummary.create(observations, feedback)

    def export_history(
        self,
        query: HistorySummaryQuery,
        *,
        include_observations: bool = False,
    ) -> str:
        summary = self.history_summary(query)
        repository, effective = self._effective_policy(None)
        observations: list[dict[str, object]] = []
        if include_observations and effective.capture_enabled and repository.memory_store_exists():
            store = MemoryStore.open_if_enabled(self._data_dir, effective)
            if store is not None:
                with store:
                    observations = [
                        item.to_dict()
                        for item in store.list_route_observations()
                        if (
                            query.workspace_identity_digest is None
                            or item.workspace_identity_digest == query.workspace_identity_digest
                        )
                        and (
                            query.route_signature_digest is None
                            or item.route_signature_digest == query.route_signature_digest
                        )
                    ]
        document = {
            "schema_id": "workflow-skill-router/history-export",
            "schema_version": "1.0.0",
            "artifact_kind": "history-export",
            "summary": summary.to_dict(),
            "observations": observations,
            "feedback_included": False,
        }
        exported = canonical_json(document)
        forbidden = (
            "raw_prompt",
            "raw_objective",
            "reported_outcome",
            "file_content",
            "tool_arguments",
            "secrets",
            '"free_text"',
            str(self._data_dir.absolute()),
        )
        if any(item and item in exported for item in forbidden):
            raise MemoryStoreError("memory-history-export-redaction-failed")
        return exported

    def enforce_retention(self, *, now: str | None = None) -> RetentionResult:
        repository, effective = self._effective_policy(None)
        applied_at = _utc_now() if now is None else now
        if not effective.capture_enabled or not repository.memory_store_exists():
            return RetentionResult(0, 0, 0, applied_at)
        store = MemoryStore.open_if_enabled(self._data_dir, effective)
        if store is None:
            return RetentionResult(0, 0, 0, applied_at)
        with store:
            counts = store.enforce_retention(
                retention_days=effective.policy.storage.retention_days,
                max_observations=effective.policy.storage.max_observations,
                now=applied_at,
            )
        return RetentionResult(
            deleted_observations=counts["deleted_observations"],
            deleted_feedback=counts["deleted_feedback"],
            remaining_observations=counts["remaining_observations"],
            applied_at=applied_at,
        )

    def purge_memory(self, command: PurgeMemoryCommand) -> PurgeMemoryResult:
        if not isinstance(command, PurgeMemoryCommand):
            raise TypeError("command must be PurgeMemoryCommand")
        repository, effective = self._effective_policy(None)
        if not repository.memory_store_exists():
            empty = HistorySummary.empty()
            if command.expected_summary_digest != empty.summary_digest:
                raise MemoryCommandConflict("stale-summary-digest")
            return PurgeMemoryResult(
                status="scope-not-available" if command.scope not in {"history-only", "analytics-only"} else "purged",
                scope=command.scope,
                deleted_observations=0,
                deleted_feedback=0,
                deleted_command_receipts=0,
                summary_digest_before=empty.summary_digest,
                summary_digest_after=empty.summary_digest,
                replayed=False,
                reason_codes=("scope-not-available",) if command.scope not in {"history-only", "analytics-only"} else (),
            )
        # Purge is an explicit privacy operation and remains available after
        # capture is disabled. Opening an existing Store never creates paths or
        # records a new Policy Snapshot.
        store = (
            MemoryStore.open_if_enabled(self._data_dir, effective)
            if effective.capture_enabled
            else MemoryStore.open_existing(self._data_dir)
        )
        if store is None:
            raise MemoryStoreError("memory-store-unavailable")
        with store:
            command_digest = _digest({
                "command": command.digest_document(),
                "policy_snapshot_id": store.current_policy_snapshot.snapshot_id,
            })
            existing = store.load_admin_result(
                idempotency_key=command.idempotency_key,
                command_kind="purge-workflow-memory",
                command_digest=command_digest,
            )
            if existing is not None:
                return PurgeMemoryResult.from_dict(existing, replayed=True)
            observations = store.list_route_observations()
            feedback = store.list_route_feedback()
            current = HistorySummary.create(observations, feedback)
            if command.expected_summary_digest != current.summary_digest:
                raise MemoryCommandConflict("stale-summary-digest")
            empty_digest = HistorySummary.empty().summary_digest
            stored, replayed = store.execute_purge_command(
                idempotency_key=command.idempotency_key,
                command_digest=command_digest,
                scope=command.scope,
                summary_digest_before=current.summary_digest,
                summary_digest_after=empty_digest,
                managed_profiles_requested=command.include_managed_profiles,
            )
            return PurgeMemoryResult.from_dict(stored, replayed=replayed)


    @staticmethod
    def _persisted_matcher(workflow) -> MatcherSeed | None:
        if workflow.routing_domains or workflow.routing_tags:
            return MatcherSeed((), workflow.routing_domains, workflow.routing_tags, "trusted-routing-context")
        if workflow.profile_objective_keywords or workflow.profile_domains or workflow.profile_tags:
            return MatcherSeed(
                workflow.profile_objective_keywords,
                workflow.profile_domains,
                workflow.profile_tags,
                "existing-profile",
            )
        return None

    @staticmethod
    def _not_recorded(
        command: RememberWorkflowCommand,
        status: str,
        reasons: tuple[str, ...],
        policy_digest: str | None,
    ) -> RememberWorkflowResult:
        return RememberWorkflowResult(
            status=status,
            observation_id=None,
            observation_digest=None,
            route_signature_digest=None,
            policy_digest=policy_digest,
            target_profile_class=command.target_profile_class,
            reason_codes=tuple(dict.fromkeys(reasons)),
            replayed=False,
        )


__all__ = [
    "HistorySummary",
    "HistorySummaryQuery",
    "MemoryCommandConflict",
    "PurgeMemoryCommand",
    "PurgeMemoryResult",
    "RecordRouteFeedbackCommand",
    "RecordRouteFeedbackResult",
    "AutomaticPromotionNotification",
    "AutomaticPromotionResult",
    "RetentionResult",
    "RouteFeedbackError",
    "RememberWorkflowCommand",
    "RememberWorkflowResult",
    "WorkflowMemoryService",
]
