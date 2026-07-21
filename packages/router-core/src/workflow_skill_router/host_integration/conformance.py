from __future__ import annotations

from collections.abc import Callable

from workflow_skill_router.composition import open as open_router
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
from workflow_skill_router.service_models import RequestContext


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


def run_host_conformance(adapter, resources: ServerOwnedHostResources) -> HostConformanceReport:
    """透過 production composition root 執行離線、vendor-neutral Host conformance。"""

    manifest = validate_host_manifest(adapter.host_manifest())
    service = open_router(
        resources.database,
        resources.artifact_root,
        adapter,
        resources.request_authorizer,
        resources.instruction_content_resolver,
        resources.artifact_protector,
        resources.activation_preflight,
        resources.evaluation_ports,
        resources.clock,
        resources.id_factory,
    )
    fixture = adapter.build_conformance_fixture()
    valid_context = RequestContext(
        fixture.valid_session_id, "conformance-runner", "policy:conformance",
    )
    wrong_context = RequestContext(
        fixture.wrong_session_id, "conformance-runner", "policy:conformance",
    )
    cases: list[HostConformanceCase] = [
        HostConformanceCase(
            "composition-happy-path",
            service.__class__.__name__ == "RouterService",
            "composed-through-production-root",
        ),
        _expected_failure(
            "snapshot-stale",
            "snapshot-stale",
            lambda: fixture.snapshots.require(fixture.stale_snapshot_ref),
        ),
        _expected_failure(
            "receipt-forged",
            "activation-receipt-invalid",
            lambda: fixture.activation_preflight.verify_consumption_receipt(
                ReceiptProbe(valid_context, fixture.forged_receipt_ref)
            ),
        ),
        _expected_failure(
            "session-mismatch",
            "request-session-mismatch",
            lambda: fixture.activation_preflight.verify_consumption_receipt(
                ReceiptProbe(wrong_context, fixture.valid_receipt_ref)
            ),
        ),
    ]

    first = fixture.coordinator.record(EventAppendProbe(
        fixture.valid_session_id,
        0,
        "conformance-idempotent",
        "sha256:" + "a" * 64,
    ))
    replay = fixture.coordinator.record(EventAppendProbe(
        fixture.valid_session_id,
        0,
        "conformance-idempotent",
        "sha256:" + "a" * 64,
    ))
    cases.append(HostConformanceCase(
        "idempotent-replay",
        first.event_id == replay.event_id and replay.replayed is True,
        "idempotent-replay-confirmed",
        ("same-event-id", "replayed"),
    ))
    cases.append(_expected_failure(
        "cas-conflict",
        "state-version-conflict",
        lambda: fixture.coordinator.record(EventAppendProbe(
            fixture.valid_session_id,
            0,
            "conformance-cas-conflict",
            "sha256:" + "b" * 64,
        )),
    ))
    cases.append(_expected_failure(
        "native-goal-refresh",
        "goal-resume-refresh-required",
        lambda: fixture.scheduler.next(
            NativeGoalResumeProbe(valid_context, fixture.native_goal_id, ()),
            require_resume_refresh=True,
        ),
    ))
    cases.append(_expected_failure(
        "artifact-protection-failure",
        "artifact-protection-failed",
        lambda: fixture.artifact_protector.protect(
            b"conformance-payload", "host-conformance",
        ),
    ))
    passed = all(item.passed for item in cases)
    return HostConformanceReport(
        adapter_id=manifest.adapter_id,
        authority_label=manifest.authority_label,
        status=(
            "passed-development-conformance" if passed
            else "failed-development-conformance"
        ),
        production_authority=manifest.production_authority,
        host_pilot_verified=False,
        hybrid_full=False,
        composition_root="workflow_skill_router.composition.open",
        service_type=service.__class__.__name__,
        cases=tuple(cases),
    )
