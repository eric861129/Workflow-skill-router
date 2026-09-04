from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Iterable

from workflow_skill_router.schemas.artifacts import canonical_json

from .policy_resolver import EffectiveMemoryPolicy
from .store import MemoryPolicySnapshot
from .workflow_reader import CompletedWorkflowPhase, CompletedWorkflowSnapshot


OBSERVATION_SCHEMA_ID = "workflow-skill-router/route-observation"
OBSERVATION_SCHEMA_VERSION = "1.0.0"
OBSERVATION_ARTIFACT_KIND = "route-observation"
_MATCHER_SOURCES = (
    "trusted-routing-context",
    "existing-profile",
    "user-explicit",
)
_TARGETS = (
    "managed-personal",
    "managed-workspace-local",
    "user-personal",
    "workspace-file",
)
_RISKS = ("r0", "r1", "r2", "r3")
_SIDE_EFFECTS = ("none", "known-success", "known-failure", "unknown")
_ONE_SHOT = ("none", "remember-once", "no-memory")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
_TOP_FIELDS = frozenset({
    "schema_id", "schema_version", "artifact_kind", "observation_id",
    "observation_digest", "workflow_run_digest", "workflow_fingerprint",
    "workspace_identity_digest", "work_mode", "terminal_status",
    "required_gates_passed", "side_effect_outcome", "risk_class",
    "policy_snapshot_id", "route_signature_digest", "route_source",
    "routing_profile_ids", "routing_profile_digest", "matched_profile_rule_id",
    "matcher_seed", "phases", "target_profile_class", "activation_status",
    "evidence_class", "automatic_promotion_eligible", "observed_at",
})


class RouteObservationError(ValueError):
    """Raised when a sanitized Route Observation violates its strict contract."""


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_values(values: Iterable[str], field: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise RouteObservationError(f"invalid-matcher-values:{field}")
    result: list[str] = []
    for raw in values:
        if not isinstance(raw, str):
            raise RouteObservationError(f"invalid-matcher-value:{field}")
        value = " ".join(raw.strip().casefold().split())
        if not value or len(value) > 128 or any(ord(ch) < 32 for ch in value):
            raise RouteObservationError(f"invalid-matcher-value:{field}")
        if field in {"domains", "tags"} and re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", value) is None:
            raise RouteObservationError("invalid-matcher-identifier")
        if field == "objective_keywords" and (
            "/" in value
            or "\\" in value
            or "://" in value
            or re.match(r"^[a-z]:", value) is not None
        ):
            raise RouteObservationError("sensitive-matcher-value")
        if value in result:
            raise RouteObservationError("duplicate-matcher-value")
        result.append(value)
    if len(result) > 32:
        raise RouteObservationError(f"too-many-matcher-values:{field}")
    return tuple(result)


@dataclass(frozen=True, slots=True)
class MatcherSeed:
    objective_keywords: tuple[str, ...]
    domains: tuple[str, ...]
    tags: tuple[str, ...]
    source: str

    def __post_init__(self) -> None:
        if self.source not in _MATCHER_SOURCES:
            raise RouteObservationError("invalid-matcher-source")
        object.__setattr__(self, "objective_keywords", _normalize_values(self.objective_keywords, "objective_keywords"))
        object.__setattr__(self, "domains", _normalize_values(self.domains, "domains"))
        object.__setattr__(self, "tags", _normalize_values(self.tags, "tags"))

    @property
    def has_signal(self) -> bool:
        return bool(self.objective_keywords or self.domains or self.tags)

    def to_dict(self) -> dict[str, object]:
        return {
            "objective_keywords": list(self.objective_keywords),
            "domains": list(self.domains),
            "tags": list(self.tags),
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class ObservationEligibility:
    eligible: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RouteObservationPhase:
    phase_id: str
    primary_skill_id: str | None
    support_skill_ids: tuple[str, ...]
    exit_gate_ids: tuple[str, ...]

    @classmethod
    def from_completed(cls, phase: CompletedWorkflowPhase) -> "RouteObservationPhase":
        return cls(phase.phase_id, phase.primary_skill_id, phase.support_skill_ids, phase.exit_gate_ids)

    def to_dict(self) -> dict[str, object]:
        return {
            "phase_id": self.phase_id,
            "primary_skill_id": self.primary_skill_id,
            "support_skill_ids": list(self.support_skill_ids),
            "exit_gate_ids": list(self.exit_gate_ids),
        }


@dataclass(frozen=True, slots=True)
class RouteObservation:
    observation_id: str
    observation_digest: str
    workflow_run_digest: str
    workflow_fingerprint: str
    workspace_identity_digest: str | None
    work_mode: str
    terminal_status: str
    required_gates_passed: bool
    side_effect_outcome: str
    risk_class: str
    policy_snapshot_id: str
    route_signature_digest: str
    route_source: str
    routing_profile_ids: tuple[str, ...]
    routing_profile_digest: str | None
    matched_profile_rule_id: str | None
    matcher_seed: MatcherSeed
    phases: tuple[RouteObservationPhase, ...]
    target_profile_class: str
    activation_status: str
    evidence_class: str
    automatic_promotion_eligible: bool
    observed_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": OBSERVATION_SCHEMA_ID,
            "schema_version": OBSERVATION_SCHEMA_VERSION,
            "artifact_kind": OBSERVATION_ARTIFACT_KIND,
            "observation_id": self.observation_id,
            "observation_digest": self.observation_digest,
            "workflow_run_digest": self.workflow_run_digest,
            "workflow_fingerprint": self.workflow_fingerprint,
            "workspace_identity_digest": self.workspace_identity_digest,
            "work_mode": self.work_mode,
            "terminal_status": self.terminal_status,
            "required_gates_passed": self.required_gates_passed,
            "side_effect_outcome": self.side_effect_outcome,
            "risk_class": self.risk_class,
            "policy_snapshot_id": self.policy_snapshot_id,
            "route_signature_digest": self.route_signature_digest,
            "route_source": self.route_source,
            "routing_profile_ids": list(self.routing_profile_ids),
            "routing_profile_digest": self.routing_profile_digest,
            "matched_profile_rule_id": self.matched_profile_rule_id,
            "matcher_seed": self.matcher_seed.to_dict(),
            "phases": [phase.to_dict() for phase in self.phases],
            "target_profile_class": self.target_profile_class,
            "activation_status": self.activation_status,
            "evidence_class": self.evidence_class,
            "automatic_promotion_eligible": self.automatic_promotion_eligible,
            "observed_at": self.observed_at,
        }

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())


def evaluate_observation_eligibility(
    workflow: CompletedWorkflowSnapshot,
    policy: EffectiveMemoryPolicy,
    matcher_seed: MatcherSeed | None,
    *,
    target_profile_class: str,
    risk_class: str,
    side_effect_outcome: str,
    one_shot: str,
) -> ObservationEligibility:
    reasons: list[str] = []
    if one_shot not in _ONE_SHOT:
        reasons.append("invalid-one-shot")
    if one_shot == "no-memory":
        reasons.append("explicit-no-memory")
    if workflow.terminal_status != "completed":
        reasons.append("workflow-not-completed")
    if not workflow.required_gates_passed:
        reasons.append("required-gate-failed")
    if risk_class not in _RISKS:
        reasons.append("invalid-risk-class")
    elif risk_class in policy.policy.eligibility.exclude_risk_levels:
        reasons.append("risk-excluded")
    if side_effect_outcome not in _SIDE_EFFECTS:
        reasons.append("invalid-side-effect-outcome")
    elif side_effect_outcome == "unknown":
        reasons.append("side-effect-unknown")
    elif side_effect_outcome == "known-failure":
        reasons.append("side-effect-failed")
    if workflow.pending_consent:
        reasons.append("pending-consent")
    if matcher_seed is None or not matcher_seed.has_signal:
        reasons.append("insufficient-match-signal")
    if target_profile_class not in _TARGETS:
        reasons.append("invalid-target")
    elif target_profile_class not in policy.allowed_targets:
        # `remember-once` in observe mode may retain a managed target as
        # non-executable metadata, but it still cannot write a Profile.
        one_shot_observe = (
            one_shot == "remember-once"
            and policy.mode.value == "observe"
            and target_profile_class in {"managed-personal", "managed-workspace-local"}
        )
        if not one_shot_observe:
            reasons.append("target-not-allowed")
    if (
        workflow.route_source == "user-explicit"
        and policy.mode.value == "observe"
        and one_shot != "remember-once"
    ):
        reasons.append("explicit-route-requires-remember-once")
    return ObservationEligibility(not reasons, tuple(dict.fromkeys(reasons)))


def build_route_observation(
    workflow: CompletedWorkflowSnapshot,
    matcher_seed: MatcherSeed,
    policy_snapshot: MemoryPolicySnapshot,
    *,
    target_profile_class: str,
    risk_class: str,
    side_effect_outcome: str,
    observed_at: str,
) -> RouteObservation:
    phases = tuple(RouteObservationPhase.from_completed(phase) for phase in workflow.phases)
    route_signature = {
        "work_mode": workflow.work_mode,
        "route_source": workflow.route_source,
        "routing_profile_ids": list(workflow.routing_profile_ids),
        "routing_profile_digest": workflow.routing_profile_digest,
        "matched_profile_rule_id": workflow.matched_profile_rule_id,
        "matcher_seed": matcher_seed.to_dict(),
        "phases": [phase.to_dict() for phase in phases],
        "target_profile_class": target_profile_class,
    }
    route_signature_digest = _digest(route_signature)
    automatic_eligible = (
        matcher_seed.source != "user-explicit"
        and policy_snapshot.mode.value == "automatic"
        and target_profile_class in {"managed-personal", "managed-workspace-local"}
    )
    payload: dict[str, object] = {
        "schema_id": OBSERVATION_SCHEMA_ID,
        "schema_version": OBSERVATION_SCHEMA_VERSION,
        "artifact_kind": OBSERVATION_ARTIFACT_KIND,
        "observation_id": "",
        "observation_digest": "",
        "workflow_run_digest": workflow.workflow_run_digest,
        "workflow_fingerprint": workflow.workflow_fingerprint,
        "workspace_identity_digest": workflow.workspace_identity_digest,
        "work_mode": workflow.work_mode,
        "terminal_status": workflow.terminal_status,
        "required_gates_passed": workflow.required_gates_passed,
        "side_effect_outcome": side_effect_outcome,
        "risk_class": risk_class,
        "policy_snapshot_id": policy_snapshot.snapshot_id,
        "route_signature_digest": route_signature_digest,
        "route_source": workflow.route_source,
        "routing_profile_ids": list(workflow.routing_profile_ids),
        "routing_profile_digest": workflow.routing_profile_digest,
        "matched_profile_rule_id": workflow.matched_profile_rule_id,
        "matcher_seed": matcher_seed.to_dict(),
        "phases": [phase.to_dict() for phase in phases],
        "target_profile_class": target_profile_class,
        "activation_status": "unverified",
        "evidence_class": "user-or-agent-reported-local",
        "automatic_promotion_eligible": automatic_eligible,
        "observed_at": observed_at,
    }
    digest_payload = {k: v for k, v in payload.items() if k not in {"observation_id", "observation_digest"}}
    observation_digest = _digest(digest_payload)
    payload["observation_digest"] = observation_digest
    payload["observation_id"] = "observation:" + observation_digest.removeprefix("sha256:")[:32]
    return decode_route_observation(payload)


def _strict_list(value: object, field: str, *, max_items: int = 64) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > max_items or any(not isinstance(item, str) for item in value):
        raise RouteObservationError(f"invalid-list:{field}")
    if len(set(value)) != len(value):
        raise RouteObservationError(f"duplicate-list-value:{field}")
    return tuple(value)


def decode_route_observation(value: Mapping[str, object]) -> RouteObservation:
    if not isinstance(value, Mapping) or any(not isinstance(k, str) for k in value):
        raise RouteObservationError("invalid-observation-document")
    if set(value) != _TOP_FIELDS:
        raise RouteObservationError("invalid-observation-fields")
    if value["schema_id"] != OBSERVATION_SCHEMA_ID or value["schema_version"] != OBSERVATION_SCHEMA_VERSION or value["artifact_kind"] != OBSERVATION_ARTIFACT_KIND:
        raise RouteObservationError("invalid-observation-contract")
    observation_id = value["observation_id"]
    observation_digest = value["observation_digest"]
    if not isinstance(observation_id, str) or not observation_id.startswith("observation:") or len(observation_id) > 128:
        raise RouteObservationError("invalid-observation-id")
    if not isinstance(observation_digest, str) or not _DIGEST.fullmatch(observation_digest):
        raise RouteObservationError("invalid-observation-digest")
    for field in ("workflow_run_digest", "workflow_fingerprint", "policy_snapshot_id", "route_signature_digest"):
        if not isinstance(value[field], str) or not _DIGEST.fullmatch(value[field]):
            raise RouteObservationError(f"invalid-digest:{field}")
    for field in ("workspace_identity_digest", "routing_profile_digest"):
        if value[field] is not None and (not isinstance(value[field], str) or not _DIGEST.fullmatch(value[field])):
            raise RouteObservationError(f"invalid-digest:{field}")
    if value["work_mode"] not in {"single", "phased", "managed-goal"}:
        raise RouteObservationError("invalid-work-mode")
    if value["terminal_status"] != "completed" or value["required_gates_passed"] is not True:
        raise RouteObservationError("invalid-terminal-state")
    if value["side_effect_outcome"] not in _SIDE_EFFECTS or value["risk_class"] not in _RISKS:
        raise RouteObservationError("invalid-risk-or-side-effect")
    if value["target_profile_class"] not in _TARGETS:
        raise RouteObservationError("invalid-target")
    if value["activation_status"] != "unverified" or value["evidence_class"] != "user-or-agent-reported-local":
        raise RouteObservationError("invalid-evidence-boundary")
    if not isinstance(value["automatic_promotion_eligible"], bool):
        raise RouteObservationError("invalid-promotion-eligibility")
    if not isinstance(value["observed_at"], str) or not value["observed_at"].endswith("Z") or len(value["observed_at"]) > 40:
        raise RouteObservationError("invalid-observed-at")
    route_source = value["route_source"]
    if not isinstance(route_source, str) or not _SAFE_ID.fullmatch(route_source):
        raise RouteObservationError("invalid-route-source")
    profile_ids = _strict_list(value["routing_profile_ids"], "routing_profile_ids")
    matched_rule = value["matched_profile_rule_id"]
    if matched_rule is not None and (not isinstance(matched_rule, str) or not _SAFE_ID.fullmatch(matched_rule)):
        raise RouteObservationError("invalid-matched-rule")
    matcher = value["matcher_seed"]
    if not isinstance(matcher, Mapping) or set(matcher) != {"objective_keywords", "domains", "tags", "source"}:
        raise RouteObservationError("invalid-matcher-seed")
    seed = MatcherSeed(
        _strict_list(matcher["objective_keywords"], "objective_keywords", max_items=32),
        _strict_list(matcher["domains"], "domains", max_items=32),
        _strict_list(matcher["tags"], "tags", max_items=32),
        str(matcher["source"]),
    )
    raw_phases = value["phases"]
    if not isinstance(raw_phases, list) or not raw_phases or len(raw_phases) > 64:
        raise RouteObservationError("invalid-phases")
    phases: list[RouteObservationPhase] = []
    for raw in raw_phases:
        if not isinstance(raw, Mapping) or set(raw) != {"phase_id", "primary_skill_id", "support_skill_ids", "exit_gate_ids"}:
            raise RouteObservationError("invalid-phase")
        phase_id = raw["phase_id"]
        primary = raw["primary_skill_id"]
        if not isinstance(phase_id, str) or not _SAFE_ID.fullmatch(phase_id):
            raise RouteObservationError("invalid-phase-id")
        if primary is not None and (not isinstance(primary, str) or not primary.startswith("skill:")):
            raise RouteObservationError("invalid-primary-skill")
        phases.append(RouteObservationPhase(
            phase_id,
            primary,
            _strict_list(raw["support_skill_ids"], "support_skill_ids"),
            _strict_list(raw["exit_gate_ids"], "exit_gate_ids"),
        ))
    digest_payload = {k: v for k, v in value.items() if k not in {"observation_id", "observation_digest"}}
    expected = _digest(digest_payload)
    if observation_digest != expected or observation_id != "observation:" + expected.removeprefix("sha256:")[:32]:
        raise RouteObservationError("observation-digest-mismatch")
    return RouteObservation(
        observation_id=observation_id,
        observation_digest=observation_digest,
        workflow_run_digest=str(value["workflow_run_digest"]),
        workflow_fingerprint=str(value["workflow_fingerprint"]),
        workspace_identity_digest=None if value["workspace_identity_digest"] is None else str(value["workspace_identity_digest"]),
        work_mode=str(value["work_mode"]), terminal_status="completed", required_gates_passed=True,
        side_effect_outcome=str(value["side_effect_outcome"]), risk_class=str(value["risk_class"]),
        policy_snapshot_id=str(value["policy_snapshot_id"]), route_signature_digest=str(value["route_signature_digest"]),
        route_source=route_source, routing_profile_ids=profile_ids,
        routing_profile_digest=None if value["routing_profile_digest"] is None else str(value["routing_profile_digest"]),
        matched_profile_rule_id=None if matched_rule is None else str(matched_rule), matcher_seed=seed,
        phases=tuple(phases), target_profile_class=str(value["target_profile_class"]), activation_status="unverified",
        evidence_class="user-or-agent-reported-local", automatic_promotion_eligible=bool(value["automatic_promotion_eligible"]),
        observed_at=str(value["observed_at"]),
    )


__all__ = [
    "MatcherSeed", "ObservationEligibility", "RouteObservation", "RouteObservationError",
    "RouteObservationPhase", "build_route_observation", "decode_route_observation",
    "evaluate_observation_eligibility",
]
