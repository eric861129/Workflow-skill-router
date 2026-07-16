from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
from typing import Protocol

from workflow_skill_router.capabilities.models import CapabilityKind
from workflow_skill_router.routing.leases import LeaseAlreadyConsumed, validate_invocation
from workflow_skill_router.routing.models import (
    ExecutionLease, InvocationContext, LeaseConsumptionReceipt,
    LeaseConsumptionRequest, VerifiedRuntimeApproval,
)
from workflow_skill_router.schemas.artifacts import canonical_json


class ActivationPreflightError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class InstructionContentHandle:
    capability_id: str
    content: bytes
    stable_identity: str


@dataclass(frozen=True, slots=True)
class RuntimeContractHandle:
    capability_id: str
    binding_kind: str
    binding_digest: str
    opaque_ref: str


@dataclass(frozen=True, slots=True)
class BoundCapabilityHandle:
    handle_id: str
    lease_id: str
    capability_id: str
    action_digest: str
    binding_digest: str
    reservation_digest: str
    bound_bytes: bytes | None
    runtime_contract_ref: str | None


@dataclass(frozen=True, slots=True)
class HostActivationReceipt:
    reservation_digest: str
    lease_id: str
    capability_id: str
    action_digest: str
    binding_digest: str
    receipt_digest: str


class InstructionContentResolver(Protocol):
    def open_stable(self, capability_id: str) -> InstructionContentHandle: ...


class RuntimeContractResolver(Protocol):
    def resolve(self, capability_id: str, binding_kind: str) -> RuntimeContractHandle: ...


class BoundCapabilityConsumer(Protocol):
    def consume(self, handle: BoundCapabilityHandle) -> HostActivationReceipt: ...


def _digest(document: dict[str, object]) -> str:
    return "sha256:" + hashlib.sha256(
        canonical_json(document).encode("utf-8")
    ).hexdigest()


class SQLiteLeaseActivationRepository:
    def __init__(self, database: Path, *, clock=None) -> None:
        self._database = database
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def compare_and_consume(
        self,
        request: LeaseConsumptionRequest,
        expected_consumption_version: int = 0,
    ) -> LeaseConsumptionReceipt:
        if expected_consumption_version != 0:
            raise LeaseAlreadyConsumed(request.lease_id)
        invocation_digest = _digest(asdict(request))
        binding_receipt_digest = _digest({
            "lease_id": request.lease_id,
            "capability_id": request.capability_id,
            "kind": request.activation_binding_kind,
            "observed_binding_digest": request.observed_binding_digest,
        })
        reservation_digest = _digest({
            "invocation_digest": invocation_digest,
            "binding_receipt_digest": binding_receipt_digest,
        })
        consumed_at = self._clock().astimezone(timezone.utc).isoformat()
        try:
            with closing(sqlite3.connect(self._database, timeout=30.0)) as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO lease_content_bindings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        request.lease_id, request.capability_id,
                        request.activation_binding_kind, request.observed_binding_digest,
                        request.observed_binding_digest, binding_receipt_digest,
                        consumed_at, canonical_json(asdict(request)),
                    ),
                )
                connection.execute(
                    "INSERT INTO lease_activation_consumptions VALUES ("
                    "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 'reserved', NULL, NULL)",
                    (
                        request.lease_id, request.capability_id, request.scope_anchor_id,
                        request.purpose, request.invocation_context_digest,
                        invocation_digest, request.action_digest, request.runtime_approval_ref,
                        request.runtime_approval_scope_digest, request.activation_binding_kind,
                        request.observed_binding_digest, binding_receipt_digest,
                        request.state_version, consumed_at, reservation_digest,
                    ),
                )
                connection.commit()
        except sqlite3.IntegrityError as error:
            raise LeaseAlreadyConsumed(request.lease_id) from error
        return LeaseConsumptionReceipt(
            request.lease_id,
            invocation_digest,
            reservation_digest,
            1,
            consumed_at,
        )

    def mark_activated(self, receipt: HostActivationReceipt) -> None:
        with closing(sqlite3.connect(self._database)) as connection:
            cursor = connection.execute(
                "UPDATE lease_activation_consumptions SET activation_status='activated',"
                "activation_receipt_digest=?,activated_at=? "
                "WHERE lease_id=? AND reservation_digest=? AND capability_id=? "
                "AND action_digest=? AND observed_binding_digest=? AND activation_status='reserved'",
                (
                    receipt.receipt_digest,
                    self._clock().astimezone(timezone.utc).isoformat(),
                    receipt.lease_id,
                    receipt.reservation_digest,
                    receipt.capability_id,
                    receipt.action_digest,
                    receipt.binding_digest,
                ),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise ActivationPreflightError("activation-receipt-mismatch")
            connection.commit()

    def consumption_count(self) -> int:
        with closing(sqlite3.connect(self._database)) as connection:
            return int(connection.execute(
                "SELECT COUNT(*) FROM lease_activation_consumptions"
            ).fetchone()[0])


class ActivationPreflightService:
    def __init__(
        self,
        repository: SQLiteLeaseActivationRepository,
        *,
        instruction_content_resolver: InstructionContentResolver | None,
        runtime_contract_resolver: RuntimeContractResolver | None,
        bound_capability_consumer: BoundCapabilityConsumer | None,
    ) -> None:
        self._repository = repository
        self._instructions = instruction_content_resolver
        self._contracts = runtime_contract_resolver
        self._consumer = bound_capability_consumer
        self._consumed_handles: set[str] = set()

    def bind_single_use(
        self,
        lease: ExecutionLease,
        capability_id: str,
        capability_fingerprint: str,
        action_digest: str,
        runtime_approval: VerifiedRuntimeApproval | None,
        state_version: int,
        invocation_context: InvocationContext,
        invocation_nonce: str,
        now: datetime,
    ) -> BoundCapabilityHandle:
        capability = next(
            (
                item for item in lease.allowed_capabilities
                if item.capability_id == capability_id
                and item.capability_fingerprint == capability_fingerprint
            ),
            None,
        )
        if capability is None:
            raise ActivationPreflightError("capability-not-leased")

        bound_bytes = None
        contract_ref = None
        if capability.capability_kind is CapabilityKind.SKILL:
            if self._instructions is None:
                raise ActivationPreflightError("content-preflight-unavailable")
            handle = self._instructions.open_stable(capability_id)
            if handle.capability_id != capability_id:
                raise ActivationPreflightError("instruction-handle-mismatch")
            observed_digest = "sha256:" + hashlib.sha256(handle.content).hexdigest()
            bound_bytes = handle.content
        else:
            if self._contracts is None:
                raise ActivationPreflightError("runtime-contract-preflight-unavailable")
            contract = self._contracts.resolve(
                capability_id,
                capability.activation_binding.kind,
            )
            observed_digest = contract.binding_digest
            contract_ref = contract.opaque_ref
        if observed_digest != capability.activation_binding.trusted_digest:
            raise ActivationPreflightError("binding-digest-mismatch")

        decision = validate_invocation(
            lease,
            capability_id,
            capability_fingerprint,
            action_digest,
            runtime_approval,
            observed_digest,
            state_version,
            now,
            invocation_context=invocation_context,
            invocation_nonce=invocation_nonce,
            consumption_port=self._repository,
        )
        if not decision.allowed or decision.receipt is None:
            raise ActivationPreflightError(decision.reason)
        receipt = decision.receipt
        return BoundCapabilityHandle(
            handle_id="bound:" + receipt.reservation_digest.removeprefix("sha256:"),
            lease_id=lease.lease_id,
            capability_id=capability_id,
            action_digest=action_digest,
            binding_digest=observed_digest,
            reservation_digest=receipt.reservation_digest,
            bound_bytes=bound_bytes,
            runtime_contract_ref=contract_ref,
        )

    def consume_bound(self, handle: BoundCapabilityHandle) -> HostActivationReceipt:
        if handle.handle_id in self._consumed_handles:
            raise ActivationPreflightError("handle-consumed")
        if self._consumer is None:
            raise ActivationPreflightError("host-consumer-unavailable")
        self._consumed_handles.add(handle.handle_id)
        receipt = self._consumer.consume(handle)
        if not isinstance(receipt, HostActivationReceipt):
            raise ActivationPreflightError("activation-receipt-required")
        self._repository.mark_activated(receipt)
        return receipt

    def bind_single_use_after_validation(self, command, result, snapshot):
        del command, snapshot
        # 無效 route 絕不觸碰 instruction 或 runtime contract；有效 route 的即時
        # invocation 由 server-internal bind_single_use 接收 authenticated context。
        return result

    def verify_consumption_receipt(self, command) -> None:
        if getattr(command, "activation_receipt_ref", None) is None:
            raise ActivationPreflightError("activation-receipt-required")
