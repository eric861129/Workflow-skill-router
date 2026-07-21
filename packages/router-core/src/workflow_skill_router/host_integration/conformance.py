from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256

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


def run_host_conformance(
    adapter: HostConformanceAdapterPort,
    resources: ServerOwnedHostResources,
) -> HostConformanceReport:
    """透過 production composition root 執行離線、vendor-neutral Host conformance。"""

    manifest = validate_host_manifest(adapter.host_manifest())
    recording_adapter = _RecordingAdapter(adapter)
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
    probe = adapter.build_conformance_probe()
    valid_context = RequestContext(
        probe.valid_session_id, "conformance-runner", "policy:conformance",
    )
    wrong_context = RequestContext(
        probe.wrong_session_id, "conformance-runner", "policy:conformance",
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
            lambda: ports.snapshots.require(probe.stale_snapshot_ref),
        ),
        _expected_failure(
            "receipt-forged",
            "activation-receipt-invalid",
            lambda: ports.activation_preflight.verify_consumption_receipt(
                ReceiptProbe(valid_context, probe.forged_receipt_ref)
            ),
        ),
        _expected_failure(
            "session-mismatch",
            "request-session-mismatch",
            lambda: ports.activation_preflight.verify_consumption_receipt(
                ReceiptProbe(wrong_context, probe.valid_receipt_ref)
            ),
        ),
    ]

    first = ports.coordinator.record(EventAppendProbe(
        probe.valid_session_id,
        0,
        "conformance-idempotent",
        "sha256:" + "a" * 64,
    ))
    replay = ports.coordinator.record(EventAppendProbe(
        probe.valid_session_id,
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
        lambda: ports.coordinator.record(EventAppendProbe(
            probe.valid_session_id,
            0,
            "conformance-cas-conflict",
            "sha256:" + "b" * 64,
        )),
    ))
    cases.append(_expected_failure(
        "native-goal-refresh",
        "goal-resume-refresh-required",
        lambda: ports.scheduler.next(
            NativeGoalResumeProbe(valid_context, probe.native_goal_id, ()),
            require_resume_refresh=True,
        ),
    ))
    cases.append(_artifact_protection_case(ports.artifacts))
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
