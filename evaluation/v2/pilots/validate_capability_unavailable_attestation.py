from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any


SCHEMA_VERSION = "workflow-skill-router/capability-unavailable-attestation/1.0"
RECORD_TYPE = "reviewed-capability-unavailable-attestation"
EVIDENCE_LANE = "capability-unavailable"
CLAIM_BOUNDARY = "unavailable-evidence-only-not-a-verified-host-pilot"
AUTHORITY_BOUNDARY = "real-host-apis-absent"
SAFE_DIAGNOSTIC = "verified-host-capability-unavailable"
RUNTIME_BINDING = {
    "runtime_profile": "bundled-local-r0",
    "conformance_profile": None,
    "fallback_mode": "skill-only-fallback",
}
RUNTIME_PACKAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
CHECKED_CAPABILITIES = frozenset({"sync_runtime_context", "validate_route"})
SOURCE_REVISION = re.compile(r"^git:[0-9a-f]{7,64}$")
REVIEWER = re.compile(
    r"^reviewer:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
CANONICAL_UTC = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    code: str

    def public_dict(self) -> dict[str, object]:
        return {"valid": self.valid, "code": self.code}


def _invalid(code: str) -> ValidationResult:
    return ValidationResult(False, code)


def _has_exact_keys(value: object, expected: frozenset[str]) -> bool:
    return isinstance(value, Mapping) and set(value) == expected


def _canonical_utc(value: object) -> bool:
    if not isinstance(value, str) or CANONICAL_UTC.fullmatch(value) is None:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def validate_attestation(record: object) -> ValidationResult:
    """驗證可公開的 Host capability-unavailable 審查證明，不讀取或輸出原始證據。"""

    if isinstance(record, Mapping) and "reviewer" not in record:
        return _invalid("capability-unavailable-reviewer-invalid")
    if isinstance(record, Mapping) and "timestamp" not in record:
        return _invalid("capability-unavailable-timestamp-invalid")

    expected_top_level = frozenset({
        "schema_version",
        "record_type",
        "attestation_status",
        "evidence_lane",
        "claim_boundary",
        "checked_capability",
        "source_revision",
        "runtime",
        "authority_boundary",
        "safe_diagnostic",
        "reviewer",
        "timestamp",
        "claims",
    })
    if not _has_exact_keys(record, expected_top_level):
        return _invalid("capability-unavailable-structure-invalid")
    assert isinstance(record, Mapping)

    if record.get("schema_version") != SCHEMA_VERSION or record.get("record_type") != RECORD_TYPE:
        return _invalid("capability-unavailable-structure-invalid")
    if record.get("attestation_status") != "reviewed":
        return _invalid("capability-unavailable-review-status-invalid")
    if record.get("evidence_lane") != EVIDENCE_LANE:
        return _invalid("capability-unavailable-evidence-lane-invalid")
    if record.get("claim_boundary") != CLAIM_BOUNDARY:
        return _invalid("capability-unavailable-claim-boundary-invalid")

    capability = record.get("checked_capability")
    if not _has_exact_keys(capability, frozenset({"id", "authority_requirement"})):
        return _invalid("capability-unavailable-capability-invalid")
    assert isinstance(capability, Mapping)
    if (
        capability.get("id") not in CHECKED_CAPABILITIES
        or capability.get("authority_requirement") != "verified-host-required"
    ):
        return _invalid("capability-unavailable-capability-invalid")

    source_revision = record.get("source_revision")
    if not isinstance(source_revision, str) or SOURCE_REVISION.fullmatch(source_revision) is None:
        return _invalid("capability-unavailable-source-binding-invalid")
    runtime = record.get("runtime")
    if not _has_exact_keys(runtime, frozenset({*RUNTIME_BINDING, "runtime_package_digest"})):
        return _invalid("capability-unavailable-runtime-binding-invalid")
    assert isinstance(runtime, Mapping)
    if (
        any(runtime.get(field) != expected for field, expected in RUNTIME_BINDING.items())
        or not isinstance(runtime.get("runtime_package_digest"), str)
        or RUNTIME_PACKAGE_DIGEST.fullmatch(runtime["runtime_package_digest"]) is None
    ):
        return _invalid("capability-unavailable-runtime-binding-invalid")
    if record.get("authority_boundary") != AUTHORITY_BOUNDARY:
        return _invalid("capability-unavailable-authority-boundary-invalid")
    if record.get("safe_diagnostic") != SAFE_DIAGNOSTIC:
        return _invalid("capability-unavailable-diagnostic-invalid")

    reviewer = record.get("reviewer")
    if not isinstance(reviewer, str) or REVIEWER.fullmatch(reviewer) is None:
        return _invalid("capability-unavailable-reviewer-invalid")
    if not _canonical_utc(record.get("timestamp")):
        return _invalid("capability-unavailable-timestamp-invalid")

    claims = record.get("claims")
    if not _has_exact_keys(claims, frozenset({"verified_host_pilot", "production_authority", "hybrid_full"})):
        return _invalid("capability-unavailable-claim-boundary-invalid")
    assert isinstance(claims, Mapping)
    if any(claims.get(field) is not False for field in claims):
        return _invalid("capability-unavailable-claim-boundary-invalid")

    return ValidationResult(True, "capability-unavailable-attestation-valid")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a public-safe reviewed capability-unavailable attestation."
    )
    parser.add_argument("--record", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        record: Any = json.loads(args.record.read_text(encoding="utf-8"))
        result = validate_attestation(record)
    except Exception:
        result = _invalid("capability-unavailable-input-invalid")
    print(json.dumps(result.public_dict(), sort_keys=True, separators=(",", ":")))
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
