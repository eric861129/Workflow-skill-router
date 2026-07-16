from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AdapterViolation(LookupError): pass


@dataclass(frozen=True, slots=True)
class AdapterKey:
    schema_id: str
    schema_version: str
    artifact_kind: str


class ArtifactAdapter(Protocol):
    def adapt(self, artifact: object) -> object: ...


class AdapterRegistry:
    def __init__(self, adapters: dict[AdapterKey, ArtifactAdapter], aliases: dict[str, tuple[str, ...]] | None = None) -> None:
        self._adapters = dict(adapters); self._aliases = dict(aliases or {})

    def resolve(self, key: AdapterKey) -> ArtifactAdapter:
        try: return self._adapters[key]
        except KeyError as error: raise AdapterViolation(f"unsupported_artifact:{key}") from error

    def resolve_capability_alias(self, alias: str) -> str:
        matches = self._aliases.get(alias, ())
        if len(matches) > 1: raise AdapterViolation("ambiguous_alias")
        if not matches: raise AdapterViolation("unknown_alias")
        return matches[0]
