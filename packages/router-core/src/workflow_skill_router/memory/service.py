from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re

from workflow_skill_router.schemas.artifacts import canonical_json

from .observations import (
    MatcherSeed,
    build_route_observation,
    evaluate_observation_eligibility,
)
from .policy_io import MemoryPolicyRepository
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


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


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
    "MemoryCommandConflict",
    "RememberWorkflowCommand",
    "RememberWorkflowResult",
    "WorkflowMemoryService",
]
