from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
import uuid


class Clock(Protocol):
    def now_utc(self) -> datetime: ...


class IdFactory(Protocol):
    def new_event_id(self) -> str: ...


class SystemClock:
    def now_utc(self) -> datetime:
        return datetime.now(UTC)


class UuidFactory:
    def new_event_id(self) -> str:
        return str(uuid.uuid4())

