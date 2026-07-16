from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class EvaluationStatus(StrEnum):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    MANUAL_REQUIRED = "manual-required"
    UNSUPPORTED = "unsupported"
    COMPLETED = "completed"
    INVALID = "invalid"


class EvaluationProfile(StrEnum):
    CONTRACT = "contract"
    BEHAVIOR = "behavior"
    OUTCOME = "outcome"


@dataclass(frozen=True, slots=True)
class ModelExecutionPayload:
    opaque_run_case_id: str
    prompt: str
    profile: EvaluationProfile
    allowed_tools: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InteractionDriverSpec:
    opaque_run_case_id: str
    replies: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScoringSpec:
    opaque_run_case_id: str
    scoring_spec_hash: str
    expected_envelope: str
    hard_invariants: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScoringKey:
    opaque_run_case_id: str
    execution_payload_hash: str
    driver_package_hash: str
    scoring_spec_hash: str


@dataclass(frozen=True, slots=True)
class SealingRoots:
    execution_root: Path
    driver_root: Path
    scoring_root: Path


@dataclass(frozen=True, slots=True)
class SealedCasePaths:
    opaque_run_case_id: str
    execution_dir: Path
    driver_dir: Path
    scoring_dir: Path
    execution_payload: Path
    execution_manifest: Path
    driver_package: Path
    driver_manifest: Path
    scoring_package: Path
    scoring_key: Path

    @classmethod
    def under_distinct_roots(cls, roots: SealingRoots, opaque_id: str) -> "SealedCasePaths":
        resolved = tuple(path.resolve() for path in (
            roots.execution_root, roots.driver_root, roots.scoring_root,
        ))
        if len(set(resolved)) != 3 or any(
            left in right.parents or right in left.parents
            for index, left in enumerate(resolved)
            for right in resolved[index + 1:]
        ):
            raise EvaluationIntegrityError("sealing_roots_not_disjoint")
        execution, driver, scoring = (root / opaque_id for root in resolved)
        return cls(
            opaque_id, execution, driver, scoring,
            execution / "payload.json", execution / "execution-manifest.json",
            driver / "driver.json", driver / "driver-manifest.json",
            scoring / "scoring.json", scoring / "scoring-key.json",
        )


class EvaluationIntegrityError(RuntimeError):
    pass
