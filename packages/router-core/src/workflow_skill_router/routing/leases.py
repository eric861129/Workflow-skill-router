from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
from threading import Lock

from workflow_skill_router.schemas.artifacts import canonical_json

from .models import (
    ExecutionLease,
    InvocationContext,
    InvocationDecision,
    LeaseCapability,
    LeaseConsumptionPort,
    LeaseConsumptionReceipt,
    LeaseConsumptionRequest,
    Route,
    RouteValidationRequest,
    SkillSelectionPolicy,
    ValidationContext,
    VerifiedRuntimeApproval,
)


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime 必須包含 timezone")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _digest(document: dict[str, object]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()


def build_invocation_context(
    scope_anchor_id: str,
    purpose: str,
    actor: str,
    session_id: str,
    runtime_policy_snapshot_id: str,
) -> InvocationContext:
    document = {
        "scope_anchor_id": scope_anchor_id,
        "purpose": purpose,
        "actor": actor,
        "session_id": session_id,
        "runtime_policy_snapshot_id": runtime_policy_snapshot_id,
    }
    return InvocationContext(
        scope_anchor_id,
        purpose,
        actor,
        session_id,
        runtime_policy_snapshot_id,
        _digest(document),
    )


def issue_execution_lease(
    route: Route,
    request: RouteValidationRequest,
    policy: SkillSelectionPolicy,
    context: ValidationContext,
    allowed_capabilities: tuple[LeaseCapability, ...],
) -> ExecutionLease:
    expires_at = context.now + timedelta(minutes=5)
    approval = context.runtime_approval
    if approval is not None:
        expires_at = min(expires_at, approval.expires_at)
    identity = {
        "route_id": route.route_id,
        "snapshot_id": route.capability_snapshot_id,
        "state_version": request.state_version,
        "action_digest": request.action_digest,
        "issued_at": _timestamp(context.now),
    }
    return ExecutionLease(
        lease_id="lease:" + _digest(identity).removeprefix("sha256:"),
        workflow_run_id=route.workflow_run_id,
        phase_id=route.phase_id,
        scope_anchor_id=request.scope_anchor_id,
        route_id=route.route_id,
        capability_snapshot_id=route.capability_snapshot_id,
        policy_revision=policy.plan_revision,
        state_version=request.state_version,
        runtime_policy_snapshot_id=context.runtime_policy_snapshot_id,
        action_digest=request.action_digest,
        runtime_approval_ref=approval.approval_ref if approval else None,
        runtime_approval_scope_digest=approval.scope_digest if approval else None,
        content_preflight_policy_digest=context.content_preflight_policy_digest,
        allowed_capabilities=allowed_capabilities,
        issued_at=_timestamp(context.now),
        expires_at=_timestamp(expires_at),
        max_activations=1,
        activation_mode="single-use-preflight",
    )


class LeaseAlreadyConsumed(RuntimeError):
    pass


class InMemoryLeaseConsumptionPort:
    def __init__(self, *, clock=None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._versions: dict[str, int] = {}
        self._lock = Lock()

    def compare_and_consume(
        self,
        request: LeaseConsumptionRequest,
        expected_consumption_version: int = 0,
    ) -> LeaseConsumptionReceipt:
        with self._lock:
            current = self._versions.get(request.lease_id, 0)
            if current != expected_consumption_version:
                raise LeaseAlreadyConsumed(request.lease_id)
            version = current + 1
            self._versions[request.lease_id] = version
            document = asdict(request)
            invocation_digest = _digest(document)
            return LeaseConsumptionReceipt(
                request.lease_id,
                invocation_digest,
                _digest({
                    "lease_id": request.lease_id,
                    "invocation_digest": invocation_digest,
                    "consumption_version": version,
                }),
                version,
                _timestamp(self._clock()),
            )


def validate_invocation(
    lease: ExecutionLease,
    capability_id: str,
    capability_fingerprint: str,
    action_digest: str,
    runtime_approval: VerifiedRuntimeApproval | None,
    observed_binding_digest: str,
    state_version: int,
    now: datetime,
    *,
    invocation_context: InvocationContext,
    invocation_nonce: str,
    consumption_port: LeaseConsumptionPort,
) -> InvocationDecision:
    if now >= _parse_timestamp(lease.expires_at):
        return InvocationDecision(False, "lease-expired", None)
    capability = next(
        (
            item for item in lease.allowed_capabilities
            if item.capability_id == capability_id
            and item.capability_fingerprint == capability_fingerprint
        ),
        None,
    )
    if capability is None:
        return InvocationDecision(False, "capability-not-leased", None)
    if action_digest != lease.action_digest:
        return InvocationDecision(False, "action-digest-mismatch", None)
    if state_version != lease.state_version:
        return InvocationDecision(False, "state-version-mismatch", None)

    expected_context = build_invocation_context(
        invocation_context.scope_anchor_id,
        invocation_context.purpose,
        invocation_context.actor,
        invocation_context.session_id,
        invocation_context.runtime_policy_snapshot_id,
    )
    if (
        invocation_context != expected_context
        or invocation_context.scope_anchor_id != lease.scope_anchor_id
        or invocation_context.purpose != capability.purpose
        or invocation_context.runtime_policy_snapshot_id != lease.runtime_policy_snapshot_id
    ):
        return InvocationDecision(False, "invocation-context-mismatch", None)

    if lease.runtime_approval_ref is None:
        if runtime_approval is not None:
            return InvocationDecision(False, "runtime-approval-mismatch", None)
    elif (
        runtime_approval is None
        or runtime_approval.approval_ref != lease.runtime_approval_ref
        or runtime_approval.scope_digest != lease.runtime_approval_scope_digest
        or runtime_approval.action_digest != lease.action_digest
        or runtime_approval.expires_at <= now
    ):
        return InvocationDecision(False, "runtime-approval-mismatch", None)
    if observed_binding_digest != capability.activation_binding.trusted_digest:
        return InvocationDecision(False, "activation-binding-mismatch", None)

    request = LeaseConsumptionRequest(
        lease.lease_id,
        capability_id,
        capability_fingerprint,
        lease.scope_anchor_id,
        capability.purpose,
        invocation_context.context_digest,
        capability.activation_binding.kind,
        observed_binding_digest,
        action_digest,
        lease.runtime_approval_ref,
        lease.runtime_approval_scope_digest,
        state_version,
        invocation_nonce,
    )
    try:
        receipt = consumption_port.compare_and_consume(
            request,
            expected_consumption_version=0,
        )
    except LeaseAlreadyConsumed:
        return InvocationDecision(False, "lease-consumed", None)
    except Exception:
        return InvocationDecision(False, "lease-consumption-failed", None)
    return InvocationDecision(True, "lease-consumed-reserved", receipt)
