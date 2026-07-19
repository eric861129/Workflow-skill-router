from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable, Mapping

from .contracts import (
    AdapterSelection, EvaluationIntegrityError, EvaluationProfile, EvaluationStatus,
    ModelExecutionPayload, ModelTurnRequest,
)


def select_execution_adapter(capability_ids: Iterable[str], profile: str) -> AdapterSelection:
    capabilities = frozenset(capability_ids)
    if profile == EvaluationProfile.CONTRACT.value:
        return AdapterSelection("contract", EvaluationStatus.COMPLETED, "tier-0-contract")
    if "host:fresh-task" in capabilities:
        return AdapterSelection("host-task", EvaluationStatus.SCHEDULED, "fresh-model-execution")
    if "external:fresh-session" in capabilities:
        return AdapterSelection("external-provider", EvaluationStatus.SCHEDULED, "fresh-model-execution")
    if "evaluation:subprocess:fresh-model" in capabilities:
        return AdapterSelection("subprocess", EvaluationStatus.SCHEDULED, "fresh-model-execution")
    return AdapterSelection("manual-import", EvaluationStatus.MANUAL_REQUIRED, "manual-provenance",
                            "fresh-execution-adapter-unavailable")


class HostTaskAdapter:
    kind = "host-task"

    def __init__(self, port, receipt_verifier) -> None:
        self._port = port
        self._verifier = receipt_verifier
        self._task_ids: set[str] = set()
        self._active: tuple[str, str] | None = None

    def start_attempt(self, payload: ModelExecutionPayload, attempt_nonce: str) -> str:
        task_id, receipt = self._port.create_fresh(payload, attempt_nonce)
        if task_id in self._task_ids or not self._verifier.verify(receipt, attempt_nonce, payload):
            raise EvaluationIntegrityError("host_context_not_fresh")
        self._task_ids.add(task_id)
        self._active = (task_id, attempt_nonce)
        return task_id

    def execute_turn(self, request: ModelTurnRequest) -> Mapping[str, object]:
        if self._active is None or request.attempt_nonce != self._active[1]:
            raise EvaluationIntegrityError("attempt_context_mismatch")
        return self._port.execute(self._active[0], request)


class ExternalProviderAdapter(HostTaskAdapter):
    kind = "external-provider"


@dataclass(frozen=True, slots=True)
class ManualBundle:
    manual_bundle_id: str
    import_token: str
    execution_payload_hash: str
    driver_package_hash: str


class ManualImportAdapter:
    kind = "manual-import"

    def create_bundle(self, execution_payload_hash: str, driver_package_hash: str) -> ManualBundle:
        identity = f"{execution_payload_hash}:{driver_package_hash}".encode()
        digest = sha256(identity).hexdigest()
        return ManualBundle("manual:" + digest[:20], "token:" + digest, execution_payload_hash, driver_package_hash)
