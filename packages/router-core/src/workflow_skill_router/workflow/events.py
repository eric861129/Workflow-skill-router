from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, slots=True)
class EventDraft:
    event_type: str
    actor: str
    plan_revision: int
    inline_payload: Mapping[str, Any]
    payload_ref: str | None
    correlation_id: str
    causation_id: str | None
    workflow_run_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "inline_payload", MappingProxyType(dict(self.inline_payload)))


@dataclass(frozen=True, slots=True)
class WorkflowEvent:
    sequence: int
    schema_id: str
    schema_version: str
    artifact_kind: str
    event_id: str
    workflow_run_id: str | None
    aggregate_id: str
    aggregate_type: str
    event_type: str
    actor: str
    occurred_at: str
    state_version_before: int
    state_version_after: int
    plan_revision: int
    payload_digest: str
    payload_ref: str | None
    inline_payload: Mapping[str, Any]
    idempotency_key: str
    correlation_id: str
    causation_id: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "inline_payload", MappingProxyType(dict(self.inline_payload)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "artifact_kind": self.artifact_kind,
            "event_id": self.event_id,
            "workflow_run_id": self.workflow_run_id,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "event_type": self.event_type,
            "actor": self.actor,
            "occurred_at": self.occurred_at,
            "state_version_before": self.state_version_before,
            "state_version_after": self.state_version_after,
            "plan_revision": self.plan_revision,
            "payload_digest": self.payload_digest,
            "payload_ref": self.payload_ref,
            "inline_payload": dict(self.inline_payload),
            "idempotency_key": self.idempotency_key,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
        }
