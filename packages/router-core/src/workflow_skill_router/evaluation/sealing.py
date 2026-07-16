from __future__ import annotations

from dataclasses import fields
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from workflow_skill_router.schemas.artifacts import canonical_json_bytes

from .contracts import (
    EvaluationIntegrityError, ScoringKey, ScoringSpec, SealedCasePaths, SealingRoots,
)


def _hash(value: Mapping[str, Any]) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _bytes(value: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def _write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    content = _bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise EvaluationIntegrityError("sealed_path_collision")
        return
    with path.open("xb") as handle:
        handle.write(content)


def seal_authoring_case(case: dict[str, object], roots: SealingRoots) -> SealedCasePaths:
    if set(case) != {"execution", "driver", "scoring"}:
        raise EvaluationIntegrityError("authoring_case_shape_invalid")
    public_identity = {"execution": case["execution"], "driver": case["driver"]}
    opaque_id = "case_" + _hash(public_identity)[:20]
    execution = {"opaque_run_case_id": opaque_id, **dict(case["execution"])}
    driver = {
        "driver_case_id": f"driver_{opaque_id}",
        "opaque_run_case_id": opaque_id,
        **dict(case["driver"]),
    }
    scoring = {"scoring_case_id": f"score_{opaque_id}", **dict(case["scoring"])}
    execution_hash, driver_hash, scoring_hash = map(_hash, (execution, driver, scoring))
    paths = SealedCasePaths.under_distinct_roots(roots, opaque_id)
    _write_exclusive(paths.execution_payload, execution)
    _write_exclusive(paths.execution_manifest, {
        "execution_payload_hash": execution_hash,
        "driver_package_hash": driver_hash,
    })
    _write_exclusive(paths.driver_package, driver)
    _write_exclusive(paths.driver_manifest, {"driver_package_hash": driver_hash})
    _write_exclusive(paths.scoring_package, scoring)
    _write_exclusive(paths.scoring_key, {
        "opaque_run_case_id": opaque_id,
        "execution_payload_hash": execution_hash,
        "driver_package_hash": driver_hash,
        "scoring_spec_hash": scoring_hash,
    })
    return paths


def load_scoring_key(path: Path) -> ScoringKey:
    value = json.loads(path.read_text(encoding="utf-8"))
    if set(value) != {field.name for field in fields(ScoringKey)}:
        raise EvaluationIntegrityError("scoring_key_shape_invalid")
    return ScoringKey(**value)


def verify_scoring_binding(execution_result: dict[str, object], key: ScoringKey) -> None:
    for name in ("opaque_run_case_id", "execution_payload_hash", "driver_package_hash"):
        if execution_result.get(name) != getattr(key, name):
            raise EvaluationIntegrityError(f"{name}_mismatch")


def verify_scoring_spec_binding(spec: ScoringSpec, key: ScoringKey) -> None:
    if spec.opaque_run_case_id != key.opaque_run_case_id:
        raise EvaluationIntegrityError("opaque_run_case_id_mismatch")
    if spec.scoring_spec_hash != key.scoring_spec_hash:
        raise EvaluationIntegrityError("scoring_spec_hash_mismatch")
