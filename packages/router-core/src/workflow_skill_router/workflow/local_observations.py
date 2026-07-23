from __future__ import annotations

from dataclasses import dataclass


LOCAL_PROGRESS_TRANSITIONS = frozenset({
    "start",
    "submit",
    "pause",
    "resume",
    "fail",
})


class LocalObservationPolicyError(ValueError):
    """Raised when unverified input crosses the Router-local authority boundary."""


@dataclass(frozen=True, slots=True)
class LocalProgressObservation:
    """User- or agent-reported progress for one Router-owned local item."""

    work_item_id: str
    transition: str
    check_ids: tuple[str, ...]
    reported_outcome: str | None
