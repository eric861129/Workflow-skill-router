from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

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
from workflow_skill_router.persistence.artifacts import ArtifactRef
from workflow_skill_router.service_models import RouterDiagnostics, RouterStatusView


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


@dataclass(frozen=True, slots=True)
class _RuntimeAuthority:
    session_id: str
    runtime_fingerprint: str
    runtime_policy_snapshot_id: str
    verification_receipt_digest: str


class _RuntimeAuthorityRepository:
    def require(self, context):
        if context.session_id != VALID_SESSION:
            raise HostIntegrationConformanceError("request-session-mismatch")
        return _RuntimeAuthority(
            session_id=context.session_id,
            runtime_fingerprint="runtime:reference",
            runtime_policy_snapshot_id=context.runtime_policy_snapshot_id,
            verification_receipt_digest="sha256:" + "1" * 64,
        )


@dataclass(frozen=True, slots=True)
class _RuntimeContextResult:
    session_id: str
    snapshot_ref: str
    fresh: bool
    runtime_fingerprint: str
    runtime_policy_snapshot_id: str
    authority_receipt_digest: str


class _RuntimeContext:
    expected_runtime_fingerprint = "runtime:reference"
    expected_policy_snapshot_id = "policy:conformance"
    expected_authority_receipt = "sha256:" + "1" * 64

    def sync_verified(self, request):
        authority = request.authority
        if (
            authority is None
            or authority.session_id != VALID_SESSION
            or authority.runtime_fingerprint != self.expected_runtime_fingerprint
            or authority.runtime_policy_snapshot_id != self.expected_policy_snapshot_id
            or authority.verification_receipt_digest
            != self.expected_authority_receipt
        ):
            raise HostIntegrationConformanceError("runtime-authority-unavailable")
        if request.host_snapshot_ref != _SnapshotRepository.fresh_ref:
            raise HostIntegrationConformanceError("runtime-context-unavailable")
        return _RuntimeContextResult(
            authority.session_id,
            request.host_snapshot_ref,
            True,
            authority.runtime_fingerprint,
            authority.runtime_policy_snapshot_id,
            authority.verification_receipt_digest,
        )


@dataclass(frozen=True, slots=True)
class _ActivationBindingResult:
    valid: bool
    activation_lease_ref: str
    route_id: str
    session_id: str
    snapshot_ref: str


class _ActivationPreflight:
    valid_receipt_ref = "receipt:reference-valid"

    def __init__(self) -> None:
        self._bound_routes: set[str] = set()
        self._receipt_route: str | None = None

    def bind_single_use_after_validation(self, command, result, snapshot):
        if command.context.session_id != VALID_SESSION:
            raise HostIntegrationConformanceError("request-session-mismatch")
        snapshot_ref = (
            snapshot.get("snapshot_id")
            if isinstance(snapshot, dict)
            else getattr(snapshot, "snapshot_id", None)
        )
        if getattr(result, "valid", None) is not True or not snapshot_ref:
            raise HostIntegrationConformanceError("activation-preflight-failed")
        if command.route_id in self._bound_routes:
            raise HostIntegrationConformanceError("activation-lease-already-bound")
        self._bound_routes.add(command.route_id)
        self._receipt_route = command.route_id
        return _ActivationBindingResult(
            valid=True,
            activation_lease_ref="activation-lease:reference",
            route_id=command.route_id,
            session_id=command.context.session_id,
            snapshot_ref=snapshot_ref,
        )

    def verify_consumption_receipt(self, command) -> None:
        if command.context.session_id != VALID_SESSION:
            raise HostIntegrationConformanceError("request-session-mismatch")
        if command.activation_receipt_ref != self.valid_receipt_ref:
            raise HostIntegrationConformanceError("activation-receipt-invalid")
        if command.route_id != self._receipt_route:
            raise HostIntegrationConformanceError(
                "activation-receipt-route-mismatch"
            )


class _ReferenceArtifactStore:
    def put_bytes(
        self,
        content: bytes,
        media_type: str,
        classification: str,
        purpose: str,
    ):
        del purpose
        digest = "sha256:" + sha256(content).hexdigest()
        return ArtifactRef(
            digest=digest,
            media_type=media_type,
            sensitivity=classification,
            protection_kind="reference-envelope",
            protection_ref="key:reference-conformance",
        )


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
class _PolicySnapshot:
    revision: int
    runtime_policy_snapshot_id: str
    receipt_ref: str


class _PolicyRepository:
    current_revision = 7

    def require(self, policy_revision: int, runtime_policy_snapshot_id: str):
        if policy_revision != self.current_revision:
            raise HostIntegrationConformanceError("policy-stale")
        if runtime_policy_snapshot_id != "policy:conformance":
            raise HostIntegrationConformanceError("policy-unavailable")
        return _PolicySnapshot(
            policy_revision,
            runtime_policy_snapshot_id,
            "policy-receipt:reference",
        )


@dataclass(frozen=True, slots=True)
class _RouteValidationContext:
    session_id: str
    current: bool
    receipt_ref: str


class _ValidationContext:
    def current_for(self, command, snapshot, policy):
        if command.context.session_id != VALID_SESSION:
            raise HostIntegrationConformanceError("request-session-mismatch")
        if not snapshot or not isinstance(policy, _PolicySnapshot):
            raise HostIntegrationConformanceError("route-validation-unavailable")
        return _RouteValidationContext(
            session_id=command.context.session_id,
            current=True,
            receipt_ref="route-context-receipt:reference",
        )


class _RouteValidator:
    def validate(self, request, snapshot, policy, context):
        if (
            not snapshot
            or not isinstance(policy, _PolicySnapshot)
            or not isinstance(context, _RouteValidationContext)
            or context.current is not True
        ):
            raise HostIntegrationConformanceError("route-validation-unavailable")
        if getattr(request, "allowed", None) is not True:
            raise HostIntegrationConformanceError("route-validation-rejected")
        snapshot_ref = (
            snapshot.get("snapshot_id")
            if isinstance(snapshot, dict)
            else getattr(snapshot, "snapshot_id", None)
        )
        return SimpleNamespace(
            valid=True,
            receipt_ref="route-validation-receipt:reference",
            route_id=request.route_id,
            snapshot_ref=snapshot_ref,
            policy_revision=policy.revision,
            context_receipt_ref=context.receipt_ref,
        )


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
        return SimpleNamespace(
            status="ready",
            receipt_ref="scheduler-decision-receipt:reference",
            session_id=query.context.session_id,
            native_goal_id=query.goal_binding_id,
            refreshed_contexts=tuple(query.refreshed_contexts),
        )


@dataclass(frozen=True, slots=True)
class _GateContextResult:
    workflow_run_id: str
    phase_id: str
    current: bool
    evidence_digest: str


class _GateContext:
    def build_from_current_projection(self, command):
        if command.context.session_id != VALID_SESSION:
            raise HostIntegrationConformanceError("request-session-mismatch")
        if not str(command.expected_evidence_digest).startswith("sha256:"):
            raise HostIntegrationConformanceError("evidence-stale")
        return _GateContextResult(
            command.workflow_run_id,
            command.phase_id,
            True,
            command.expected_evidence_digest,
        )


@dataclass(frozen=True, slots=True)
class _GateEvaluationResult:
    status: str
    passed: bool
    evidence_digest: str
    decision_ref: str


class _GateEvaluator:
    def evaluate(self, request):
        if (
            getattr(request, "current", None) is not True
            or not str(getattr(request, "evidence_digest", "")).startswith("sha256:")
        ):
            raise HostIntegrationConformanceError("gate-evaluation-unavailable")
        return _GateEvaluationResult(
            "evaluated",
            True,
            request.evidence_digest,
            "gate-decision:reference",
        )


@dataclass(frozen=True, slots=True)
class _GatePersistReceipt:
    state_version: int
    receipt_ref: str
    idempotency_key: str


class _GateCoordinator:
    def __init__(self) -> None:
        self._state_version = 0
        self._idempotency_keys: set[str] = set()

    def persist_result(self, command, result):
        if command.context.session_id != VALID_SESSION:
            raise HostIntegrationConformanceError("request-session-mismatch")
        if (
            getattr(result, "status", None) != "evaluated"
            or getattr(result, "passed", None) is not True
        ):
            raise HostIntegrationConformanceError("gate-persist-failed")
        if command.expected_state_version != self._state_version:
            raise HostIntegrationConformanceError("state-version-conflict")
        if command.idempotency_key in self._idempotency_keys:
            raise HostIntegrationConformanceError("gate-persist-failed")
        self._idempotency_keys.add(command.idempotency_key)
        self._state_version += 1
        return _GatePersistReceipt(
            self._state_version,
            "gate-append-receipt:reference",
            command.idempotency_key,
        )


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
            runtime_authority=_RuntimeAuthorityRepository(),
            runtime_context=_RuntimeContext(),
            artifacts=artifact_protector,
            snapshot_codec=noop,
            runtime_sync=noop,
            projections=noop,
            planner=noop,
            scheduler=scheduler,
            snapshots=snapshots,
            policies=_PolicyRepository(),
            validation_context=_ValidationContext(),
            route_validator=_RouteValidator(),
            activation_preflight=activation_preflight,
            coordinator=coordinator,
            gate_context=_GateContext(),
            gate_evaluator=_GateEvaluator(),
            gate_coordinator=_GateCoordinator(),
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
            evaluation_mode="unavailable",
        )


def create_reference_adapter() -> ReferenceHostAdapter:
    return ReferenceHostAdapter()


def create_reference_server_resources(root: Path) -> ServerOwnedHostResources:
    return ServerOwnedHostResources(
        database=root / "reference-router.db",
        artifact_root=root / "reference-artifacts",
        request_authorizer=_RequestAuthorizer(),
        instruction_content_resolver=_Noop(),
        artifact_protector=_ReferenceArtifactStore(),
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
