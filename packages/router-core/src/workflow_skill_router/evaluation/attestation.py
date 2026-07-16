from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class ReviewAttestationError(PermissionError):
    pass


class ReviewVerifier(Protocol):
    def verify(self, opaque_receipt: str, review_subject_digest: str, now: datetime) -> bool: ...


class ReviewVerifierRegistry:
    """預設拒絕；只有已驗證 bridge initialization 可註冊 host authority。"""

    def __init__(self, verifiers: dict[str, ReviewVerifier] | None = None) -> None:
        self._verifiers = dict(verifiers or {})

    def verify(self, authority_id: str, receipt: str, subject_digest: str, now: datetime) -> None:
        verifier = self._verifiers.get(authority_id)
        if verifier is None or not verifier.verify(receipt, subject_digest, now):
            raise ReviewAttestationError("human_review_attestation_invalid")
