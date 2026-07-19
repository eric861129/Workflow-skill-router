from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping


def canonical_json(document: Mapping[str, Any]) -> str:
    """以穩定鍵序與 UTF-8 可讀文字編碼 JSON object。"""

    return json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def canonical_json_bytes(document: Mapping[str, Any]) -> bytes:
    """回傳 canonical JSON 的 UTF-8 bytes。"""

    return canonical_json(document).encode("utf-8")


@dataclass(frozen=True, slots=True)
class ArtifactEnvelope:
    """所有 V2 artifact 共用且可分派的外層契約。"""

    schema_id: str
    schema_version: str
    artifact_kind: str
    artifact_id: str
    created_at: str
    payload: Mapping[str, Any]

    @classmethod
    def from_dict(cls, document: Mapping[str, Any]) -> "ArtifactEnvelope":
        required = (
            "schema_id",
            "schema_version",
            "artifact_kind",
            "artifact_id",
            "created_at",
            "payload",
        )
        missing = [name for name in required if name not in document]
        if missing:
            raise ValueError(f"ArtifactEnvelope 缺少欄位: {', '.join(missing)}")
        payload = document["payload"]
        if not isinstance(payload, Mapping):
            raise TypeError("ArtifactEnvelope.payload 必須是 object")
        return cls(
            *(str(document[name]) for name in required[:-1]),
            payload=dict(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "artifact_kind": self.artifact_kind,
            "artifact_id": self.artifact_id,
            "created_at": self.created_at,
            "payload": dict(self.payload),
        }
