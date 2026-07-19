from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from workflow_skill_router.persistence.sqlite_store import AppendResult, SQLiteEventStore

from .events import EventDraft
from .observations import (
    ActivationObservation, EvidenceObservation, Observation, PauseRequestObservation,
    SideEffectIntentObservation, SideEffectOutcomeObservation,
)


class ObservationIntegrityError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RecordObservationCommand:
    workflow_run_id: str
    phase_id: str
    observation: Observation
    expected_state_version: int
    idempotency_key: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class WorkEventContext:
    workflow_run_id: str
    phase_id: str
    state_version: int
    plan_revision: int
    actor: str
    causation_id: str | None

    def event_draft(
        self,
        event_type: str,
        payload: Mapping[str, object],
        *,
        correlation_id: str,
    ) -> EventDraft:
        return EventDraft(
            workflow_run_id=self.workflow_run_id,
            event_type=event_type,
            actor=self.actor,
            plan_revision=self.plan_revision,
            inline_payload={"phase_id": self.phase_id, **dict(payload)},
            payload_ref=None,
            correlation_id=correlation_id,
            causation_id=self.causation_id,
        )


def _exact(value: object, fields: frozenset[str], context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} must be object")
    keys = {str(key) for key in value}
    missing = sorted(fields - keys)
    unknown = sorted(keys - fields)
    if missing:
        raise ValueError(f"{context} missing field: {', '.join(missing)}")
    if unknown:
        raise ValueError(f"{context} unknown field: {', '.join(unknown)}")
    return value


def decode_record_observation(document: object) -> RecordObservationCommand:
    root = _exact(document, frozenset({
        "workflow_run_id", "phase_id", "observation", "expected_state_version",
        "idempotency_key", "correlation_id",
    }), "record observation")
    raw = root["observation"]
    if not isinstance(raw, Mapping) or not isinstance(raw.get("kind"), str):
        raise ValueError("observation kind missing")
    kind = raw["kind"]
    contracts = {
        "activation": (
            frozenset({"kind", "capability_id", "activation_receipt_ref"}),
            lambda item: ActivationObservation(str(item["capability_id"]), str(item["activation_receipt_ref"])),
        ),
        "evidence": (
            frozenset({"kind", "gate_id", "evidence_kind", "evidence_receipt_ref"}),
            lambda item: EvidenceObservation(str(item["gate_id"]), str(item["evidence_kind"]), str(item["evidence_receipt_ref"])),
        ),
        "side-effect-intent": (
            frozenset({"kind", "action_digest", "intent_receipt_ref"}),
            lambda item: SideEffectIntentObservation(str(item["action_digest"]), str(item["intent_receipt_ref"])),
        ),
        "side-effect-outcome": (
            frozenset({"kind", "intent_id", "action_digest", "outcome_receipt_ref"}),
            lambda item: SideEffectOutcomeObservation(str(item["intent_id"]), str(item["action_digest"]), str(item["outcome_receipt_ref"])),
        ),
        "pause-request": (
            frozenset({"kind", "reason_code", "blocker_ref"}),
            lambda item: PauseRequestObservation(str(item["reason_code"]), str(item["blocker_ref"])),
        ),
    }
    if kind not in contracts:
        raise ValueError("unsupported observation kind")
    fields, decoder = contracts[kind]
    observation = decoder(_exact(raw, fields, "observation"))
    expected = root["expected_state_version"]
    if isinstance(expected, bool) or not isinstance(expected, int):
        raise ValueError("expected_state_version must be integer")
    return RecordObservationCommand(
        str(root["workflow_run_id"]), str(root["phase_id"]), observation, expected,
        str(root["idempotency_key"]), str(root["correlation_id"]),
    )


def _payload(verified: object) -> Mapping[str, object]:
    if isinstance(verified, Mapping):
        return verified
    method = getattr(verified, "to_event_payload", None)
    if callable(method):
        result = method()
        if isinstance(result, Mapping):
            return result
    raise ObservationIntegrityError("verified receipt payload 無效")


class WorkEventCoordinator:
    def __init__(
        self,
        store: SQLiteEventStore,
        context_repository,
        activation_verifier,
        evidence_verifier,
        side_effect_verifier,
        transition_coordinator,
    ) -> None:
        self._store = store
        self._contexts = context_repository
        self._activations = activation_verifier
        self._evidence = evidence_verifier
        self._side_effects = side_effect_verifier
        self._transitions = transition_coordinator

    def record(self, command: RecordObservationCommand) -> AppendResult:
        context = self._contexts.require(
            command.workflow_run_id,
            command.phase_id,
            command.expected_state_version,
        )
        observation = command.observation
        if isinstance(observation, ActivationObservation):
            verified = self._activations.resolve_and_verify(
                observation.activation_receipt_ref,
                context=context,
            )
            draft = context.event_draft(
                "CAPABILITY_ACTIVATION_OBSERVED", _payload(verified),
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
                "EVIDENCE_RECORDED", _payload(verified),
                correlation_id=command.correlation_id,
            )
        elif isinstance(observation, SideEffectIntentObservation):
            verified = self._side_effects.verify_intent(
                observation.intent_receipt_ref, context,
            )
            draft = context.event_draft(
                "SIDE_EFFECT_INTENT_RECORDED", _payload(verified),
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
                "SIDE_EFFECT_OUTCOME_RECORDED", _payload(verified),
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
            "workflow",
            command.workflow_run_id,
            [draft],
            command.expected_state_version,
            command.idempotency_key,
        )
