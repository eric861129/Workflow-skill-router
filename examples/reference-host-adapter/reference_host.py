from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from workflow_skill_router.composition import RouterCompositionPorts
from workflow_skill_router.host_integration import (
    HOST_MANIFEST_SCHEMA,
    REFERENCE_AUTHORITY_LABEL,
    HostConformanceProbeInputs,
    HostIntegrationConformanceError,
    HostIntegrationManifest,
    HostPortRequirement,
    ServerOwnedHostResources,
    run_host_conformance,
)
from workflow_skill_router.service_models import NextWorkResult, RouterDiagnostics, RouterStatusView


VALID_SESSION = "session:reference"


class _Clock:
    def now_utc(self):
        return "2026-07-21T00:00:00+00:00"


class _Ids:
    def __init__(self) -> None:
        self.sequence = 0

    def new_event_id(self) -> str:
        self.sequence += 1
        return f"event:reference-{self.sequence}"


class _RequestAuthorizer:
    def _require(self, context) -> None:
        if context.session_id != VALID_SESSION:
            raise HostIntegrationConformanceError("request-session-mismatch")

    def authorize_read(self, context) -> None:
        self._require(context)

    def authorize_mutation(self, context, expected_state_version: int) -> None:
        del expected_state_version
        self._require(context)

    def authorize_reporting(self, context, observation: object) -> None:
        del observation
        self._require(context)


class _ActivationPreflight:
    valid_receipt_ref = "receipt:reference-valid"

    def bind_single_use_after_validation(self, command, result, snapshot):
        del command, snapshot
        return result

    def verify_consumption_receipt(self, command) -> None:
        if command.context.session_id != VALID_SESSION:
            raise HostIntegrationConformanceError("request-session-mismatch")
        if command.activation_receipt_ref != self.valid_receipt_ref:
            raise HostIntegrationConformanceError("activation-receipt-invalid")


class _RejectingArtifactProtector:
    def protect(self, content: bytes, purpose: str):
        del content, purpose
        raise HostIntegrationConformanceError("artifact-protection-failed")

    def put_bytes(
        self,
        content: bytes,
        media_type: str,
        classification: str,
        purpose: str,
    ):
        del content, media_type, classification, purpose
        raise HostIntegrationConformanceError("artifact-protection-failed")


class _EvaluationPorts:
    def run(self, command):
        del command
        raise HostIntegrationConformanceError("reference-evaluation-disabled")

    def compare(self, command):
        del command
        raise HostIntegrationConformanceError("reference-evaluation-disabled")

    def export(self, command):
        del command
        raise HostIntegrationConformanceError("reference-evaluation-disabled")


class _SnapshotRepository:
    fresh_ref = "snapshot:reference-fresh"
    stale_ref = "snapshot:reference-stale"

    def require(self, snapshot_id: str):
        if snapshot_id == self.stale_ref:
            raise HostIntegrationConformanceError("snapshot-stale")
        if snapshot_id != self.fresh_ref:
            raise HostIntegrationConformanceError("snapshot-unavailable")
        return {"snapshot_id": snapshot_id, "fresh": True}


@dataclass(frozen=True, slots=True)
class _AppendResult:
    event_id: str
    resulting_state_version: int
    replayed: bool


class _AppendOnlyCoordinator:
    def __init__(self, ids: _Ids) -> None:
        self._ids = ids
        self._version = 0
        self._replays: dict[tuple[str, str], tuple[str, _AppendResult]] = {}

    def record(self, command):
        if command.session_id != VALID_SESSION:
            raise HostIntegrationConformanceError("request-session-mismatch")
        key = (command.session_id, command.idempotency_key)
        existing = self._replays.get(key)
        if existing is not None:
            digest, result = existing
            if digest != command.payload_digest:
                raise HostIntegrationConformanceError("idempotency-conflict")
            return _AppendResult(result.event_id, result.resulting_state_version, True)
        if command.expected_state_version != self._version:
            raise HostIntegrationConformanceError("state-version-conflict")
        self._version += 1
        result = _AppendResult(self._ids.new_event_id(), self._version, False)
        self._replays[key] = (command.payload_digest, result)
        return result


class _Scheduler:
    required_refresh = ("goal", "workspace", "capabilities", "evidence")

    def next(self, query, require_resume_refresh: bool = True):
        if query.context.session_id != VALID_SESSION:
            raise HostIntegrationConformanceError("request-session-mismatch")
        if require_resume_refresh and tuple(query.refreshed_contexts) != self.required_refresh:
            raise HostIntegrationConformanceError("goal-resume-refresh-required")
        return NextWorkResult("ready", (), None)


class _Noop:
    def __getattr__(self, name):
        del name

        def method(*args, **kwargs):
            del args, kwargs
            return None

        return method


class _StatusReader:
    def read(self, query):
        return RouterStatusView(
            getattr(query, "goal_binding_id", None),
            getattr(query, "workflow_run_id", None),
            0,
            None,
            False,
        )


def _requirement(
    port_name: str,
    capability_id: str,
    required_receipt: str,
    freshness_condition: str,
    diagnostic: str,
) -> HostPortRequirement:
    return HostPortRequirement(
        port_name=port_name,
        capability_id=capability_id,
        authority_owner="verified-host",
        trusted_input="server-owned verified integration input",
        required_receipt=required_receipt,
        freshness_condition=freshness_condition,
        fail_closed_behavior="reject operation without changing Router or Host state",
        public_safe_diagnostic=diagnostic,
    )


def _manifest() -> HostIntegrationManifest:
    definitions = (
        ("runtime_authority", "verified-host-runtime", "runtime-authority-receipt", "current session", "runtime-authority-unavailable"),
        ("runtime_context", "runtime-authority-receipt", "runtime-authority-receipt", "current snapshot", "runtime-context-unavailable"),
        ("scheduler", "verified-host-scheduler", "scheduler-decision-receipt", "resume context refreshed", "goal-resume-refresh-required"),
        ("snapshot_repository", "verified-capability-snapshot", "snapshot-receipt", "risk-specific snapshot TTL", "snapshot-stale"),
        ("policy_repository", "runtime-policy-snapshot", "policy-receipt", "current policy revision", "policy-stale"),
        ("route_validation", "route-validation-authority", "route-validation-receipt", "current route context", "route-validation-unavailable"),
        ("activation_preflight", "activation-preflight", "activation-lease", "single-use lease", "activation-preflight-failed"),
        ("activation_receipt_verification", "activation-receipt-verifier", "activation-consumption-receipt", "bound session and route", "activation-receipt-invalid"),
        ("append_only_event_coordination", "verified-event-store", "event-append-receipt", "current state version", "state-version-conflict"),
        ("gate_context", "verified-evidence-store", "evidence-receipt", "current evidence digest", "evidence-stale"),
        ("gate_evaluator", "gate-authority", "gate-decision-receipt", "current gate revision", "gate-evaluation-unavailable"),
        ("gate_coordinator", "gate-result-store", "gate-append-receipt", "current state version", "gate-persist-failed"),
        ("artifact_protection", "verified-artifact-protector", "protection-receipt", "verified protection before write", "artifact-protection-failed"),
        ("evaluation", "configured-evaluation-adapter", "evaluation-authorization", "sealed case and authorization", "reference-evaluation-disabled"),
    )
    return HostIntegrationManifest(
        schema_version=HOST_MANIFEST_SCHEMA,
        adapter_id="reference-host-adapter",
        authority_label=REFERENCE_AUTHORITY_LABEL,
        production_authority=False,
        server_owned_configuration=True,
        ports=tuple(_requirement(*definition) for definition in definitions),
    )


class ReferenceHostAdapter:
    """僅供開發與 conformance；不具備正式 Host authority。"""

    def __init__(self) -> None:
        self.build_count = 0
        self.last_ports: RouterCompositionPorts | None = None

    def host_manifest(self) -> HostIntegrationManifest:
        return _manifest()

    def build_router_ports(
        self,
        *,
        database,
        artifact_root,
        request_authorizer,
        instruction_content_resolver,
        artifact_protector,
        activation_preflight,
        evaluation_ports,
        clock,
        id_factory,
    ) -> RouterCompositionPorts:
        del database, artifact_root, instruction_content_resolver, clock
        self.build_count += 1
        snapshots = _SnapshotRepository()
        coordinator = _AppendOnlyCoordinator(id_factory)
        scheduler = _Scheduler()
        noop = _Noop()
        ports = RouterCompositionPorts(
            authorizer=request_authorizer,
            runtime_authority=noop,
            runtime_context=noop,
            artifacts=artifact_protector,
            snapshot_codec=noop,
            runtime_sync=noop,
            projections=noop,
            planner=noop,
            scheduler=scheduler,
            snapshots=snapshots,
            policies=noop,
            validation_context=noop,
            route_validator=noop,
            activation_preflight=activation_preflight,
            coordinator=coordinator,
            gate_context=noop,
            gate_evaluator=noop,
            gate_coordinator=noop,
            status_reader=_StatusReader(),
            diagnostics_reader=lambda: RouterDiagnostics(0, 0, 0),
            evaluation=evaluation_ports,
        )
        self.last_ports = ports
        return ports

    def build_conformance_probe(self) -> HostConformanceProbeInputs:
        return HostConformanceProbeInputs(
            fresh_snapshot_ref=_SnapshotRepository.fresh_ref,
            stale_snapshot_ref=_SnapshotRepository.stale_ref,
            valid_receipt_ref=_ActivationPreflight.valid_receipt_ref,
            forged_receipt_ref="receipt:reference-forged",
            valid_session_id=VALID_SESSION,
            wrong_session_id="session:wrong",
            native_goal_id="native-goal:reference",
        )


def create_reference_adapter() -> ReferenceHostAdapter:
    return ReferenceHostAdapter()


def create_reference_server_resources(root: Path) -> ServerOwnedHostResources:
    return ServerOwnedHostResources(
        database=root / "reference-router.db",
        artifact_root=root / "reference-artifacts",
        request_authorizer=_RequestAuthorizer(),
        instruction_content_resolver=_Noop(),
        artifact_protector=_RejectingArtifactProtector(),
        activation_preflight=_ActivationPreflight(),
        evaluation_ports=_EvaluationPorts(),
        clock=_Clock(),
        id_factory=_Ids(),
    )


def public_reference_identity() -> dict[str, object]:
    manifest = _manifest()
    return {
        "adapter_id": manifest.adapter_id,
        "authority_label": manifest.authority_label,
        "production_authority_declared": manifest.production_authority,
        "production_authority_verified": False,
        "host_pilot_verified": False,
        "hybrid_full": False,
        "manifest_digest": "sha256:" + sha256(
            json.dumps(
                manifest.to_public_dict(), sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest(),
    }


def main() -> None:
    """執行開發用途 conformance，且只輸出可公開的診斷資訊。"""

    with TemporaryDirectory(prefix="workflow-skill-router-reference-host-") as temp:
        adapter = create_reference_adapter()
        resources = create_reference_server_resources(Path(temp))
        report = run_host_conformance(adapter, resources)
        print(json.dumps(report.to_public_dict(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
