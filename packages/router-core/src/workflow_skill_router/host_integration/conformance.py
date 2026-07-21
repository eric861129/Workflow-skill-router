from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
import re
from types import SimpleNamespace

from workflow_skill_router.composition import RouterCompositionPorts, open as open_router
from workflow_skill_router.host_integration.contracts import (
    EventAppendProbe,
    HostConformanceCase,
    HostConformanceReport,
    HostIntegrationConformanceError,
    NativeGoalResumeProbe,
    ReceiptProbe,
    ServerOwnedHostResources,
    validate_host_manifest,
)
from workflow_skill_router.ports import HostConformanceAdapterPort
from workflow_skill_router.service_models import RequestContext


_SHA256_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def _is_sha256_digest(value: object) -> bool:
    return isinstance(value, str) and _SHA256_DIGEST.fullmatch(value) is not None


def _has_opaque_suffix(value: object, prefix: str) -> bool:
    return (
        isinstance(value, str)
        and value.startswith(prefix)
        and bool(value.removeprefix(prefix).strip())
    )


class _RecordingAdapter:
    """委派正式 adapter，並捕捉送入 production composition root 的同一組 ports。"""

    def __init__(self, delegate) -> None:
        self._delegate = delegate
        self.captured_ports: RouterCompositionPorts | None = None

    def host_manifest(self):
        return self._delegate.host_manifest()

    def build_router_ports(self, **server_owned_resources):
        ports = self._delegate.build_router_ports(**server_owned_resources)
        self.captured_ports = ports
        return ports

    def require_captured_ports(self) -> RouterCompositionPorts:
        if self.captured_ports is None:
            raise HostIntegrationConformanceError("composition-ports-not-captured")
        return self.captured_ports


def _expected_failure(
    name: str,
    diagnostic: str,
    operation: Callable[[], object],
) -> HostConformanceCase:
    try:
        operation()
    except HostIntegrationConformanceError as error:
        return HostConformanceCase(
            name=name,
            passed=error.diagnostic == diagnostic,
            diagnostic=error.diagnostic,
        )
    except Exception:
        return HostConformanceCase(name, False, "unexpected-failure")
    return HostConformanceCase(name, False, "fail-closed-not-enforced")


def _successful_operation(
    name: str,
    success_diagnostic: str,
    failure_diagnostic: str,
    operation: Callable[[], object],
    validator: Callable[[object], bool],
) -> HostConformanceCase:
    try:
        result = operation()
    except HostIntegrationConformanceError as error:
        return HostConformanceCase(name, False, error.diagnostic)
    except Exception:
        return HostConformanceCase(name, False, "unexpected-failure")
    try:
        passed = validator(result)
    except Exception:
        return HostConformanceCase(name, False, "unexpected-failure")
    return HostConformanceCase(
        name,
        passed,
        success_diagnostic if passed else failure_diagnostic,
    )


def _renamed_case(name: str, case: HostConformanceCase) -> HostConformanceCase:
    return HostConformanceCase(
        name,
        case.passed,
        case.diagnostic,
        case.evidence,
        case.private_details,
    )


def _runtime_authority_case(authority_port, valid_context, wrong_context):
    authority = _successful_operation(
        "runtime_authority",
        "runtime-authority-session-bound",
        "runtime-authority-invalid",
        lambda: authority_port.require(valid_context),
        lambda result: (
            getattr(result, "session_id", None) == valid_context.session_id
            and getattr(result, "runtime_policy_snapshot_id", None)
            == valid_context.runtime_policy_snapshot_id
            and isinstance(getattr(result, "runtime_fingerprint", None), str)
            and bool(getattr(result, "runtime_fingerprint", "").strip())
            and _is_sha256_digest(
                getattr(result, "verification_receipt_digest", None)
            )
        ),
    )
    rejected = _expected_failure(
        "runtime-authority-session-rejection",
        "request-session-mismatch",
        lambda: authority_port.require(wrong_context),
    )
    if authority.passed and rejected.passed:
        return authority
    return HostConformanceCase(
        "runtime_authority",
        False,
        authority.diagnostic if not authority.passed else rejected.diagnostic,
    )


def _runtime_context_case(runtime_context_port, authority, probe):
    request = SimpleNamespace(
        authority=authority,
        host_snapshot_ref=probe.fresh_snapshot_ref,
        plugin_handshake_ref=None,
        agent_runtime_snapshot=None,
    )
    current = _successful_operation(
        "runtime_context",
        "runtime-context-fresh",
        "runtime-context-invalid",
        lambda: runtime_context_port.sync_verified(request),
        lambda result: (
            getattr(result, "session_id", None) == probe.valid_session_id
            and getattr(result, "snapshot_ref", None) == probe.fresh_snapshot_ref
            and getattr(result, "fresh", None) is True
            and getattr(result, "runtime_fingerprint", None)
            == getattr(authority, "runtime_fingerprint", None)
            and getattr(result, "runtime_policy_snapshot_id", None)
            == getattr(authority, "runtime_policy_snapshot_id", None)
            and getattr(result, "authority_receipt_digest", None)
            == getattr(authority, "verification_receipt_digest", None)
        ),
    )
    stale_request = SimpleNamespace(
        authority=authority,
        host_snapshot_ref=probe.stale_snapshot_ref,
        plugin_handshake_ref=None,
        agent_runtime_snapshot=None,
    )
    stale = _expected_failure(
        "runtime-context-stale",
        "runtime-context-unavailable",
        lambda: runtime_context_port.sync_verified(stale_request),
    )
    unrelated_authority = SimpleNamespace(
        session_id=probe.wrong_session_id,
        runtime_fingerprint="runtime:unrelated",
        runtime_policy_snapshot_id="policy:unrelated",
        verification_receipt_digest="sha256:" + "0" * 64,
    )
    unrelated = _expected_failure(
        "runtime-context-unrelated-authority",
        "runtime-authority-unavailable",
        lambda: runtime_context_port.sync_verified(SimpleNamespace(
            authority=unrelated_authority,
            host_snapshot_ref=probe.fresh_snapshot_ref,
            plugin_handshake_ref=None,
            agent_runtime_snapshot=None,
        )),
    )
    same_session_mismatches = (
        SimpleNamespace(
            session_id=probe.valid_session_id,
            runtime_fingerprint="runtime:mismatched",
            runtime_policy_snapshot_id=getattr(
                authority, "runtime_policy_snapshot_id", None
            ),
            verification_receipt_digest=getattr(
                authority, "verification_receipt_digest", None
            ),
        ),
        SimpleNamespace(
            session_id=probe.valid_session_id,
            runtime_fingerprint=getattr(authority, "runtime_fingerprint", None),
            runtime_policy_snapshot_id="policy:mismatched",
            verification_receipt_digest=getattr(
                authority, "verification_receipt_digest", None
            ),
        ),
        SimpleNamespace(
            session_id=probe.valid_session_id,
            runtime_fingerprint=getattr(authority, "runtime_fingerprint", None),
            runtime_policy_snapshot_id=getattr(
                authority, "runtime_policy_snapshot_id", None
            ),
            verification_receipt_digest="sha256:" + "f" * 64,
        ),
    )
    binding_cases = tuple(
        _expected_failure(
            f"runtime-context-authority-binding-{index}",
            "runtime-authority-unavailable",
            lambda mismatch=mismatch: runtime_context_port.sync_verified(
                SimpleNamespace(
                    authority=mismatch,
                    host_snapshot_ref=probe.fresh_snapshot_ref,
                    plugin_handshake_ref=None,
                    agent_runtime_snapshot=None,
                )
            ),
        )
        for index, mismatch in enumerate(same_session_mismatches, start=1)
    )
    checks = (current, stale, unrelated, *binding_cases)
    if all(case.passed for case in checks):
        return current
    return HostConformanceCase(
        "runtime_context",
        False,
        (
            next(case.diagnostic for case in checks if not case.passed)
        ),
    )


def _scheduler_case(scheduler_port, valid_context, probe):
    current = _successful_operation(
        "scheduler-current",
        "scheduler-resume-context-current",
        "scheduler-result-invalid",
        lambda: scheduler_port.next(
            NativeGoalResumeProbe(
                valid_context,
                probe.native_goal_id,
                ("goal", "workspace", "capabilities", "evidence"),
            ),
            require_resume_refresh=True,
        ),
        lambda result: (
            getattr(result, "status", None) == "ready"
            and getattr(result, "session_id", None) == valid_context.session_id
            and getattr(result, "native_goal_id", None) == probe.native_goal_id
            and tuple(getattr(result, "refreshed_contexts", ()))
            == ("goal", "workspace", "capabilities", "evidence")
            and _has_opaque_suffix(
                getattr(result, "receipt_ref", None),
                "scheduler-decision-receipt:",
            )
        ),
    )
    stale = _expected_failure(
        "native-goal-refresh",
        "goal-resume-refresh-required",
        lambda: scheduler_port.next(
            NativeGoalResumeProbe(valid_context, probe.native_goal_id, ()),
            require_resume_refresh=True,
        ),
    )
    wrong_context = RequestContext(
        probe.wrong_session_id,
        valid_context.actor,
        valid_context.runtime_policy_snapshot_id,
    )
    wrong_session = _expected_failure(
        "scheduler-wrong-session",
        "request-session-mismatch",
        lambda: scheduler_port.next(
            NativeGoalResumeProbe(
                wrong_context,
                probe.native_goal_id,
                ("goal", "workspace", "capabilities", "evidence"),
            ),
            require_resume_refresh=True,
        ),
    )
    combined = HostConformanceCase(
        "scheduler",
        current.passed and stale.passed and wrong_session.passed,
        (
            "scheduler-resume-freshness-enforced"
            if current.passed and stale.passed and wrong_session.passed
            else (
                current.diagnostic
                if not current.passed
                else stale.diagnostic if not stale.passed else wrong_session.diagnostic
            )
        ),
    )
    return combined, stale


def _policy_repository_case(policy_port, valid_context):
    current_revision = 7
    current = _successful_operation(
        "policy_repository",
        "policy-current-revision-confirmed",
        "policy-receipt-invalid",
        lambda: policy_port.require(
            current_revision, valid_context.runtime_policy_snapshot_id
        ),
        lambda result: (
            getattr(result, "revision", None) == current_revision
            and getattr(result, "runtime_policy_snapshot_id", None)
            == valid_context.runtime_policy_snapshot_id
            and isinstance(getattr(result, "receipt_ref", None), str)
            and bool(getattr(result, "receipt_ref", "").strip())
        ),
    )
    stale = _expected_failure(
        "policy-stale-rejection",
        "policy-stale",
        lambda: policy_port.require(
            current_revision - 1, valid_context.runtime_policy_snapshot_id
        ),
    )
    wrong_snapshot = _expected_failure(
        "policy-runtime-snapshot-mismatch",
        "policy-unavailable",
        lambda: policy_port.require(current_revision, "policy:unrelated"),
    )
    if current.passed and stale.passed and wrong_snapshot.passed:
        return current
    return HostConformanceCase(
        "policy_repository",
        False,
        (
            current.diagnostic
            if not current.passed
            else stale.diagnostic if not stale.passed else wrong_snapshot.diagnostic
        ),
    )


def _route_validation_case(
    validation_context_port,
    route_validator_port,
    snapshot,
    policy,
    valid_context,
):
    valid_proposal = SimpleNamespace(route_id="route:accepted", allowed=True)
    command = SimpleNamespace(
        context=valid_context,
        route_proposal=valid_proposal,
    )
    try:
        context = validation_context_port.current_for(command, snapshot, policy)
    except HostIntegrationConformanceError as error:
        return HostConformanceCase("route_validation", False, error.diagnostic)
    except Exception:
        return HostConformanceCase("route_validation", False, "unexpected-failure")
    context_valid = (
        getattr(context, "session_id", None) == valid_context.session_id
        and getattr(context, "current", None) is True
        and isinstance(getattr(context, "receipt_ref", None), str)
        and bool(getattr(context, "receipt_ref", "").strip())
    )
    if not context_valid:
        return HostConformanceCase(
            "route_validation", False, "route-validation-context-invalid"
        )
    snapshot_ref = (
        snapshot.get("snapshot_id")
        if isinstance(snapshot, dict)
        else getattr(snapshot, "snapshot_id", None)
    )
    valid = _successful_operation(
        "route-validation-accepted",
        "route-validation-receipt-confirmed",
        "route-validation-receipt-invalid",
        lambda: route_validator_port.validate(
            valid_proposal, snapshot, policy, context
        ),
        lambda result: (
            getattr(result, "valid", None) is True
            and _has_opaque_suffix(
                getattr(result, "receipt_ref", None),
                "route-validation-receipt:",
            )
            and getattr(result, "route_id", None) == valid_proposal.route_id
            and getattr(result, "snapshot_ref", None) == snapshot_ref
            and getattr(result, "policy_revision", None)
            == getattr(policy, "revision", None)
            and getattr(result, "context_receipt_ref", None)
            == getattr(context, "receipt_ref", None)
        ),
    )
    rejected_proposal = SimpleNamespace(route_id="route:rejected", allowed=False)
    rejected = _expected_failure(
        "route-validation-rejection",
        "route-validation-rejected",
        lambda: route_validator_port.validate(
            rejected_proposal, snapshot, policy, context
        ),
    )
    return HostConformanceCase(
        "route_validation",
        valid.passed and rejected.passed,
        (
            "route-validation-fail-closed-confirmed"
            if valid.passed and rejected.passed
            else valid.diagnostic if not valid.passed else rejected.diagnostic
        ),
    )


def _activation_preflight_case(activation_port, valid_context, snapshot):
    command = SimpleNamespace(
        context=valid_context,
        route_id="route:activation-conformance",
    )
    result = SimpleNamespace(valid=True)
    bound = _successful_operation(
        "activation_preflight",
        "activation-single-use-bound",
        "activation-binding-invalid",
        lambda: activation_port.bind_single_use_after_validation(
            command, result, snapshot
        ),
        lambda item: (
            getattr(item, "valid", None) is True
            and isinstance(getattr(item, "activation_lease_ref", None), str)
            and bool(getattr(item, "activation_lease_ref", "").strip())
            and getattr(item, "route_id", None) == command.route_id
            and getattr(item, "session_id", None) == valid_context.session_id
            and getattr(item, "snapshot_ref", None)
            == (
                snapshot.get("snapshot_id")
                if isinstance(snapshot, dict)
                else getattr(snapshot, "snapshot_id", None)
            )
        ),
    )
    duplicate = _expected_failure(
        "activation-binding-replay",
        "activation-lease-already-bound",
        lambda: activation_port.bind_single_use_after_validation(
            command, result, snapshot
        ),
    )
    invalid_result = _expected_failure(
        "activation-invalid-result",
        "activation-preflight-failed",
        lambda: activation_port.bind_single_use_after_validation(
            SimpleNamespace(
                context=valid_context,
                route_id="route:activation-invalid-result",
            ),
            SimpleNamespace(valid=False),
            snapshot,
        ),
    )
    invalid_snapshot = _expected_failure(
        "activation-invalid-snapshot",
        "activation-preflight-failed",
        lambda: activation_port.bind_single_use_after_validation(
            SimpleNamespace(
                context=valid_context,
                route_id="route:activation-invalid-snapshot",
            ),
            result,
            None,
        ),
    )
    wrong_context = RequestContext(
        "session:wrong", valid_context.actor, valid_context.runtime_policy_snapshot_id
    )
    wrong_session = _expected_failure(
        "activation-wrong-session",
        "request-session-mismatch",
        lambda: activation_port.bind_single_use_after_validation(
            SimpleNamespace(
                context=wrong_context,
                route_id="route:activation-wrong-session",
            ),
            result,
            snapshot,
        ),
    )
    checks = (bound, duplicate, invalid_result, invalid_snapshot, wrong_session)
    if all(case.passed for case in checks):
        return bound
    return HostConformanceCase(
        "activation_preflight",
        False,
        next(case.diagnostic for case in checks if not case.passed),
    )


def _gate_context_case(gate_context_port, command):
    current = _successful_operation(
        "gate_context",
        "gate-context-current",
        "gate-context-invalid",
        lambda: gate_context_port.build_from_current_projection(command),
        lambda result: (
            getattr(result, "workflow_run_id", None) == command.workflow_run_id
            and getattr(result, "phase_id", None) == command.phase_id
            and getattr(result, "current", None) is True
            and getattr(result, "evidence_digest", None)
            == command.expected_evidence_digest
        ),
    )
    stale_command = SimpleNamespace(
        context=command.context,
        workflow_run_id=command.workflow_run_id,
        phase_id=command.phase_id,
        expected_state_version=command.expected_state_version,
        expected_evidence_digest="stale-evidence",
    )
    stale = _expected_failure(
        "gate-context-stale",
        "evidence-stale",
        lambda: gate_context_port.build_from_current_projection(stale_command),
    )
    if current.passed and stale.passed:
        return current
    return HostConformanceCase(
        "gate_context",
        False,
        current.diagnostic if not current.passed else stale.diagnostic,
    )


def _gate_evaluator_case(gate_evaluator_port, request):
    current = _successful_operation(
        "gate_evaluator",
        "gate-evaluation-authoritative",
        "gate-evaluation-invalid",
        lambda: gate_evaluator_port.evaluate(request),
        lambda result: (
            getattr(result, "status", None) == "evaluated"
            and getattr(result, "passed", None) is True
            and getattr(result, "evidence_digest", None)
            == request.evidence_digest
            and isinstance(getattr(result, "decision_ref", None), str)
            and bool(getattr(result, "decision_ref", "").strip())
        ),
    )
    stale_request = SimpleNamespace(
        workflow_run_id=getattr(request, "workflow_run_id", None),
        phase_id=getattr(request, "phase_id", None),
        current=False,
        evidence_digest=getattr(request, "evidence_digest", None),
    )
    stale = _expected_failure(
        "gate-evaluator-stale",
        "gate-evaluation-unavailable",
        lambda: gate_evaluator_port.evaluate(stale_request),
    )
    if current.passed and stale.passed:
        return current
    return HostConformanceCase(
        "gate_evaluator",
        False,
        current.diagnostic if not current.passed else stale.diagnostic,
    )


def _gate_coordinator_case(gate_coordinator_port, command, result):
    persisted = _successful_operation(
        "gate_coordinator",
        "gate-result-persisted",
        "gate-persist-invalid",
        lambda: gate_coordinator_port.persist_result(command, result),
        lambda receipt: (
            getattr(receipt, "state_version", None)
            == command.expected_state_version + 1
            and isinstance(getattr(receipt, "receipt_ref", None), str)
            and bool(getattr(receipt, "receipt_ref", "").strip())
            and getattr(receipt, "idempotency_key", None)
            == command.idempotency_key
        ),
    )
    stale_command = SimpleNamespace(
        context=command.context,
        workflow_run_id=command.workflow_run_id,
        phase_id=command.phase_id,
        expected_state_version=command.expected_state_version,
        expected_evidence_digest=command.expected_evidence_digest,
        idempotency_key="gate-persist:stale-distinct",
    )
    cas_conflict = _expected_failure(
        "gate-coordinator-cas-conflict",
        "state-version-conflict",
        lambda: gate_coordinator_port.persist_result(stale_command, result),
    )
    if persisted.passed and cas_conflict.passed:
        return persisted
    return HostConformanceCase(
        "gate_coordinator",
        False,
        persisted.diagnostic if not persisted.passed else cas_conflict.diagnostic,
    )


def _evaluation_case(evaluation_port, valid_context, probe):
    authorization_ref = "evaluation-authorization:conformance"
    commands = (
        (
            "run",
            SimpleNamespace(
                context=valid_context,
                sealed_input_ref="sealed:case",
                authorization_ref=authorization_ref,
            ),
            "evaluation_ref",
        ),
        (
            "compare",
            SimpleNamespace(
                context=valid_context,
                sealed_input_ref="sealed:comparison",
                authorization_ref=authorization_ref,
            ),
            "comparison_ref",
        ),
        (
            "export",
            SimpleNamespace(
                context=valid_context,
                sealed_input_ref="sealed:artifact",
                authorization_ref=authorization_ref,
            ),
            "artifact_ref",
        ),
    )
    evaluation_mode = getattr(probe, "evaluation_mode", "unavailable")
    if evaluation_mode not in {"configured", "unavailable"}:
        return HostConformanceCase("evaluation", False, "evaluation-mode-invalid")
    if evaluation_mode == "configured":
        operation_cases: list[HostConformanceCase] = []
        for operation_name, command, receipt_field in commands:
            case = _successful_operation(
                f"evaluation-{operation_name}",
                "evaluation-receipt-confirmed",
                "evaluation-receipt-invalid",
                lambda operation_name=operation_name, command=command: getattr(
                    evaluation_port, operation_name
                )(command),
                lambda result, receipt_field=receipt_field: (
                    isinstance(getattr(result, receipt_field, None), str)
                    and bool(getattr(result, receipt_field, "").strip())
                    and getattr(result, "session_id", None)
                    == valid_context.session_id
                    and getattr(result, "sealed_input_ref", None)
                    == command.sealed_input_ref
                    and getattr(result, "authorization_ref", None)
                    == command.authorization_ref
                    and getattr(result, "operation", None) == operation_name
                ),
            )
            operation_cases.append(case)
            wrong_context = RequestContext(
                probe.wrong_session_id,
                valid_context.actor,
                valid_context.runtime_policy_snapshot_id,
            )
            wrong_session = _expected_failure(
                f"evaluation-{operation_name}-wrong-session",
                "request-session-mismatch",
                lambda operation_name=operation_name, command=command: getattr(
                    evaluation_port, operation_name
                )(SimpleNamespace(
                    context=wrong_context,
                    sealed_input_ref=command.sealed_input_ref,
                    authorization_ref=command.authorization_ref,
                )),
            )
            operation_cases.append(wrong_session)
        failed = next(
            (case for case in operation_cases if not case.passed),
            None,
        )
        if failed is not None:
            return HostConformanceCase("evaluation", False, failed.diagnostic)
        return HostConformanceCase(
            "evaluation", True, "evaluation-configured-receipts-confirmed"
        )
    for operation_name, command, _ in commands:
        case = _expected_failure(
            f"evaluation-{operation_name}",
            "reference-evaluation-disabled",
            lambda operation_name=operation_name, command=command: getattr(
                evaluation_port, operation_name
            )(command),
        )
        if not case.passed:
            return HostConformanceCase("evaluation", False, case.diagnostic)
    return HostConformanceCase(
        "evaluation", True, "evaluation-unavailable-fail-closed"
    )


def _snapshot_repository_cases(snapshot_port, probe):
    fresh = _successful_operation(
        "snapshot-fresh",
        "snapshot-fresh-confirmed",
        "snapshot-invalid",
        lambda: snapshot_port.require(probe.fresh_snapshot_ref),
        lambda result: (
            (
                result.get("snapshot_id")
                if isinstance(result, dict)
                else getattr(result, "snapshot_id", None)
            )
            == probe.fresh_snapshot_ref
            and (
                result.get("fresh")
                if isinstance(result, dict)
                else getattr(result, "fresh", None)
            )
            is True
        ),
    )
    stale = _expected_failure(
        "snapshot-stale",
        "snapshot-stale",
        lambda: snapshot_port.require(probe.stale_snapshot_ref),
    )
    combined = HostConformanceCase(
        "snapshot_repository",
        fresh.passed and stale.passed,
        (
            "snapshot-freshness-enforced"
            if fresh.passed and stale.passed
            else fresh.diagnostic if not fresh.passed else stale.diagnostic
        ),
    )
    return combined, stale


def _receipt_verification_cases(activation_port, valid_context, wrong_context, probe):
    route_id = "route:activation-conformance"
    valid = _successful_operation(
        "receipt-valid",
        "activation-receipt-session-bound",
        "activation-receipt-validation-failed",
        lambda: activation_port.verify_consumption_receipt(
            ReceiptProbe(valid_context, probe.valid_receipt_ref, route_id)
        ),
        lambda result: result is None,
    )
    forged = _expected_failure(
        "receipt-forged",
        "activation-receipt-invalid",
        lambda: activation_port.verify_consumption_receipt(
            ReceiptProbe(valid_context, probe.forged_receipt_ref, route_id)
        ),
    )
    mismatch = _expected_failure(
        "session-mismatch",
        "request-session-mismatch",
        lambda: activation_port.verify_consumption_receipt(
            ReceiptProbe(wrong_context, probe.valid_receipt_ref, route_id)
        ),
    )
    wrong_route = _expected_failure(
        "activation-receipt-route-mismatch",
        "activation-receipt-route-mismatch",
        lambda: activation_port.verify_consumption_receipt(
            ReceiptProbe(
                valid_context,
                probe.valid_receipt_ref,
                "route:unrelated",
            )
        ),
    )
    combined = HostConformanceCase(
        "activation_receipt_verification",
        valid.passed and forged.passed and mismatch.passed and wrong_route.passed,
        (
            "activation-receipt-verification-enforced"
            if valid.passed and forged.passed and mismatch.passed and wrong_route.passed
            else (
                valid.diagnostic
                if not valid.passed
                else (
                    forged.diagnostic
                    if not forged.passed
                    else mismatch.diagnostic if not mismatch.passed else wrong_route.diagnostic
                )
            )
        ),
    )
    return combined, forged, mismatch


def _append_coordination_cases(coordinator_port, probe):
    first_command = EventAppendProbe(
        probe.valid_session_id,
        0,
        "conformance-idempotent",
        "sha256:" + "a" * 64,
    )
    try:
        first = coordinator_port.record(first_command)
        replay = coordinator_port.record(first_command)
        replay_valid = (
            isinstance(getattr(first, "event_id", None), str)
            and bool(getattr(first, "event_id", "").strip())
            and first.event_id == getattr(replay, "event_id", None)
            and getattr(replay, "replayed", None) is True
        )
        replay_case = HostConformanceCase(
            "idempotent-replay",
            replay_valid,
            (
                "idempotent-replay-confirmed"
                if replay_valid
                else "idempotent-replay-invalid"
            ),
            ("same-event-id", "replayed") if replay_valid else (),
        )
    except HostIntegrationConformanceError as error:
        replay_case = HostConformanceCase(
            "idempotent-replay", False, error.diagnostic
        )
    except Exception:
        replay_case = HostConformanceCase(
            "idempotent-replay", False, "unexpected-failure"
        )
    cas_case = _expected_failure(
        "cas-conflict",
        "state-version-conflict",
        lambda: coordinator_port.record(EventAppendProbe(
            probe.valid_session_id,
            0,
            "conformance-cas-conflict",
            "sha256:" + "b" * 64,
        )),
    )
    combined = HostConformanceCase(
        "append_only_event_coordination",
        replay_case.passed and cas_case.passed,
        (
            "append-only-coordination-enforced"
            if replay_case.passed and cas_case.passed
            else replay_case.diagnostic if not replay_case.passed else cas_case.diagnostic
        ),
    )
    return combined, replay_case, cas_case


def _artifact_protection_case(artifacts) -> HostConformanceCase:
    """只透過 ArtifactStorePort.put_bytes 驗證 restricted artifact 保護。"""

    content = b"workflow-skill-router-host-conformance"
    try:
        reference = artifacts.put_bytes(
            content,
            "application/octet-stream",
            "restricted",
            "host-conformance",
        )
    except Exception:
        return HostConformanceCase(
            "artifact-protection", False, "artifact-protection-failed"
        )

    expected_digest = "sha256:" + sha256(content).hexdigest()
    protection_kind = getattr(reference, "protection_kind", None)
    protection_ref = getattr(reference, "protection_ref", None)
    normalized_protection_kind = (
        protection_kind.strip().casefold()
        if isinstance(protection_kind, str)
        else ""
    )
    normalized_protection_ref = (
        protection_ref.strip() if isinstance(protection_ref, str) else ""
    )
    unsafe_location = any(
        getattr(reference, field, None)
        for field in ("path", "location", "relative_path", "url")
    )
    valid = (
        getattr(reference, "digest", None) == expected_digest
        and getattr(reference, "media_type", None) == "application/octet-stream"
        and getattr(reference, "sensitivity", None) == "restricted"
        and isinstance(protection_kind, str)
        and normalized_protection_kind not in {"", "none"}
        and isinstance(protection_ref, str)
        and bool(normalized_protection_ref)
        and not unsafe_location
        and "/" not in normalized_protection_ref
        and "\\" not in normalized_protection_ref
    )
    return HostConformanceCase(
        "artifact-protection",
        valid,
        (
            "protected-artifact-reference-confirmed"
            if valid
            else "artifact-reference-invalid"
        ),
        ("restricted", "protected") if valid else (),
    )


def _composition_failure_report(manifest) -> HostConformanceReport:
    cases = (
        HostConformanceCase(
            "composition-happy-path", False, "composition-ports-invalid"
        ),
        *(
            HostConformanceCase(
                requirement.port_name,
                False,
                "composition-ports-invalid",
            )
            for requirement in manifest.ports
        ),
    )
    return HostConformanceReport(
        adapter_id=manifest.adapter_id,
        authority_label=manifest.authority_label,
        status="failed-development-conformance",
        production_authority_declared=manifest.production_authority,
        production_authority_verified=False,
        host_pilot_verified=False,
        hybrid_full=False,
        composition_root="workflow_skill_router.composition.open",
        service_type="unavailable",
        cases=cases,
    )


def run_host_conformance(
    adapter: HostConformanceAdapterPort,
    resources: ServerOwnedHostResources,
) -> HostConformanceReport:
    """透過 production composition root 執行離線、vendor-neutral Host conformance。"""

    manifest = validate_host_manifest(adapter.host_manifest())
    recording_adapter = _RecordingAdapter(adapter)
    try:
        service = open_router(
            resources.database,
            resources.artifact_root,
            recording_adapter,
            resources.request_authorizer,
            resources.instruction_content_resolver,
            resources.artifact_protector,
            resources.activation_preflight,
            resources.evaluation_ports,
            resources.clock,
            resources.id_factory,
        )
        ports = recording_adapter.require_captured_ports()
    except Exception:
        return _composition_failure_report(manifest)
    probe = adapter.build_conformance_probe()
    valid_context = RequestContext(
        probe.valid_session_id, "conformance-runner", "policy:conformance",
    )
    wrong_context = RequestContext(
        probe.wrong_session_id, "conformance-runner", "policy:conformance",
    )
    composition_case = HostConformanceCase(
        "composition-happy-path",
        service.__class__.__name__ == "RouterService",
        "composed-through-production-root",
    )
    authority_case = _runtime_authority_case(
        ports.runtime_authority, valid_context, wrong_context
    )
    try:
        authority = ports.runtime_authority.require(valid_context)
    except Exception:
        authority = None
    runtime_context_case = _runtime_context_case(
        ports.runtime_context, authority, probe
    )
    snapshot_case, snapshot_stale_case = _snapshot_repository_cases(
        ports.snapshots, probe
    )
    try:
        snapshot = ports.snapshots.require(probe.fresh_snapshot_ref)
    except Exception:
        snapshot = None
    policy_case = _policy_repository_case(ports.policies, valid_context)
    try:
        policy = ports.policies.require(7, valid_context.runtime_policy_snapshot_id)
    except Exception:
        policy = None
    route_validation_case = _route_validation_case(
        ports.validation_context,
        ports.route_validator,
        snapshot,
        policy,
        valid_context,
    )
    activation_preflight_case = _activation_preflight_case(
        ports.activation_preflight, valid_context, snapshot
    )
    receipt_case, receipt_forged_case, session_mismatch_case = (
        _receipt_verification_cases(
            ports.activation_preflight, valid_context, wrong_context, probe
        )
    )
    append_case, replay_case, cas_case = _append_coordination_cases(
        ports.coordinator, probe
    )
    scheduler_case, native_goal_case = _scheduler_case(
        ports.scheduler, valid_context, probe
    )
    gate_command = SimpleNamespace(
        context=valid_context,
        workflow_run_id="run:conformance",
        phase_id="phase:conformance",
        expected_state_version=0,
        expected_evidence_digest="sha256:" + "c" * 64,
        idempotency_key="gate-persist:conformance",
    )
    gate_context_case = _gate_context_case(ports.gate_context, gate_command)
    try:
        gate_request = ports.gate_context.build_from_current_projection(gate_command)
    except Exception:
        gate_request = None
    gate_evaluator_case = _gate_evaluator_case(ports.gate_evaluator, gate_request)
    try:
        gate_result = ports.gate_evaluator.evaluate(gate_request)
    except Exception:
        gate_result = None
    gate_coordinator_case = _gate_coordinator_case(
        ports.gate_coordinator, gate_command, gate_result
    )
    artifact_case = _artifact_protection_case(ports.artifacts)
    evaluation_case = _evaluation_case(ports.evaluation, valid_context, probe)
    cases: list[HostConformanceCase] = [
        composition_case,
        authority_case,
        runtime_context_case,
        scheduler_case,
        snapshot_case,
        policy_case,
        route_validation_case,
        activation_preflight_case,
        receipt_case,
        append_case,
        gate_context_case,
        gate_evaluator_case,
        gate_coordinator_case,
        _renamed_case("artifact_protection", artifact_case),
        evaluation_case,
        snapshot_stale_case,
        receipt_forged_case,
        session_mismatch_case,
        replay_case,
        cas_case,
        native_goal_case,
        artifact_case,
    ]
    passed = all(item.passed for item in cases)
    return HostConformanceReport(
        adapter_id=manifest.adapter_id,
        authority_label=manifest.authority_label,
        status=(
            "passed-development-conformance" if passed
            else "failed-development-conformance"
        ),
        production_authority_declared=manifest.production_authority,
        production_authority_verified=False,
        host_pilot_verified=False,
        hybrid_full=False,
        composition_root="workflow_skill_router.composition.open",
        service_type=service.__class__.__name__,
        cases=tuple(cases),
    )
