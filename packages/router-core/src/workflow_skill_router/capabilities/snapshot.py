from __future__ import annotations

from datetime import datetime, timezone
import hashlib

from workflow_skill_router.schemas.artifacts import canonical_json_bytes

from .codecs import SCHEMA_VERSION, encode_capability
from .merge import merge_observations
from .models import CapabilitySnapshot, Freshness, RiskLevel
from .providers import ProviderResult


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("snapshot datetime 必須包含 timezone")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _freshness_document(value: Freshness) -> dict[str, object]:
    return {
        "observed_at": _timestamp(value.observed_at),
        "expires_at": _timestamp(value.expires_at),
        "degraded_allowed": value.degraded_allowed,
        "stale": value.stale,
    }


def _identity_document(snapshot: CapabilitySnapshot) -> dict[str, object]:
    return {
        "schema_version": snapshot.schema_version,
        "created_at": snapshot.created_at,
        "runtime_fingerprint": snapshot.runtime_fingerprint,
        "provider_revisions": list(snapshot.provider_revisions),
        "capabilities": [
            encode_capability(item).to_dict()["payload"]
            for item in snapshot.capabilities
        ],
        "drift_from_snapshot_id": snapshot.drift_from_snapshot_id,
        "freshness": _freshness_document(snapshot.freshness),
    }


def rebuild_snapshot_id(snapshot: CapabilitySnapshot) -> str:
    """由 snapshot 的 frozen identity fields 重算 content address。"""

    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(_identity_document(snapshot))
    ).hexdigest()


def build_snapshot(
    results: tuple[ProviderResult, ...],
    runtime_fingerprint: str,
    previous: CapabilitySnapshot | None,
    now: datetime | None = None,
) -> CapabilitySnapshot:
    """建立順序無關、內容定址的 capability snapshot。"""

    created = now or datetime.now(timezone.utc)
    if created.tzinfo is None or created.utcoffset() is None:
        raise ValueError("now 必須包含 timezone")
    if not runtime_fingerprint:
        raise ValueError("runtime_fingerprint 不可為空")
    capabilities = merge_observations(results, RiskLevel.R0, created)
    raw_expires_at = min(
        (item.freshness.expires_at for item in capabilities),
        default=created,
    )
    stale = (
        not capabilities
        or raw_expires_at <= created
        or any(item.freshness.stale for item in capabilities)
    )
    freshness = Freshness(
        observed_at=created,
        expires_at=max(created, raw_expires_at),
        degraded_allowed=False,
        stale=stale,
    )
    provider_revisions = tuple(sorted(
        f"{item.provider_id}:{item.revision}"
        for item in results
    ))
    provisional = CapabilitySnapshot(
        snapshot_id="pending",
        schema_version=SCHEMA_VERSION,
        created_at=_timestamp(created),
        runtime_fingerprint=runtime_fingerprint,
        provider_revisions=provider_revisions,
        capabilities=capabilities,
        drift_from_snapshot_id=previous.snapshot_id if previous else None,
        freshness=freshness,
    )
    return CapabilitySnapshot(
        snapshot_id=rebuild_snapshot_id(provisional),
        schema_version=provisional.schema_version,
        created_at=provisional.created_at,
        runtime_fingerprint=provisional.runtime_fingerprint,
        provider_revisions=provisional.provider_revisions,
        capabilities=provisional.capabilities,
        drift_from_snapshot_id=provisional.drift_from_snapshot_id,
        freshness=provisional.freshness,
    )
