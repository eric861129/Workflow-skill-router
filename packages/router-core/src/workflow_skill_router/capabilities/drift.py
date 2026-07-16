from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
from typing import Any

from workflow_skill_router.schemas.artifacts import ArtifactEnvelope, canonical_json_bytes
from workflow_skill_router.schemas.errors import SchemaRegistryError

from .codecs import SCHEMA_VERSION
from .models import Capability, CapabilityDrift, CapabilitySnapshot, DriftKind


CAPABILITY_DRIFT_SCHEMA_ID = "workflow-skill-router/capability-drift"
_ENVELOPE_FIELDS = frozenset({
    "schema_id",
    "schema_version",
    "artifact_kind",
    "artifact_id",
    "created_at",
    "payload",
})
_DRIFT_FIELDS = frozenset({
    "drift_id",
    "previous_snapshot_id",
    "current_snapshot_id",
    "capability_id",
    "kind",
    "changed_fields",
    "before_fingerprint",
    "after_fingerprint",
    "detected_at",
})
_KIND_ORDER = {kind: index for index, kind in enumerate(DriftKind)}


def _exact_mapping(
    value: object,
    expected: frozenset[str],
    context: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaRegistryError(f"{context} must be object")
    if not all(isinstance(key, str) for key in value):
        raise SchemaRegistryError(f"{context} unknown field: non-string key")
    keys = set(value)
    missing = sorted(expected - keys)
    if missing:
        raise SchemaRegistryError(f"{context} missing field: {', '.join(missing)}")
    unknown = sorted(keys - expected)
    if unknown:
        raise SchemaRegistryError(f"{context} unknown field: {', '.join(unknown)}")
    return value


def _string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise SchemaRegistryError(f"{context} must be non-empty string")
    return value


def _optional_string(value: object, context: str) -> str | None:
    return None if value is None else _string(value, context)


def _canonical_timestamp(value: object, context: str) -> str:
    text = _string(value, context)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise SchemaRegistryError(f"{context} must be ISO-8601 datetime") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SchemaRegistryError(f"{context} must include timezone")
    canonical = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if canonical != text:
        raise SchemaRegistryError(f"{context} must use canonical UTC timestamp")
    return canonical


def _payload(drift: CapabilityDrift) -> dict[str, object]:
    return {
        "drift_id": drift.drift_id,
        "previous_snapshot_id": drift.previous_snapshot_id,
        "current_snapshot_id": drift.current_snapshot_id,
        "capability_id": drift.capability_id,
        "kind": drift.kind.value,
        "changed_fields": list(drift.changed_fields),
        "before_fingerprint": drift.before_fingerprint,
        "after_fingerprint": drift.after_fingerprint,
        "detected_at": drift.detected_at,
    }


def encode_drift(drift: CapabilityDrift) -> ArtifactEnvelope:
    detected_at = _canonical_timestamp(drift.detected_at, "capability drift.detected_at")
    return ArtifactEnvelope(
        schema_id=CAPABILITY_DRIFT_SCHEMA_ID,
        schema_version=SCHEMA_VERSION,
        artifact_kind="capability-drift",
        artifact_id=drift.drift_id,
        created_at=detected_at,
        payload=_payload(drift),
    )


def decode_drift(document: Mapping[str, Any]) -> CapabilityDrift:
    envelope = _exact_mapping(document, _ENVELOPE_FIELDS, "artifact envelope")
    if (
        envelope["schema_id"] != CAPABILITY_DRIFT_SCHEMA_ID
        or envelope["schema_version"] != SCHEMA_VERSION
        or envelope["artifact_kind"] != "capability-drift"
    ):
        raise SchemaRegistryError("artifact envelope contract mismatch")
    artifact_id = _string(envelope["artifact_id"], "artifact envelope.artifact_id")
    created_at = _canonical_timestamp(envelope["created_at"], "artifact envelope.created_at")
    payload = _exact_mapping(envelope["payload"], _DRIFT_FIELDS, "capability drift")
    changed = payload["changed_fields"]
    if not isinstance(changed, list) or not all(
        isinstance(item, str) and item for item in changed
    ):
        raise SchemaRegistryError("capability drift.changed_fields must be string array")
    try:
        kind = DriftKind(_string(payload["kind"], "capability drift.kind"))
    except ValueError as error:
        raise SchemaRegistryError("capability drift.kind has invalid value") from error
    detected_at = _canonical_timestamp(
        payload["detected_at"],
        "capability drift.detected_at",
    )
    drift = CapabilityDrift(
        drift_id=_string(payload["drift_id"], "capability drift.drift_id"),
        previous_snapshot_id=_optional_string(
            payload["previous_snapshot_id"],
            "capability drift.previous_snapshot_id",
        ),
        current_snapshot_id=_string(
            payload["current_snapshot_id"],
            "capability drift.current_snapshot_id",
        ),
        capability_id=_string(payload["capability_id"], "capability drift.capability_id"),
        kind=kind,
        changed_fields=tuple(changed),
        before_fingerprint=_optional_string(
            payload["before_fingerprint"],
            "capability drift.before_fingerprint",
        ),
        after_fingerprint=_optional_string(
            payload["after_fingerprint"],
            "capability drift.after_fingerprint",
        ),
        detected_at=detected_at,
    )
    if artifact_id != drift.drift_id:
        raise SchemaRegistryError("capability drift artifact_id mismatch")
    if created_at != drift.detected_at:
        raise SchemaRegistryError("capability drift detected_at mismatch")
    return drift


def _build_drift(
    previous_snapshot_id: str | None,
    current_snapshot_id: str,
    capability_id: str,
    kind: DriftKind,
    changed_fields: tuple[str, ...],
    before_fingerprint: str | None,
    after_fingerprint: str | None,
    detected_at: str,
) -> CapabilityDrift:
    identity = {
        "previous_snapshot_id": previous_snapshot_id,
        "current_snapshot_id": current_snapshot_id,
        "capability_id": capability_id,
        "kind": kind.value,
        "changed_fields": list(changed_fields),
        "before_fingerprint": before_fingerprint,
        "after_fingerprint": after_fingerprint,
        "detected_at": detected_at,
    }
    drift_id = "sha256:" + hashlib.sha256(canonical_json_bytes(identity)).hexdigest()
    return CapabilityDrift(
        drift_id=drift_id,
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        capability_id=capability_id,
        kind=kind,
        changed_fields=changed_fields,
        before_fingerprint=before_fingerprint,
        after_fingerprint=after_fingerprint,
        detected_at=detected_at,
    )


def _is_rename(before: Capability, after: Capability) -> bool:
    return (
        before.canonical_id in after.aliases
        or after.canonical_id in before.aliases
        or bool(set(before.aliases) & set(after.aliases))
    )


def _same_id_drifts(
    before: Capability,
    after: Capability,
    previous: CapabilitySnapshot,
    current: CapabilitySnapshot,
) -> list[CapabilityDrift]:
    changes: list[tuple[DriftKind, tuple[str, ...]]] = []
    if before.installer_content_digest.value != after.installer_content_digest.value:
        changes.append((DriftKind.INSTRUCTION_CONTENT, ("installer_content_digest",)))
    semantic_fields: list[str] = []
    for field_name in (
        "display_name",
        "description",
        "domains",
        "stages",
        "side_effect",
        "aliases",
        "conflicts",
        "context_cost",
        "capability_fingerprint",
    ):
        if getattr(before, field_name) != getattr(after, field_name):
            semantic_fields.append(field_name)
    if semantic_fields:
        changes.append((DriftKind.SEMANTIC_METADATA, tuple(semantic_fields)))
    if before.requirements != after.requirements or before.compatibility.value != after.compatibility.value:
        changes.append((DriftKind.TOOL_SCHEMA, ("requirements", "compatibility")))
    if before.auth_state.value != after.auth_state.value:
        changes.append((DriftKind.AUTH, ("auth_state",)))
    if before.eligibility.value != after.eligibility.value:
        changes.append((DriftKind.POLICY, ("eligibility",)))
    runtime_fields = tuple(
        field_name
        for field_name in ("presence", "exposure")
        if getattr(before, field_name).value != getattr(after, field_name).value
    )
    if runtime_fields:
        changes.append((DriftKind.RUNTIME_EXPOSURE, runtime_fields))
    return [
        _build_drift(
            previous.snapshot_id,
            current.snapshot_id,
            after.canonical_id,
            kind,
            changed_fields,
            before.capability_fingerprint,
            after.capability_fingerprint,
            current.created_at,
        )
        for kind, changed_fields in changes
    ]


def compare_snapshots(
    previous: CapabilitySnapshot,
    current: CapabilitySnapshot,
) -> tuple[CapabilityDrift, ...]:
    """比較 canonical identity，再產生穩定排序的 typed drift。"""

    before_by_id = {item.canonical_id: item for item in previous.capabilities}
    after_by_id = {item.canonical_id: item for item in current.capabilities}
    removed = set(before_by_id) - set(after_by_id)
    added = set(after_by_id) - set(before_by_id)
    drifts: list[CapabilityDrift] = []

    consumed_removed: set[str] = set()
    consumed_added: set[str] = set()
    for old_id in sorted(removed):
        for new_id in sorted(added):
            if new_id in consumed_added:
                continue
            before = before_by_id[old_id]
            after = after_by_id[new_id]
            if _is_rename(before, after):
                drifts.append(_build_drift(
                    previous.snapshot_id,
                    current.snapshot_id,
                    new_id,
                    DriftKind.RENAME,
                    ("canonical_id",),
                    before.capability_fingerprint,
                    after.capability_fingerprint,
                    current.created_at,
                ))
                consumed_removed.add(old_id)
                consumed_added.add(new_id)
                break

    for canonical_id in sorted(removed - consumed_removed):
        before = before_by_id[canonical_id]
        drifts.append(_build_drift(
            previous.snapshot_id,
            current.snapshot_id,
            canonical_id,
            DriftKind.REMOVE,
            ("capability",),
            before.capability_fingerprint,
            None,
            current.created_at,
        ))
    for canonical_id in sorted(added - consumed_added):
        after = after_by_id[canonical_id]
        drifts.append(_build_drift(
            previous.snapshot_id,
            current.snapshot_id,
            canonical_id,
            DriftKind.ADD,
            ("capability",),
            None,
            after.capability_fingerprint,
            current.created_at,
        ))
    for canonical_id in sorted(set(before_by_id) & set(after_by_id)):
        drifts.extend(_same_id_drifts(
            before_by_id[canonical_id],
            after_by_id[canonical_id],
            previous,
            current,
        ))
    return tuple(sorted(
        drifts,
        key=lambda item: (
            item.capability_id,
            _KIND_ORDER[item.kind],
            item.changed_fields,
            item.drift_id,
        ),
    ))
