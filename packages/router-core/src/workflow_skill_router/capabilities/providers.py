from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from .models import CapabilityKind, FieldObservation


@dataclass(frozen=True, slots=True)
class DiscoveryContext:
    runtime_fingerprint: str
    risk: str


@dataclass(frozen=True, slots=True)
class CapabilityObservation:
    canonical_id: str
    kind: CapabilityKind
    source: str
    fields: Mapping[str, FieldObservation[Any]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))


@dataclass(frozen=True, slots=True)
class ProviderResult:
    provider_id: str
    revision: str
    observed_at: datetime
    observations: tuple[CapabilityObservation, ...]
    degraded: bool
    reasons: tuple[str, ...]


@runtime_checkable
class CapabilityProvider(Protocol):
    def discover(self, context: DiscoveryContext) -> ProviderResult:
        """回傳此 provider 可證明的 metadata observations。"""
