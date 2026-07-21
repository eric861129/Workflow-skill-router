from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from workflow_skill_router.workflow.local_observations import LocalProgressObservation


@dataclass(frozen=True, slots=True)
class ActivationObservation:
    capability_id: str
    activation_receipt_ref: str


@dataclass(frozen=True, slots=True)
class EvidenceObservation:
    gate_id: str
    evidence_kind: str
    evidence_receipt_ref: str


@dataclass(frozen=True, slots=True)
class SideEffectIntentObservation:
    action_digest: str
    intent_receipt_ref: str


@dataclass(frozen=True, slots=True)
class SideEffectOutcomeObservation:
    intent_id: str
    action_digest: str
    outcome_receipt_ref: str


@dataclass(frozen=True, slots=True)
class PauseRequestObservation:
    reason_code: str
    blocker_ref: str


Observation: TypeAlias = (
    ActivationObservation
    | EvidenceObservation
    | SideEffectIntentObservation
    | SideEffectOutcomeObservation
    | PauseRequestObservation
    | LocalProgressObservation
)
