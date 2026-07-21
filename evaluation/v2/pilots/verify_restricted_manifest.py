from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import hmac
import json
from pathlib import Path
import re
from typing import Any


SPECIFICATION = "wsr-beta5-pilot-hmac-v1"
MESSAGE_PREFIX = b"workflow-skill-router/beta5-pilot/v1"
SCHEMA_VERSION = "workflow-skill-router/restricted-pilot-binding-manifest/1.0"
EXECUTION_STATUS = "restricted-binding-frozen-before-task-1"
COMMITMENT = re.compile(r"^hmac-sha256:[0-9a-f]{64}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
RUN_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{7,127}$")
TASK_IDENTITY = re.compile(r"^task:[A-Za-z0-9_-]{16,128}$")
SOURCE_IDENTITY = re.compile(r"^source:[A-Za-z0-9_-]{16,128}$")
PROFILE_IDENTITY = re.compile(r"^profile:[A-Za-z0-9_-]{16,128}$")
REVIEWER_IDENTITY = re.compile(r"^reviewer:[A-Za-z0-9_-]{12,128}$")
CANONICAL_UTC = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)


def _slot_specs() -> tuple[tuple[str, bool, bool, bool, bool], ...]:
    return (
        *((f"single-{index:02d}", False, True, False, False) for index in range(1, 7)),
        *((f"phased-{index:02d}", True, False, index <= 4, True) for index in range(1, 9)),
        *((f"goal-{index:02d}", False, index <= 4, False, index >= 5) for index in range(1, 7)),
    )


SLOT_SPECS = _slot_specs()
DOMAIN_LABELS = frozenset({
    "task-identity",
    "source-identity",
    "profile-identity",
    "binding-record",
    "task-set",
    "reviewer-attestation",
    "binding-manifest",
})


@dataclass(frozen=True, slots=True)
class VerificationResult:
    valid: bool
    code: str

    def public_dict(self) -> dict[str, object]:
        return {"valid": self.valid, "code": self.code}


def boolean_field(value: bool) -> str:
    if type(value) is not bool:
        raise ValueError("boolean-field-invalid")
    return "true" if value else "false"


def _length_prefixed(value: str) -> bytes:
    if not isinstance(value, str):
        raise ValueError("commitment-field-invalid")
    encoded = value.encode("utf-8", errors="strict")
    return str(len(encoded)).encode("ascii") + b":" + encoded


def compute_commitment(
    secret: bytes,
    domain_label: str,
    fields: Sequence[str],
) -> str:
    if not isinstance(secret, bytes) or len(secret) != 32:
        raise ValueError("run-secret-invalid")
    if domain_label not in DOMAIN_LABELS:
        raise ValueError("commitment-domain-invalid")
    domain = domain_label.encode("utf-8", errors="strict")
    message = MESSAGE_PREFIX + b"\x00" + domain + b"\x00"
    message += b"".join(_length_prefixed(field) for field in fields)
    return "hmac-sha256:" + hmac.new(secret, message, sha256).hexdigest()


def _exact_keys(value: object, expected: frozenset[str]) -> bool:
    return isinstance(value, Mapping) and set(value) == expected


def _matches(pattern: re.Pattern[str], value: object) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _same(left: object, right: str) -> bool:
    return isinstance(left, str) and hmac.compare_digest(left, right)


def _invalid(code: str) -> VerificationResult:
    return VerificationResult(False, code)


def _canonical_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or CANONICAL_UTC.fullmatch(value) is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def verify_manifest(manifest: object, secret: bytes) -> VerificationResult:
    if not isinstance(secret, bytes) or len(secret) != 32:
        return _invalid("pilot-binding-secret-invalid")
    top_keys = frozenset({
        "schema_version",
        "execution_status",
        "run_id",
        "frozen_at",
        "protocol_digest",
        "source_revision",
        "runtime_package_digest",
        "commitment_scheme",
        "bindings",
        "task_set_commitment",
        "binding_manifest_commitment",
        "reviewer_attestation",
    })
    if not _exact_keys(manifest, top_keys):
        return _invalid("pilot-binding-structure-invalid")
    assert isinstance(manifest, Mapping)
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("execution_status") != EXECUTION_STATUS
        or not _matches(RUN_ID, manifest.get("run_id"))
        or not isinstance(manifest.get("source_revision"), str)
        or not 7 <= len(manifest["source_revision"]) <= 128
        or not _matches(DIGEST, manifest.get("protocol_digest"))
        or not _matches(DIGEST, manifest.get("runtime_package_digest"))
    ):
        return _invalid("pilot-binding-structure-invalid")
    frozen_at = _canonical_utc(manifest.get("frozen_at"))
    if frozen_at is None:
        return _invalid("pilot-binding-frozen-at-invalid")
    scheme = manifest.get("commitment_scheme")
    if not _exact_keys(
        scheme,
        frozenset({
            "specification",
            "secret_length_bytes",
            "secret_storage",
            "publicly_reversible",
        }),
    ):
        return _invalid("pilot-binding-structure-invalid")
    assert isinstance(scheme, Mapping)
    if scheme != {
        "specification": SPECIFICATION,
        "secret_length_bytes": 32,
        "secret_storage": "restricted-reviewer-access-only",
        "publicly_reversible": False,
    }:
        return _invalid("pilot-binding-structure-invalid")

    bindings = manifest.get("bindings")
    if not isinstance(bindings, list) or len(bindings) != len(SLOT_SPECS):
        return _invalid("pilot-binding-slot-order-invalid")
    task_commitments: set[str] = set()
    task_identities: set[str] = set()
    source_identities: set[str] = set()
    task_source_pairs: set[tuple[str, str]] = set()
    record_commitments: list[str] = []
    record_keys = frozenset({
        "slot_id",
        "task_identity",
        "task_identity_commitment",
        "source_identity",
        "source_identity_commitment",
        "profile_binding",
        "metric_population_flags",
        "record_integrity_commitment",
    })
    flag_keys = frozenset({
        "manual_envelope",
        "no_explicit_skill",
        "explicit_lock",
        "router_local_resume",
    })

    for record, spec in zip(bindings, SLOT_SPECS, strict=True):
        slot_id, profile_backed, no_explicit, explicit_lock, resume = spec
        if not _exact_keys(record, record_keys):
            return _invalid("pilot-binding-structure-invalid")
        assert isinstance(record, Mapping)
        if record.get("slot_id") != slot_id:
            return _invalid("pilot-binding-slot-order-invalid")
        if (
            not _matches(TASK_IDENTITY, record.get("task_identity"))
            or not _matches(SOURCE_IDENTITY, record.get("source_identity"))
            or not _matches(COMMITMENT, record.get("task_identity_commitment"))
            or not _matches(COMMITMENT, record.get("source_identity_commitment"))
            or not _matches(COMMITMENT, record.get("record_integrity_commitment"))
        ):
            return _invalid("pilot-binding-structure-invalid")
        task_identity = str(record["task_identity"])
        if task_identity in task_identities:
            return _invalid("pilot-binding-task-duplicate")
        task_identities.add(task_identity)
        source_identity = str(record["source_identity"])
        if source_identity in source_identities:
            return _invalid("pilot-binding-source-duplicate")
        source_identities.add(source_identity)

        profile = record.get("profile_binding")
        profile_commitment = ""
        profile_revision = ""
        if profile_backed:
            profile_keys = frozenset({
                "profile_backed",
                "profile_id",
                "profile_revision_digest",
                "profile_identity_commitment",
            })
            if not _exact_keys(profile, profile_keys):
                return _invalid("pilot-binding-profile-invalid")
            assert isinstance(profile, Mapping)
            if (
                profile.get("profile_backed") is not True
                or not _matches(PROFILE_IDENTITY, profile.get("profile_id"))
                or not _matches(DIGEST, profile.get("profile_revision_digest"))
                or not _matches(COMMITMENT, profile.get("profile_identity_commitment"))
            ):
                return _invalid("pilot-binding-profile-invalid")
            profile_revision = str(profile["profile_revision_digest"])
            profile_commitment = compute_commitment(
                secret,
                "profile-identity",
                (
                    str(manifest["run_id"]),
                    slot_id,
                    str(profile["profile_id"]),
                    profile_revision,
                ),
            )
            if not _same(profile.get("profile_identity_commitment"), profile_commitment):
                return _invalid("pilot-binding-profile-commitment-invalid")
        elif profile != {"profile_backed": False}:
            return _invalid("pilot-binding-profile-invalid")

        flags = record.get("metric_population_flags")
        if not _exact_keys(flags, flag_keys):
            return _invalid("pilot-binding-population-invalid")
        assert isinstance(flags, Mapping)
        if any(type(flags.get(key)) is not bool for key in flag_keys):
            return _invalid("pilot-binding-population-invalid")
        expected_flags = {
            "manual_envelope": True,
            "no_explicit_skill": no_explicit,
            "explicit_lock": explicit_lock,
            "router_local_resume": resume,
        }
        if dict(flags) != expected_flags or (
            flags.get("no_explicit_skill") is True
            and flags.get("explicit_lock") is True
        ):
            return _invalid("pilot-binding-population-invalid")

        task_commitment = compute_commitment(
            secret,
            "task-identity",
            (
                str(manifest["run_id"]),
                slot_id,
                task_identity,
            ),
        )
        if not _same(record.get("task_identity_commitment"), task_commitment):
            return _invalid("pilot-binding-task-commitment-invalid")
        source_commitment = compute_commitment(
            secret,
            "source-identity",
            (
                str(manifest["run_id"]),
                slot_id,
                source_identity,
            ),
        )
        if not _same(record.get("source_identity_commitment"), source_commitment):
            return _invalid("pilot-binding-source-commitment-invalid")
        if task_commitment in task_commitments:
            return _invalid("pilot-binding-task-duplicate")
        pair = (task_commitment, source_commitment)
        if pair in task_source_pairs:
            return _invalid("pilot-binding-task-source-duplicate")
        task_commitments.add(task_commitment)
        task_source_pairs.add(pair)

        record_commitment = compute_commitment(
            secret,
            "binding-record",
            (
                str(manifest["run_id"]),
                slot_id,
                task_commitment,
                source_commitment,
                profile_commitment,
                profile_revision,
                boolean_field(flags["manual_envelope"]),
                boolean_field(flags["no_explicit_skill"]),
                boolean_field(flags["explicit_lock"]),
                boolean_field(flags["router_local_resume"]),
            ),
        )
        if not _same(record.get("record_integrity_commitment"), record_commitment):
            return _invalid("pilot-binding-record-commitment-invalid")
        record_commitments.append(record_commitment)

    task_set_commitment = compute_commitment(
        secret,
        "task-set",
        (str(manifest["run_id"]), *record_commitments),
    )
    if not _same(manifest.get("task_set_commitment"), task_set_commitment):
        return _invalid("pilot-binding-task-set-invalid")

    reviewer = manifest.get("reviewer_attestation")
    reviewer_keys = frozenset({
        "reviewer_id",
        "attested_at",
        "reviewed_before_task_1",
        "real_task_status_human_reviewed",
        "commitments_verified_with_run_secret",
        "reviewer_attestation_commitment",
    })
    if not _exact_keys(reviewer, reviewer_keys):
        return _invalid("pilot-binding-review-invalid")
    assert isinstance(reviewer, Mapping)
    if (
        not _matches(REVIEWER_IDENTITY, reviewer.get("reviewer_id"))
        or reviewer.get("reviewed_before_task_1") is not True
        or reviewer.get("real_task_status_human_reviewed") is not True
        or reviewer.get("commitments_verified_with_run_secret") is not True
        or not _matches(COMMITMENT, reviewer.get("reviewer_attestation_commitment"))
    ):
        return _invalid("pilot-binding-review-invalid")
    attested_at = _canonical_utc(reviewer.get("attested_at"))
    if attested_at is None:
        return _invalid("pilot-binding-attested-at-invalid")
    if attested_at > frozen_at:
        return _invalid("pilot-binding-attestation-order-invalid")
    reviewer_commitment = compute_commitment(
        secret,
        "reviewer-attestation",
        (
            str(manifest["run_id"]),
            str(manifest["source_revision"]),
            str(manifest["runtime_package_digest"]),
            str(manifest["protocol_digest"]),
            task_set_commitment,
            str(reviewer["reviewer_id"]),
            str(reviewer["attested_at"]),
            boolean_field(True),
            boolean_field(True),
            boolean_field(True),
        ),
    )
    if not _same(reviewer.get("reviewer_attestation_commitment"), reviewer_commitment):
        return _invalid("pilot-binding-review-invalid")

    manifest_commitment = compute_commitment(
        secret,
        "binding-manifest",
        (
            str(manifest["run_id"]),
            str(manifest["frozen_at"]),
            str(manifest["source_revision"]),
            str(manifest["runtime_package_digest"]),
            str(manifest["protocol_digest"]),
            task_set_commitment,
            reviewer_commitment,
            *record_commitments,
        ),
    )
    if not _same(manifest.get("binding_manifest_commitment"), manifest_commitment):
        return _invalid("pilot-binding-manifest-commitment-invalid")
    return VerificationResult(True, "pilot-binding-valid")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a restricted beta.5 Pilot binding manifest.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--secret-file", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest: Any = json.loads(args.manifest.read_text(encoding="utf-8"))
        secret = args.secret_file.read_bytes()
        result = verify_manifest(manifest, secret)
    except Exception:
        result = _invalid("pilot-binding-input-invalid")
    print(json.dumps(result.public_dict(), sort_keys=True, separators=(",", ":")))
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
