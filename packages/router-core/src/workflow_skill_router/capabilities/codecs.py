from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from workflow_skill_router.schemas.artifacts import ArtifactEnvelope
from workflow_skill_router.schemas.errors import SchemaRegistryError

from .models import (
    AuthState,
    Availability,
    AvailabilityResult,
    Capability,
    CapabilityKind,
    CapabilitySnapshot,
    Compatibility,
    Eligibility,
    Exposure,
    FieldObservation,
    Freshness,
    Presence,
    ProvenanceRecord,
    Requirement,
    RiskAvailability,
    RiskLevel,
    SideEffect,
    TrustLevel,
)


SCHEMA_VERSION = "2.0.0-alpha.1"
CAPABILITY_SCHEMA_ID = "workflow-skill-router/capability"
CAPABILITY_SNAPSHOT_SCHEMA_ID = "workflow-skill-router/capability-snapshot"

_ENVELOPE_FIELDS = frozenset({
    "schema_id",
    "schema_version",
    "artifact_kind",
    "artifact_id",
    "created_at",
    "payload",
})
_CAPABILITY_FIELDS = frozenset({
    "canonical_id",
    "display_name",
    "kind",
    "source",
    "presence",
    "exposure",
    "auth_state",
    "eligibility",
    "compatibility",
    "freshness",
    "description",
    "domains",
    "stages",
    "side_effect",
    "requirements",
    "aliases",
    "conflicts",
    "context_cost",
    "capability_fingerprint",
    "installer_content_digest",
    "availability_by_risk",
    "provenance",
})
_SNAPSHOT_FIELDS = frozenset({
    "snapshot_id",
    "schema_version",
    "created_at",
    "runtime_fingerprint",
    "provider_revisions",
    "capabilities",
    "drift_from_snapshot_id",
    "freshness",
})
_OBSERVATION_FIELDS = frozenset({
    "value",
    "provider",
    "observed_at",
    "trust_level",
    "reason_code",
})
_FRESHNESS_FIELDS = frozenset({
    "observed_at",
    "expires_at",
    "degraded_allowed",
    "stale",
})
_REQUIREMENT_FIELDS = frozenset({"canonical_id", "kind", "purpose", "trusted"})
_AVAILABILITY_RESULT_FIELDS = frozenset({"primary", "reasons"})
_RISK_AVAILABILITY_FIELDS = frozenset({"risk", "result"})
_PROVENANCE_FIELDS = frozenset({
    "provider_id",
    "source_kind",
    "source_ref_digest",
    "observation_digest",
    "trust_level",
    "reason_code",
})


def _exact_mapping(
    value: object,
    expected: frozenset[str],
    context: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaRegistryError(f"{context} must be object")
    keys = {str(key) for key in value}
    missing = sorted(expected - keys)
    if missing:
        raise SchemaRegistryError(f"{context} missing field: {', '.join(missing)}")
    unknown = sorted(keys - expected)
    if unknown:
        raise SchemaRegistryError(f"{context} unknown field: {', '.join(unknown)}")
    return value


def _string(value: object, context: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise SchemaRegistryError(f"{context} must be non-empty string")
    return value


def _optional_string(value: object, context: str) -> str | None:
    if value is None:
        return None
    return _string(value, context)


def _boolean(value: object, context: str) -> bool:
    if not isinstance(value, bool):
        raise SchemaRegistryError(f"{context} must be boolean")
    return value


def _integer(value: object, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SchemaRegistryError(f"{context} must be non-negative integer")
    return value


def _list(value: object, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise SchemaRegistryError(f"{context} must be array")
    return value


def _string_tuple(value: object, context: str) -> tuple[str, ...]:
    return tuple(
        _string(item, f"{context}[{index}]")
        for index, item in enumerate(_list(value, context))
    )


def _enum(enum_type: type[StrEnum], value: object, context: str) -> StrEnum:
    candidate = _string(value, context)
    try:
        return enum_type(candidate)
    except ValueError as error:
        raise SchemaRegistryError(f"{context} has invalid value: {candidate}") from error


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime 必須包含 timezone")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: object, context: str) -> datetime:
    text = _string(value, context)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise SchemaRegistryError(f"{context} must be ISO-8601 datetime") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SchemaRegistryError(f"{context} must include timezone")
    return parsed


def _canonical_timestamp(value: object, context: str) -> str:
    text = _string(value, context)
    canonical = _format_datetime(_parse_datetime(text, context))
    if text != canonical:
        raise SchemaRegistryError(f"{context} must use canonical UTC timestamp")
    return canonical


def _encode_observation(value: FieldObservation[Any]) -> dict[str, object]:
    observed_value = value.value.value if isinstance(value.value, StrEnum) else value.value
    return {
        "value": observed_value,
        "provider": value.provider,
        "observed_at": _format_datetime(value.observed_at),
        "trust_level": value.trust_level.value,
        "reason_code": value.reason_code,
    }


def _decode_observation(
    value: object,
    value_type: type[StrEnum] | None,
    context: str,
) -> FieldObservation[Any]:
    document = _exact_mapping(value, _OBSERVATION_FIELDS, context)
    raw_value: object
    if value_type is None:
        raw_value = _string(document["value"], f"{context}.value")
    else:
        raw_value = _enum(value_type, document["value"], f"{context}.value")
    return FieldObservation(
        value=raw_value,
        provider=_string(document["provider"], f"{context}.provider"),
        observed_at=_parse_datetime(document["observed_at"], f"{context}.observed_at"),
        trust_level=TrustLevel(_enum(
            TrustLevel,
            document["trust_level"],
            f"{context}.trust_level",
        )),
        reason_code=_string(document["reason_code"], f"{context}.reason_code"),
    )


def _encode_freshness(value: Freshness) -> dict[str, object]:
    return {
        "observed_at": _format_datetime(value.observed_at),
        "expires_at": _format_datetime(value.expires_at),
        "degraded_allowed": value.degraded_allowed,
        "stale": value.stale,
    }


def _decode_freshness(value: object, context: str) -> Freshness:
    document = _exact_mapping(value, _FRESHNESS_FIELDS, context)
    observed_at = _parse_datetime(document["observed_at"], f"{context}.observed_at")
    expires_at = _parse_datetime(document["expires_at"], f"{context}.expires_at")
    if expires_at < observed_at:
        raise SchemaRegistryError(f"{context}.expires_at precedes observed_at")
    return Freshness(
        observed_at=observed_at,
        expires_at=expires_at,
        degraded_allowed=_boolean(
            document["degraded_allowed"],
            f"{context}.degraded_allowed",
        ),
        stale=_boolean(document["stale"], f"{context}.stale"),
    )


def _encode_requirement(value: Requirement) -> dict[str, object]:
    return {
        "canonical_id": value.canonical_id,
        "kind": value.kind.value,
        "purpose": value.purpose,
        "trusted": value.trusted,
    }


def _decode_requirement(value: object, context: str) -> Requirement:
    document = _exact_mapping(value, _REQUIREMENT_FIELDS, context)
    return Requirement(
        canonical_id=_string(document["canonical_id"], f"{context}.canonical_id"),
        kind=CapabilityKind(_enum(CapabilityKind, document["kind"], f"{context}.kind")),
        purpose=_string(document["purpose"], f"{context}.purpose"),
        trusted=_boolean(document["trusted"], f"{context}.trusted"),
    )


def _encode_availability_result(value: AvailabilityResult) -> dict[str, object]:
    return {"primary": value.primary.value, "reasons": list(value.reasons)}


def _decode_availability_result(value: object, context: str) -> AvailabilityResult:
    document = _exact_mapping(value, _AVAILABILITY_RESULT_FIELDS, context)
    return AvailabilityResult(
        primary=Availability(_enum(
            Availability,
            document["primary"],
            f"{context}.primary",
        )),
        reasons=_string_tuple(document["reasons"], f"{context}.reasons"),
    )


def _encode_risk_availability(value: RiskAvailability) -> dict[str, object]:
    return {"risk": value.risk.value, "result": _encode_availability_result(value.result)}


def _decode_risk_availability(value: object, context: str) -> RiskAvailability:
    document = _exact_mapping(value, _RISK_AVAILABILITY_FIELDS, context)
    return RiskAvailability(
        risk=RiskLevel(_enum(RiskLevel, document["risk"], f"{context}.risk")),
        result=_decode_availability_result(document["result"], f"{context}.result"),
    )


def _encode_provenance(value: ProvenanceRecord) -> dict[str, object]:
    return {
        "provider_id": value.provider_id,
        "source_kind": value.source_kind,
        "source_ref_digest": value.source_ref_digest,
        "observation_digest": value.observation_digest,
        "trust_level": value.trust_level.value,
        "reason_code": value.reason_code,
    }


def _decode_provenance(value: object, context: str) -> ProvenanceRecord:
    document = _exact_mapping(value, _PROVENANCE_FIELDS, context)
    return ProvenanceRecord(
        provider_id=_string(document["provider_id"], f"{context}.provider_id"),
        source_kind=_string(document["source_kind"], f"{context}.source_kind"),
        source_ref_digest=_string(
            document["source_ref_digest"],
            f"{context}.source_ref_digest",
        ),
        observation_digest=_string(
            document["observation_digest"],
            f"{context}.observation_digest",
        ),
        trust_level=TrustLevel(_enum(
            TrustLevel,
            document["trust_level"],
            f"{context}.trust_level",
        )),
        reason_code=_string(document["reason_code"], f"{context}.reason_code"),
    )


def _validate_risk_order(values: tuple[RiskAvailability, ...]) -> None:
    expected = tuple(RiskLevel)
    actual = tuple(item.risk for item in values)
    if actual != expected:
        raise SchemaRegistryError(
            "capability.availability_by_risk risk order must be R0,R1,R2,R3"
        )


def _encode_capability_payload(value: Capability) -> dict[str, object]:
    _validate_risk_order(value.availability_by_risk)
    return {
        "canonical_id": value.canonical_id,
        "display_name": value.display_name,
        "kind": value.kind.value,
        "source": value.source,
        "presence": _encode_observation(value.presence),
        "exposure": _encode_observation(value.exposure),
        "auth_state": _encode_observation(value.auth_state),
        "eligibility": _encode_observation(value.eligibility),
        "compatibility": _encode_observation(value.compatibility),
        "freshness": _encode_freshness(value.freshness),
        "description": value.description,
        "domains": list(value.domains),
        "stages": list(value.stages),
        "side_effect": value.side_effect.value,
        "requirements": [_encode_requirement(item) for item in value.requirements],
        "aliases": list(value.aliases),
        "conflicts": list(value.conflicts),
        "context_cost": value.context_cost,
        "capability_fingerprint": value.capability_fingerprint,
        "installer_content_digest": _encode_observation(value.installer_content_digest),
        "availability_by_risk": [
            _encode_risk_availability(item)
            for item in value.availability_by_risk
        ],
        "provenance": [_encode_provenance(item) for item in value.provenance],
    }


def _decode_capability_payload(value: object, context: str = "capability") -> Capability:
    document = _exact_mapping(value, _CAPABILITY_FIELDS, context)
    risk_values = tuple(
        _decode_risk_availability(item, f"{context}.availability_by_risk[{index}]")
        for index, item in enumerate(
            _list(document["availability_by_risk"], f"{context}.availability_by_risk")
        )
    )
    _validate_risk_order(risk_values)
    return Capability(
        canonical_id=_string(document["canonical_id"], f"{context}.canonical_id"),
        display_name=_string(document["display_name"], f"{context}.display_name"),
        kind=CapabilityKind(_enum(CapabilityKind, document["kind"], f"{context}.kind")),
        source=_string(document["source"], f"{context}.source"),
        presence=_decode_observation(document["presence"], Presence, f"{context}.presence"),
        exposure=_decode_observation(document["exposure"], Exposure, f"{context}.exposure"),
        auth_state=_decode_observation(document["auth_state"], AuthState, f"{context}.auth_state"),
        eligibility=_decode_observation(document["eligibility"], Eligibility, f"{context}.eligibility"),
        compatibility=_decode_observation(
            document["compatibility"],
            Compatibility,
            f"{context}.compatibility",
        ),
        freshness=_decode_freshness(document["freshness"], f"{context}.freshness"),
        description=_string(document["description"], f"{context}.description", allow_empty=True),
        domains=_string_tuple(document["domains"], f"{context}.domains"),
        stages=_string_tuple(document["stages"], f"{context}.stages"),
        side_effect=SideEffect(_enum(
            SideEffect,
            document["side_effect"],
            f"{context}.side_effect",
        )),
        requirements=tuple(
            _decode_requirement(item, f"{context}.requirements[{index}]")
            for index, item in enumerate(
                _list(document["requirements"], f"{context}.requirements")
            )
        ),
        aliases=_string_tuple(document["aliases"], f"{context}.aliases"),
        conflicts=_string_tuple(document["conflicts"], f"{context}.conflicts"),
        context_cost=_integer(document["context_cost"], f"{context}.context_cost"),
        capability_fingerprint=_string(
            document["capability_fingerprint"],
            f"{context}.capability_fingerprint",
        ),
        installer_content_digest=_decode_observation(
            document["installer_content_digest"],
            None,
            f"{context}.installer_content_digest",
        ),
        availability_by_risk=risk_values,
        provenance=tuple(
            _decode_provenance(item, f"{context}.provenance[{index}]")
            for index, item in enumerate(
                _list(document["provenance"], f"{context}.provenance")
            )
        ),
    )


def _decode_envelope(
    document: Mapping[str, Any],
    expected_schema_id: str,
    expected_kind: str,
) -> tuple[str, str, Mapping[str, Any]]:
    envelope = _exact_mapping(document, _ENVELOPE_FIELDS, "artifact envelope")
    schema_id = _string(envelope["schema_id"], "artifact envelope.schema_id")
    schema_version = _string(
        envelope["schema_version"],
        "artifact envelope.schema_version",
    )
    artifact_kind = _string(
        envelope["artifact_kind"],
        "artifact envelope.artifact_kind",
    )
    if (
        schema_id != expected_schema_id
        or schema_version != SCHEMA_VERSION
        or artifact_kind != expected_kind
    ):
        raise SchemaRegistryError("artifact envelope contract mismatch")
    artifact_id = _string(envelope["artifact_id"], "artifact envelope.artifact_id")
    created_at = _canonical_timestamp(
        envelope["created_at"],
        "artifact envelope.created_at",
    )
    payload = envelope["payload"]
    if not isinstance(payload, Mapping):
        raise SchemaRegistryError("artifact envelope.payload must be object")
    return artifact_id, created_at, payload


def encode_capability(value: Capability) -> ArtifactEnvelope:
    return ArtifactEnvelope(
        schema_id=CAPABILITY_SCHEMA_ID,
        schema_version=SCHEMA_VERSION,
        artifact_kind="capability",
        artifact_id=value.canonical_id,
        created_at=_format_datetime(value.freshness.observed_at),
        payload=_encode_capability_payload(value),
    )


def decode_capability(document: Mapping[str, Any]) -> Capability:
    artifact_id, _, payload = _decode_envelope(
        document,
        CAPABILITY_SCHEMA_ID,
        "capability",
    )
    capability = _decode_capability_payload(payload)
    if capability.canonical_id != artifact_id:
        raise SchemaRegistryError("capability artifact_id mismatch")
    return capability


def encode_snapshot(value: CapabilitySnapshot) -> ArtifactEnvelope:
    if value.schema_version != SCHEMA_VERSION:
        raise SchemaRegistryError("capability snapshot schema_version mismatch")
    created_at = _canonical_timestamp(value.created_at, "snapshot.created_at")
    return ArtifactEnvelope(
        schema_id=CAPABILITY_SNAPSHOT_SCHEMA_ID,
        schema_version=SCHEMA_VERSION,
        artifact_kind="capability-snapshot",
        artifact_id=value.snapshot_id,
        created_at=created_at,
        payload={
            "snapshot_id": value.snapshot_id,
            "schema_version": value.schema_version,
            "created_at": created_at,
            "runtime_fingerprint": value.runtime_fingerprint,
            "provider_revisions": list(value.provider_revisions),
            "capabilities": [
                _encode_capability_payload(item)
                for item in value.capabilities
            ],
            "drift_from_snapshot_id": value.drift_from_snapshot_id,
            "freshness": _encode_freshness(value.freshness),
        },
    )


def decode_snapshot(document: Mapping[str, Any]) -> CapabilitySnapshot:
    artifact_id, envelope_created_at, payload = _decode_envelope(
        document,
        CAPABILITY_SNAPSHOT_SCHEMA_ID,
        "capability-snapshot",
    )
    source = _exact_mapping(payload, _SNAPSHOT_FIELDS, "capability snapshot")
    snapshot_id = _string(source["snapshot_id"], "capability snapshot.snapshot_id")
    schema_version = _string(
        source["schema_version"],
        "capability snapshot.schema_version",
    )
    created_at = _canonical_timestamp(
        source["created_at"],
        "capability snapshot.created_at",
    )
    if snapshot_id != artifact_id:
        raise SchemaRegistryError("capability snapshot artifact_id mismatch")
    if schema_version != SCHEMA_VERSION:
        raise SchemaRegistryError("capability snapshot schema_version mismatch")
    if created_at != envelope_created_at:
        raise SchemaRegistryError("capability snapshot created_at mismatch")
    capabilities = tuple(
        _decode_capability_payload(item, f"capability snapshot.capabilities[{index}]")
        for index, item in enumerate(
            _list(source["capabilities"], "capability snapshot.capabilities")
        )
    )
    return CapabilitySnapshot(
        snapshot_id=snapshot_id,
        schema_version=schema_version,
        created_at=created_at,
        runtime_fingerprint=_string(
            source["runtime_fingerprint"],
            "capability snapshot.runtime_fingerprint",
        ),
        provider_revisions=_string_tuple(
            source["provider_revisions"],
            "capability snapshot.provider_revisions",
        ),
        capabilities=capabilities,
        drift_from_snapshot_id=_optional_string(
            source["drift_from_snapshot_id"],
            "capability snapshot.drift_from_snapshot_id",
        ),
        freshness=_decode_freshness(
            source["freshness"],
            "capability snapshot.freshness",
        ),
    )
