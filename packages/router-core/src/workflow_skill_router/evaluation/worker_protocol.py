from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExecutionPackageHandle:
    opaque_run_case_id: str
    payload_ref: str
    execution_payload_hash: str
    driver_package_hash: str


@dataclass(frozen=True, slots=True)
class WorkerIsolationReceipt:
    attempt_nonce: str
    worker_identity: str
    execution_root_digest: str
    scoring_root_unavailable: bool
