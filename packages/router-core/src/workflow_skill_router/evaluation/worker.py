from __future__ import annotations

from .contracts import EvaluationIntegrityError
from .worker_protocol import WorkerIsolationReceipt


def verify_worker_isolation(receipt: WorkerIsolationReceipt, attempt_nonce: str) -> None:
    if receipt.attempt_nonce != attempt_nonce or not receipt.scoring_root_unavailable:
        raise EvaluationIntegrityError("worker_isolation_unverified")
