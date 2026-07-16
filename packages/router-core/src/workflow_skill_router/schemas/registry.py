from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, TypeAlias

from .errors import SchemaRegistryError


SchemaKey: TypeAlias = tuple[str, str, str]
Decoder: TypeAlias = Callable[[Mapping[str, Any]], object]


class SchemaRegistry:
    """依 schema id、version 與 artifact kind 精確分派 decoder。"""

    def __init__(self) -> None:
        self._decoders: dict[SchemaKey, Decoder] = {}

    def register(
        self,
        schema_id: str,
        schema_version: str,
        artifact_kind: str,
        decoder: Decoder,
    ) -> None:
        key = (schema_id, schema_version, artifact_kind)
        if key in self._decoders:
            raise SchemaRegistryError(f"重複登錄 schema contract: {key}")
        self._decoders[key] = decoder

    def decode(self, document: Mapping[str, Any]) -> object:
        try:
            key = tuple(
                str(document[name])
                for name in ("schema_id", "schema_version", "artifact_kind")
            )
        except KeyError as error:
            raise SchemaRegistryError(f"缺少 schema discriminator: {error.args[0]}") from error
        decoder = self._decoders.get(key)  # type: ignore[arg-type]
        if decoder is None:
            raise SchemaRegistryError(f"未登錄的 schema contract: {key}")
        return decoder(document)
