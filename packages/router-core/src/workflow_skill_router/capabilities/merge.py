from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import re
from typing import Any

from workflow_skill_router.schemas.artifacts import canonical_json_bytes

from .availability import derive_availability
from .models import (
    AuthState,
    Capability,
    CapabilityKind,
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
from .providers import CapabilityObservation, ProviderResult


FIELD_AUTHORITY = {
    "presence": ("native-host", "plugin-handshake", "agent-runtime", "filesystem", "cache"),
    "exposure": ("native-host", "agent-runtime", "plugin-handshake", "cache", "filesystem"),
    "auth_state": ("native-host", "plugin-handshake", "agent-runtime", "cache", "filesystem"),
    "eligibility": ("native-host", "agent-runtime", "plugin-handshake", "filesystem", "cache"),
    "compatibility": ("plugin-handshake", "native-host", "agent-runtime", "filesystem", "cache"),
    "freshness": ("native-host", "plugin-handshake", "agent-runtime", "filesystem", "cache"),
    "display_name": ("filesystem", "plugin-handshake", "agent-runtime", "native-host", "cache"),
    "description": ("filesystem", "plugin-handshake", "agent-runtime", "native-host", "cache"),
    "domains": ("filesystem", "plugin-handshake", "agent-runtime", "native-host", "cache"),
    "stages": ("filesystem", "plugin-handshake", "agent-runtime", "native-host", "cache"),
    "side_effect": ("plugin-handshake", "native-host", "filesystem", "agent-runtime", "cache"),
    "requirements": ("plugin-handshake", "native-host", "filesystem", "agent-runtime", "cache"),
    "aliases": ("filesystem", "plugin-handshake", "agent-runtime", "native-host", "cache"),
    "conflicts": ("filesystem", "plugin-handshake", "agent-runtime", "native-host", "cache"),
    "context_cost": ("filesystem", "plugin-handshake", "agent-runtime", "native-host", "cache"),
    "capability_fingerprint": ("plugin-handshake", "filesystem", "native-host", "agent-runtime", "cache"),
    "installer_content_digest": ("native-host", "plugin-handshake", "filesystem", "agent-runtime", "cache"),
}

_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


class CapabilityMergeError(ValueError):
    """表示 provider observations 無法安全合併。"""


def _canonicalize(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise CapabilityMergeError("observation datetime 必須包含 timezone")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if is_dataclass(value):
        return {
            field.name: _canonicalize(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, tuple):
        return [_canonicalize(item) for item in value]
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _canonicalize(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise CapabilityMergeError(f"不支援的 observation value type: {type(value).__name__}")


def _authority_rank(field_name: str, provider: str) -> tuple[int, str]:
    order = FIELD_AUTHORITY[field_name]
    try:
        return order.index(provider), provider
    except ValueError:
        return len(order), provider


def _entry_key(
    field_name: str,
    entry: tuple[ProviderResult, CapabilityObservation, FieldObservation[Any]],
) -> tuple[object, ...]:
    result, observation, field = entry
    return (
        *_authority_rank(field_name, field.provider),
        -field.observed_at.timestamp(),
        result.provider_id,
        observation.source,
        field.reason_code,
        canonical_json_bytes({"value": _canonicalize(field.value)}),
    )


def _trusted_installer_observation(field: FieldObservation[Any]) -> bool:
    if not isinstance(field.value, str) or not _DIGEST_PATTERN.fullmatch(field.value):
        return False
    if (
        field.provider == "filesystem"
        and field.trust_level is TrustLevel.HANDSHAKE
        and field.reason_code == "trusted-installer-manifest"
    ):
        return True
    if field.provider in {"native-host", "plugin-handshake"}:
        return (
            field.trust_level in {TrustLevel.HANDSHAKE, TrustLevel.RUNTIME}
            and field.reason_code not in {
                "client-declared",
                "installer-content-unverified",
                "unknown",
            }
        )
    return False


def _unknown(
    value: object,
    now: datetime,
    reason_code: str,
) -> FieldObservation[Any]:
    return FieldObservation(value, "cache", now, TrustLevel.CACHE, reason_code)


def _select_entry(
    field_name: str,
    entries: tuple[tuple[ProviderResult, CapabilityObservation, FieldObservation[Any]], ...],
    now: datetime,
    default: object,
) -> tuple[ProviderResult | None, CapabilityObservation | None, FieldObservation[Any]]:
    candidates = tuple(entry for entry in entries if field_name in entry[1].fields)
    if field_name == "installer_content_digest":
        trusted = tuple(
            entry
            for entry in candidates
            if _trusted_installer_observation(entry[1].fields[field_name])
        )
        if trusted:
            candidates = trusted
        else:
            return None, None, _unknown(default, now, "installer-content-unverified")
    if not candidates:
        return None, None, _unknown(default, now, f"{field_name}-unobserved")
    normalized = tuple(
        (result, observation, observation.fields[field_name])
        for result, observation, _ in candidates
    )
    return min(normalized, key=lambda item: _entry_key(field_name, item))


def _observation_digest(field_name: str, value: FieldObservation[Any]) -> str:
    payload = {
        "field": field_name,
        "value": _canonicalize(value.value),
        "provider": value.provider,
        "observed_at": _canonicalize(value.observed_at),
        "trust_level": value.trust_level.value,
        "reason_code": value.reason_code,
    }
    return "sha256:" + hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _provenance(
    entries: tuple[tuple[ProviderResult, CapabilityObservation, FieldObservation[Any]], ...],
) -> tuple[ProvenanceRecord, ...]:
    records: dict[tuple[str, ...], ProvenanceRecord] = {}
    for result, observation, _ in entries:
        for field_name, field in observation.fields.items():
            digest = _observation_digest(field_name, field)
            key = (
                result.provider_id,
                observation.source,
                result.revision,
                digest,
                field.trust_level.value,
                field.reason_code,
            )
            records[key] = ProvenanceRecord(
                provider_id=result.provider_id,
                source_kind=observation.source,
                source_ref_digest=result.revision,
                observation_digest=digest,
                trust_level=field.trust_level,
                reason_code=field.reason_code,
            )
    return tuple(records[key] for key in sorted(records))


def _typed_value(
    field: FieldObservation[Any],
    expected_type: type[Any],
    field_name: str,
) -> Any:
    if expected_type is int:
        if isinstance(field.value, bool) or not isinstance(field.value, int):
            raise CapabilityMergeError(f"{field_name} observation type mismatch")
    elif not isinstance(field.value, expected_type):
        raise CapabilityMergeError(f"{field_name} observation type mismatch")
    return field.value


def _tuple_value(
    field: FieldObservation[Any],
    item_type: type[Any],
    field_name: str,
) -> tuple[Any, ...]:
    if not isinstance(field.value, tuple) or not all(
        isinstance(item, item_type) for item in field.value
    ):
        raise CapabilityMergeError(f"{field_name} observation type mismatch")
    return field.value


def _typed_observation(
    field: FieldObservation[Any],
    expected_type: type[Any],
    field_name: str,
) -> FieldObservation[Any]:
    _typed_value(field, expected_type, field_name)
    return field


def _materialize(
    canonical_id: str,
    grouped: tuple[tuple[ProviderResult, CapabilityObservation, FieldObservation[Any]], ...],
    now: datetime,
) -> Capability:
    observations = tuple(entry[1] for entry in grouped)
    kinds = {item.kind for item in observations}
    if len(kinds) != 1 or not all(isinstance(kind, CapabilityKind) for kind in kinds):
        raise CapabilityMergeError(f"{canonical_id} kind conflict")

    selected: dict[str, tuple[ProviderResult | None, CapabilityObservation | None, FieldObservation[Any]]] = {}
    defaults = {
        "display_name": canonical_id.rsplit("/", 1)[-1],
        "description": "",
        "presence": Presence.UNKNOWN,
        "exposure": Exposure.UNKNOWN,
        "auth_state": AuthState.UNKNOWN,
        "eligibility": Eligibility.UNKNOWN,
        "compatibility": Compatibility.UNKNOWN,
        "freshness": Freshness(now, now, False, True),
        "domains": (),
        "stages": (),
        "side_effect": SideEffect.NONE,
        "requirements": (),
        "aliases": (),
        "conflicts": (),
        "context_cost": 0,
        "capability_fingerprint": "unknown",
        "installer_content_digest": "unknown",
    }
    for field_name, default in defaults.items():
        selected[field_name] = _select_entry(field_name, grouped, now, default)

    source_observation = selected["display_name"][1]
    source = source_observation.source if source_observation else sorted(item.source for item in observations)[0]
    if not isinstance(source, str) or not source:
        raise CapabilityMergeError(f"{canonical_id} source type mismatch")
    provisional = Capability(
        canonical_id=canonical_id,
        display_name=_typed_value(selected["display_name"][2], str, "display_name"),
        kind=next(iter(kinds)),
        source=source,
        presence=_typed_observation(selected["presence"][2], Presence, "presence"),
        exposure=_typed_observation(selected["exposure"][2], Exposure, "exposure"),
        auth_state=_typed_observation(selected["auth_state"][2], AuthState, "auth_state"),
        eligibility=_typed_observation(selected["eligibility"][2], Eligibility, "eligibility"),
        compatibility=_typed_observation(
            selected["compatibility"][2],
            Compatibility,
            "compatibility",
        ),
        freshness=_typed_value(selected["freshness"][2], Freshness, "freshness"),
        description=_typed_value(selected["description"][2], str, "description"),
        domains=_tuple_value(selected["domains"][2], str, "domains"),
        stages=_tuple_value(selected["stages"][2], str, "stages"),
        side_effect=_typed_value(selected["side_effect"][2], SideEffect, "side_effect"),
        requirements=_tuple_value(selected["requirements"][2], Requirement, "requirements"),
        aliases=_tuple_value(selected["aliases"][2], str, "aliases"),
        conflicts=_tuple_value(selected["conflicts"][2], str, "conflicts"),
        context_cost=_typed_value(selected["context_cost"][2], int, "context_cost"),
        capability_fingerprint=_typed_value(
            selected["capability_fingerprint"][2],
            str,
            "capability_fingerprint",
        ),
        installer_content_digest=_typed_observation(
            selected["installer_content_digest"][2],
            str,
            "installer_content_digest",
        ),
        availability_by_risk=(),
        provenance=_provenance(grouped),
    )
    availability_by_risk = tuple(
        RiskAvailability(risk, derive_availability(provisional, risk, now))
        for risk in RiskLevel
    )
    return replace(provisional, availability_by_risk=availability_by_risk)


def merge_observations(
    results: tuple[ProviderResult, ...],
    risk: RiskLevel,
    now: datetime,
) -> tuple[Capability, ...]:
    """以固定欄位 authority 合併 provider observations。"""

    if not isinstance(risk, RiskLevel):
        raise TypeError("risk 必須是 RiskLevel")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now 必須包含 timezone")
    grouped: dict[
        str,
        list[tuple[ProviderResult, CapabilityObservation, FieldObservation[Any]]],
    ] = {}
    for result in results:
        for observation in result.observations:
            sentinel = next(iter(observation.fields.values()), _unknown("unknown", now, "empty"))
            grouped.setdefault(observation.canonical_id, []).append(
                (result, observation, sentinel)
            )
    return tuple(
        _materialize(canonical_id, tuple(grouped[canonical_id]), now)
        for canonical_id in sorted(grouped)
    )
