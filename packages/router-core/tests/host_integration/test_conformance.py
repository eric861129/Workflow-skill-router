from __future__ import annotations

import importlib.util
import sys
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from workflow_skill_router.composition import RouterCompositionPorts, open as open_router
from workflow_skill_router.host_integration import (
    HostIntegrationContractError,
    REQUIRED_HOST_PORTS,
    run_host_conformance,
    validate_host_manifest,
)
from workflow_skill_router.ports import (
    HostConformanceAdapterPort,
    HostIntegrationAdapterPort,
)


ROOT = Path(__file__).resolve().parents[4]
REFERENCE_PATH = ROOT / "examples/reference-host-adapter/reference_host.py"


def load_reference_module():
    spec = importlib.util.spec_from_file_location("reference_host_adapter", REFERENCE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("reference-adapter-unloadable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class HostIntegrationConformanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.reference = load_reference_module()
        self.adapter = self.reference.create_reference_adapter()
        self.resources = self.reference.create_reference_server_resources(self.root)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def report(self):
        return run_host_conformance(self.adapter, self.resources)

    def report_with_replacements(self, **replacements):
        delegate = self.reference.create_reference_adapter()

        class ReplacementAdapter:
            def host_manifest(self):
                return delegate.host_manifest()

            def build_router_ports(self, **kwargs):
                return replace(
                    delegate.build_router_ports(**kwargs),
                    **replacements,
                )

            def build_conformance_probe(self):
                return delegate.build_conformance_probe()

        return run_host_conformance(ReplacementAdapter(), self.resources)

    def test_manifest_covers_every_required_host_capability_without_secret_values(self) -> None:
        manifest = validate_host_manifest(self.adapter.host_manifest())

        self.assertEqual(set(REQUIRED_HOST_PORTS), {item.port_name for item in manifest.ports})
        self.assertFalse(manifest.production_authority)
        self.assertEqual("reference-not-production-authority", manifest.authority_label)
        public = json.dumps(manifest.to_public_dict(), ensure_ascii=False, sort_keys=True)
        for forbidden in (
            "executable_path", "environment_value", "secret_value",
            "artifact_location", "receipt_authority_value",
        ):
            self.assertNotIn(forbidden, public)
        self.assertNotRegex(public, r"[A-Za-z]:\\|/tmp/|/home/")
        for item in manifest.ports:
            self.assertTrue(item.authority_owner)
            self.assertTrue(item.trusted_input)
            self.assertTrue(item.required_receipt)
            self.assertTrue(item.freshness_condition)
            self.assertTrue(item.fail_closed_behavior)
            self.assertRegex(item.public_safe_diagnostic, r"^[a-z0-9-]+$")

    def test_happy_path_composes_only_through_production_composition_root(self) -> None:
        self.assertIsInstance(self.adapter, HostIntegrationAdapterPort)
        self.assertIsInstance(self.adapter, HostConformanceAdapterPort)

        report = self.report()

        self.assertEqual("passed-development-conformance", report.status)
        self.assertEqual(
            "workflow_skill_router.composition.open", report.composition_root,
        )
        self.assertEqual("RouterService", report.service_type)
        self.assertEqual(1, self.adapter.build_count)
        self.assertIsInstance(self.adapter.last_ports, RouterCompositionPorts)
        self.assertTrue(report.case("composition-happy-path").passed)

    def test_every_required_manifest_port_has_a_passing_captured_port_case(self) -> None:
        report = self.report()

        for port_name in REQUIRED_HOST_PORTS:
            with self.subTest(port_name=port_name):
                case = report.case(port_name)
                self.assertTrue(case.passed)
                self.assertRegex(case.diagnostic, r"^[a-z0-9-]+$")
                self.assertEqual((), case.private_details)

    def test_permissive_required_ports_cannot_pass_development_conformance(self) -> None:
        affected_cases = (
            ("runtime_authority", "runtime_authority"),
            ("runtime_context", "runtime_context"),
            ("scheduler", "scheduler"),
            ("snapshots", "snapshot_repository"),
            ("policies", "policy_repository"),
            ("validation_context", "route_validation"),
            ("route_validator", "route_validation"),
            ("activation_preflight", "activation_preflight"),
            ("activation_preflight", "activation_receipt_verification"),
            ("coordinator", "append_only_event_coordination"),
            ("gate_context", "gate_context"),
            ("gate_evaluator", "gate_evaluator"),
            ("gate_coordinator", "gate_coordinator"),
            ("artifacts", "artifact_protection"),
            ("evaluation", "evaluation"),
        )

        class PermissivePort:
            def __getattr__(self, name):
                del name

                def operation(*args, **kwargs):
                    del args, kwargs
                    return None

                return operation

        for field_name, case_name in affected_cases:
            with self.subTest(field_name=field_name):
                delegate = self.reference.create_reference_adapter()
                permissive = PermissivePort()

                class AdversarialAdapter:
                    last_ports = None

                    def host_manifest(self):
                        return delegate.host_manifest()

                    def build_router_ports(self, **kwargs):
                        self.last_ports = replace(
                            delegate.build_router_ports(**kwargs),
                            **{field_name: permissive},
                        )
                        return self.last_ports

                    def build_conformance_probe(self):
                        return delegate.build_conformance_probe()

                adapter = AdversarialAdapter()
                report = run_host_conformance(adapter, self.resources)

                self.assertIs(permissive, getattr(adapter.last_ports, field_name))
                self.assertEqual("failed-development-conformance", report.status)
                self.assertFalse(report.case(case_name).passed)

    def test_configured_evaluation_port_must_return_verifiable_receipts(self) -> None:
        delegate = self.reference.create_reference_adapter()

        class ConfiguredEvaluation:
            def result(self, operation, command, receipt_field, receipt_value):
                if command.context.session_id != self_reference.VALID_SESSION:
                    raise self_reference.HostIntegrationConformanceError(
                        "request-session-mismatch"
                    )
                return SimpleNamespace(
                    **{receipt_field: receipt_value},
                    operation=operation,
                    session_id=command.context.session_id,
                    sealed_input_ref=command.sealed_input_ref,
                    authorization_ref=command.authorization_ref,
                )

            def run(self, command):
                return self.result(
                    "run", command, "evaluation_ref", "evaluation:reference"
                )

            def compare(self, command):
                return self.result(
                    "compare", command, "comparison_ref", "comparison:reference"
                )

            def export(self, command):
                return self.result(
                    "export", command, "artifact_ref", "artifact:reference"
                )

        self_reference = self.reference

        class ConfiguredAdapter:
            def host_manifest(self):
                return delegate.host_manifest()

            def build_router_ports(self, **kwargs):
                return replace(
                    delegate.build_router_ports(**kwargs),
                    evaluation=ConfiguredEvaluation(),
                )

            def build_conformance_probe(self):
                base = delegate.build_conformance_probe()
                return replace(base, evaluation_mode="configured")

        report = run_host_conformance(ConfiguredAdapter(), self.resources)

        self.assertEqual("passed-development-conformance", report.status)
        self.assertTrue(report.case("evaluation").passed)
        self.assertEqual(
            "evaluation-configured-receipts-confirmed",
            report.case("evaluation").diagnostic,
        )

    def test_deny_all_route_validator_cannot_pass_route_conformance(self) -> None:
        reference = self.reference

        class DenyAllRouteValidator:
            def validate(self, request, snapshot, policy, context):
                del request, snapshot, policy, context
                raise reference.HostIntegrationConformanceError(
                    "route-validation-rejected"
                )

        report = self.report_with_replacements(
            route_validator=DenyAllRouteValidator()
        )

        self.assertEqual("failed-development-conformance", report.status)
        self.assertFalse(report.case("route_validation").passed)

    def test_unbound_configured_evaluation_receipts_fail_conformance(self) -> None:
        delegate = self.reference.create_reference_adapter()

        class UnboundEvaluation:
            def __init__(self):
                self.calls = []

            def run(self, command):
                self.calls.append(("run", command.context.session_id))
                return SimpleNamespace(evaluation_ref="evaluation:unbound")

            def compare(self, command):
                self.calls.append(("compare", command.context.session_id))
                return SimpleNamespace(comparison_ref="comparison:unbound")

            def export(self, command):
                self.calls.append(("export", command.context.session_id))
                return SimpleNamespace(artifact_ref="artifact:unbound")

        unbound = UnboundEvaluation()

        class UnboundEvaluationAdapter:
            def host_manifest(self):
                return delegate.host_manifest()

            def build_router_ports(self, **kwargs):
                return replace(
                    delegate.build_router_ports(**kwargs),
                    evaluation=unbound,
                )

            def build_conformance_probe(self):
                return replace(
                    delegate.build_conformance_probe(),
                    evaluation_mode="configured",
                )

        report = run_host_conformance(UnboundEvaluationAdapter(), self.resources)

        self.assertEqual("failed-development-conformance", report.status)
        self.assertFalse(report.case("evaluation").passed)
        self.assertEqual(
            {
                (operation, session)
                for operation in ("run", "compare", "export")
                for session in (self.reference.VALID_SESSION, "session:wrong")
            },
            set(unbound.calls),
        )

    def test_session_blind_receiptless_scheduler_fails_conformance(self) -> None:
        reference = self.reference

        class SessionBlindScheduler:
            def next(self, query, require_resume_refresh=True):
                if require_resume_refresh and not query.refreshed_contexts:
                    raise reference.HostIntegrationConformanceError(
                        "goal-resume-refresh-required"
                    )
                return SimpleNamespace(status="ready")

        report = self.report_with_replacements(scheduler=SessionBlindScheduler())

        self.assertEqual("failed-development-conformance", report.status)
        self.assertFalse(report.case("scheduler").passed)

    def test_runtime_context_accepting_unrelated_authority_fails_conformance(self) -> None:
        reference = self.reference

        class AuthorityBlindRuntimeContext:
            def sync_verified(self, request):
                if request.host_snapshot_ref == self.reference._SnapshotRepository.stale_ref:
                    raise reference.HostIntegrationConformanceError(
                        "runtime-context-unavailable"
                    )
                return SimpleNamespace(
                    session_id=self.reference.VALID_SESSION,
                    snapshot_ref=request.host_snapshot_ref,
                    fresh=True,
                )

            def __init__(self, reference_module):
                self.reference = reference_module

        report = self.report_with_replacements(
            runtime_context=AuthorityBlindRuntimeContext(reference)
        )

        self.assertEqual("failed-development-conformance", report.status)
        self.assertFalse(report.case("runtime_context").passed)

    def test_runtime_context_accepting_same_session_mismatched_authority_fails(self) -> None:
        reference = self.reference

        class SessionOnlyRuntimeContext:
            def sync_verified(self, request):
                if request.authority.session_id != reference.VALID_SESSION:
                    raise reference.HostIntegrationConformanceError(
                        "runtime-authority-unavailable"
                    )
                if request.host_snapshot_ref == reference._SnapshotRepository.stale_ref:
                    raise reference.HostIntegrationConformanceError(
                        "runtime-context-unavailable"
                    )
                return SimpleNamespace(
                    session_id=request.authority.session_id,
                    snapshot_ref=request.host_snapshot_ref,
                    fresh=True,
                    runtime_fingerprint=request.authority.runtime_fingerprint,
                    runtime_policy_snapshot_id=(
                        request.authority.runtime_policy_snapshot_id
                    ),
                    authority_receipt_digest=(
                        request.authority.verification_receipt_digest
                    ),
                )

        report = self.report_with_replacements(
            runtime_context=SessionOnlyRuntimeContext()
        )

        self.assertEqual("failed-development-conformance", report.status)
        self.assertFalse(report.case("runtime_context").passed)

    def test_malformed_runtime_authority_digest_fails_conformance(self) -> None:
        reference = self.reference

        class MalformedReceiptAuthority:
            def require(self, context):
                if context.session_id != reference.VALID_SESSION:
                    raise reference.HostIntegrationConformanceError(
                        "request-session-mismatch"
                    )
                return SimpleNamespace(
                    session_id=context.session_id,
                    runtime_fingerprint="runtime:reference",
                    runtime_policy_snapshot_id=context.runtime_policy_snapshot_id,
                    verification_receipt_digest="sha256:",
                )

        report = self.report_with_replacements(
            runtime_authority=MalformedReceiptAuthority()
        )

        self.assertEqual("failed-development-conformance", report.status)
        self.assertFalse(report.case("runtime_authority").passed)

    def test_empty_prefixed_route_and_scheduler_receipts_fail_conformance(self) -> None:
        reference = self.reference

        class EmptyReceiptRouteValidator:
            def validate(self, request, snapshot, policy, context):
                if request.allowed is not True:
                    raise reference.HostIntegrationConformanceError(
                        "route-validation-rejected"
                    )
                return SimpleNamespace(
                    valid=True,
                    receipt_ref="route-validation-receipt:",
                    route_id=request.route_id,
                    snapshot_ref=snapshot["snapshot_id"],
                    policy_revision=policy.revision,
                    context_receipt_ref=context.receipt_ref,
                )

        class EmptyReceiptScheduler:
            required_refresh = ("goal", "workspace", "capabilities", "evidence")

            def next(self, query, require_resume_refresh=True):
                if query.context.session_id != reference.VALID_SESSION:
                    raise reference.HostIntegrationConformanceError(
                        "request-session-mismatch"
                    )
                if require_resume_refresh and tuple(query.refreshed_contexts) != self.required_refresh:
                    raise reference.HostIntegrationConformanceError(
                        "goal-resume-refresh-required"
                    )
                return SimpleNamespace(
                    status="ready",
                    session_id=query.context.session_id,
                    native_goal_id=query.goal_binding_id,
                    refreshed_contexts=tuple(query.refreshed_contexts),
                    receipt_ref="scheduler-decision-receipt:",
                )

        route_report = self.report_with_replacements(
            route_validator=EmptyReceiptRouteValidator()
        )
        scheduler_report = self.report_with_replacements(
            scheduler=EmptyReceiptScheduler()
        )

        self.assertFalse(route_report.case("route_validation").passed)
        self.assertFalse(scheduler_report.case("scheduler").passed)

    def test_policy_repository_accepting_wrong_runtime_snapshot_fails(self) -> None:
        reference = self.reference

        class PolicySnapshotBlindRepository:
            def require(self, policy_revision, runtime_policy_snapshot_id):
                if policy_revision != 7:
                    raise reference.HostIntegrationConformanceError("policy-stale")
                return SimpleNamespace(
                    revision=policy_revision,
                    runtime_policy_snapshot_id=runtime_policy_snapshot_id,
                    receipt_ref="policy-receipt:unbound",
                )

        report = self.report_with_replacements(
            policies=PolicySnapshotBlindRepository()
        )

        self.assertEqual("failed-development-conformance", report.status)
        self.assertFalse(report.case("policy_repository").passed)

    def test_activation_preflight_without_validation_bindings_fails(self) -> None:
        reference = self.reference

        class ValidationBlindActivationPreflight:
            valid_receipt_ref = "receipt:reference-valid"

            def __init__(self):
                self.bound_routes = set()

            def bind_single_use_after_validation(self, command, result, snapshot):
                del result, snapshot
                if command.route_id in self.bound_routes:
                    raise reference.HostIntegrationConformanceError(
                        "activation-lease-already-bound"
                    )
                self.bound_routes.add(command.route_id)
                return SimpleNamespace(
                    valid=True,
                    activation_lease_ref="activation-lease:unbound",
                )

            def verify_consumption_receipt(self, command):
                if command.context.session_id != reference.VALID_SESSION:
                    raise reference.HostIntegrationConformanceError(
                        "request-session-mismatch"
                    )
                if command.activation_receipt_ref != self.valid_receipt_ref:
                    raise reference.HostIntegrationConformanceError(
                        "activation-receipt-invalid"
                    )

        report = self.report_with_replacements(
            activation_preflight=ValidationBlindActivationPreflight()
        )

        self.assertEqual("failed-development-conformance", report.status)
        self.assertFalse(report.case("activation_preflight").passed)

    def test_gate_coordinator_without_distinct_key_cas_fails(self) -> None:
        reference = self.reference

        class ReplayOnlyGateCoordinator:
            def __init__(self):
                self.persisted = False

            def persist_result(self, command, result):
                del command, result
                if self.persisted:
                    raise reference.HostIntegrationConformanceError(
                        "gate-persist-failed"
                    )
                self.persisted = True
                return SimpleNamespace(
                    state_version=1,
                    receipt_ref="gate-append-receipt:unbound",
                )

        report = self.report_with_replacements(
            gate_coordinator=ReplayOnlyGateCoordinator()
        )

        self.assertEqual("failed-development-conformance", report.status)
        self.assertFalse(report.case("gate_coordinator").passed)

    def test_adapter_without_valid_server_manifest_fails_before_port_construction(self) -> None:
        class UnsafeAdapter:
            build_called = False

            def host_manifest(self):
                return {"authority_label": "model-selected"}

            def build_router_ports(self, **kwargs):
                del kwargs
                self.build_called = True
                return self.adapter.last_ports

        unsafe = UnsafeAdapter()
        with self.assertRaises(HostIntegrationContractError) as caught:
            open_router(
                self.resources.database,
                self.resources.artifact_root,
                unsafe,
                self.resources.request_authorizer,
                self.resources.instruction_content_resolver,
                self.resources.artifact_protector,
                self.resources.activation_preflight,
                self.resources.evaluation_ports,
                self.resources.clock,
                self.resources.id_factory,
            )
        self.assertEqual("host-adapter-manifest-invalid", caught.exception.diagnostic)
        self.assertFalse(unsafe.build_called)

    def test_malformed_composition_ports_return_failed_public_safe_report(self) -> None:
        delegate = self.reference.create_reference_adapter()

        class MalformedAdapter:
            def host_manifest(self):
                return delegate.host_manifest()

            def build_router_ports(self, **kwargs):
                del kwargs
                return SimpleNamespace()

            def build_conformance_probe(self):
                return delegate.build_conformance_probe()

        report = run_host_conformance(MalformedAdapter(), self.resources)

        self.assertEqual("failed-development-conformance", report.status)
        self.assertFalse(report.case("composition-happy-path").passed)
        for port_name in REQUIRED_HOST_PORTS:
            with self.subTest(port_name=port_name):
                case = report.case(port_name)
                self.assertFalse(case.passed)
                self.assertEqual("composition-ports-invalid", case.diagnostic)

    def test_stale_snapshot_rejection_is_public_safe(self) -> None:
        case = self.report().case("snapshot-stale")
        self.assertTrue(case.passed)
        self.assertEqual("snapshot-stale", case.diagnostic)
        self.assertEqual((), case.private_details)

    def test_forged_receipt_rejection_is_public_safe(self) -> None:
        case = self.report().case("receipt-forged")
        self.assertTrue(case.passed)
        self.assertEqual("activation-receipt-invalid", case.diagnostic)
        self.assertEqual((), case.private_details)

    def test_wrong_session_rejection_is_public_safe(self) -> None:
        case = self.report().case("session-mismatch")
        self.assertTrue(case.passed)
        self.assertEqual("request-session-mismatch", case.diagnostic)
        self.assertEqual((), case.private_details)

    def test_cas_conflict_rejection_is_public_safe(self) -> None:
        case = self.report().case("cas-conflict")
        self.assertTrue(case.passed)
        self.assertEqual("state-version-conflict", case.diagnostic)
        self.assertEqual((), case.private_details)

    def test_idempotent_replay_returns_the_original_event_identity(self) -> None:
        case = self.report().case("idempotent-replay")
        self.assertTrue(case.passed)
        self.assertEqual("idempotent-replay-confirmed", case.diagnostic)
        self.assertEqual(("same-event-id", "replayed"), case.evidence)

    def test_native_goal_resume_requires_fresh_host_context(self) -> None:
        case = self.report().case("native-goal-refresh")
        self.assertTrue(case.passed)
        self.assertEqual("goal-resume-refresh-required", case.diagnostic)
        self.assertEqual((), case.private_details)

    def test_put_bytes_only_artifact_store_returns_a_protected_reference(self) -> None:
        case = self.report().case("artifact-protection")
        self.assertTrue(case.passed)
        self.assertEqual("protected-artifact-reference-confirmed", case.diagnostic)
        self.assertEqual((), case.private_details)
        self.assertFalse(hasattr(self.adapter.last_ports.artifacts, "protect"))
        self.assertEqual(("restricted", "protected"), case.evidence)

    def test_reference_conformance_never_claims_host_pilot_or_hybrid_full(self) -> None:
        report = self.report()

        self.assertEqual("reference-not-production-authority", report.authority_label)
        self.assertFalse(report.production_authority_declared)
        self.assertFalse(report.production_authority_verified)
        self.assertFalse(report.host_pilot_verified)
        self.assertFalse(report.hybrid_full)

    def test_shadow_fixture_cannot_hide_unsafe_composed_ports(self) -> None:
        delegate = self.reference.create_reference_adapter()

        class PermissiveSnapshot:
            def require(self, snapshot_id):
                return {"snapshot_id": snapshot_id, "fresh": True}

        class PermissiveActivation:
            def verify_consumption_receipt(self, command):
                del command

        class NonIdempotentCoordinator:
            sequence = 0

            def record(self, command):
                del command
                self.sequence += 1
                return SimpleNamespace(
                    event_id=f"unsafe:{self.sequence}",
                    resulting_state_version=self.sequence,
                    replayed=False,
                )

        class PermissiveScheduler:
            def next(self, query, require_resume_refresh=True):
                del query, require_resume_refresh
                return SimpleNamespace(status="ready")

        class PermissiveArtifactStore:
            def put_bytes(self, content, media_type, classification, purpose):
                del content, media_type, classification, purpose
                return "C:\\unsafe\\artifact.bin"

        class ShadowFixtureAdapter:
            def host_manifest(self):
                return delegate.host_manifest()

            def build_router_ports(self, **kwargs):
                safe_ports = delegate.build_router_ports(**kwargs)
                return replace(
                    safe_ports,
                    snapshots=PermissiveSnapshot(),
                    activation_preflight=PermissiveActivation(),
                    coordinator=NonIdempotentCoordinator(),
                    scheduler=PermissiveScheduler(),
                    artifacts=PermissiveArtifactStore(),
                )

            def build_conformance_fixture(self):
                safe_ports = delegate.last_ports
                return SimpleNamespace(
                    snapshots=safe_ports.snapshots,
                    activation_preflight=safe_ports.activation_preflight,
                    coordinator=safe_ports.coordinator,
                    scheduler=safe_ports.scheduler,
                    artifact_protector=safe_ports.artifacts,
                )

            def build_conformance_probe(self):
                return delegate.build_conformance_probe()

        report = run_host_conformance(ShadowFixtureAdapter(), self.resources)

        self.assertEqual("failed-development-conformance", report.status)
        self.assertFalse(report.case("snapshot-stale").passed)
        self.assertFalse(report.case("receipt-forged").passed)
        self.assertFalse(report.case("cas-conflict").passed)
        self.assertFalse(report.case("native-goal-refresh").passed)
        artifact_case = report.case("artifact-protection")
        self.assertFalse(artifact_case.passed)
        self.assertEqual("artifact-reference-invalid", artifact_case.diagnostic)

    def test_artifact_store_rejection_is_a_public_safe_failed_case(self) -> None:
        delegate = self.reference.create_reference_adapter()

        reference = self.reference

        class RejectingArtifactStore:
            def put_bytes(self, content, media_type, classification, purpose):
                del content, media_type, classification, purpose
                raise reference.HostIntegrationConformanceError(
                    "artifact-protection-failed"
                )

        class RejectingAdapter:
            def host_manifest(self):
                return delegate.host_manifest()

            def build_router_ports(self, **kwargs):
                return replace(
                    delegate.build_router_ports(**kwargs),
                    artifacts=RejectingArtifactStore(),
                )

            def build_conformance_probe(self):
                return delegate.build_conformance_probe()

        report = run_host_conformance(RejectingAdapter(), self.resources)
        case = report.case("artifact-protection")

        self.assertEqual("failed-development-conformance", report.status)
        self.assertFalse(case.passed)
        self.assertEqual("artifact-protection-failed", case.diagnostic)
        self.assertEqual((), case.private_details)

    def test_artifact_protection_rejects_non_meaningful_protection_evidence(self) -> None:
        delegate = self.reference.create_reference_adapter()
        reference = self.reference
        invalid_evidence = (
            ("   ", "key:artifact"),
            (None, "key:artifact"),
            (" None ", "key:artifact"),
            (" NONE ", "key:artifact"),
            (123, "key:artifact"),
            ("reference-envelope", "   "),
            ("reference-envelope", None),
            ("reference-envelope", 123),
        )

        for protection_kind, protection_ref in invalid_evidence:
            with self.subTest(
                protection_kind=protection_kind,
                protection_ref=protection_ref,
            ):
                class AdversarialArtifactStore:
                    def put_bytes(self, content, media_type, classification, purpose):
                        del purpose
                        return reference.ArtifactRef(
                            digest="sha256:" + reference.sha256(content).hexdigest(),
                            media_type=media_type,
                            sensitivity=classification,
                            protection_kind=protection_kind,
                            protection_ref=protection_ref,
                        )

                class AdversarialAdapter:
                    last_store = AdversarialArtifactStore()
                    last_ports = None

                    def host_manifest(self):
                        return delegate.host_manifest()

                    def build_router_ports(self, **kwargs):
                        self.last_ports = replace(
                            delegate.build_router_ports(**kwargs),
                            artifacts=self.last_store,
                        )
                        return self.last_ports

                    def build_conformance_probe(self):
                        return delegate.build_conformance_probe()

                adapter = AdversarialAdapter()
                report = run_host_conformance(adapter, self.resources)
                case = report.case("artifact-protection")

                self.assertIs(adapter.last_store, adapter.last_ports.artifacts)
                self.assertEqual("failed-development-conformance", report.status)
                self.assertFalse(case.passed)
                self.assertEqual("artifact-reference-invalid", case.diagnostic)

    def test_artifact_protection_accepts_normalized_non_none_evidence(self) -> None:
        delegate = self.reference.create_reference_adapter()
        reference = self.reference

        class NormalizedArtifactStore:
            def put_bytes(self, content, media_type, classification, purpose):
                del purpose
                return reference.ArtifactRef(
                    digest="sha256:" + reference.sha256(content).hexdigest(),
                    media_type=media_type,
                    sensitivity=classification,
                    protection_kind=" Protected ",
                    protection_ref=" key:artifact ",
                )

        class NormalizedAdapter:
            last_store = NormalizedArtifactStore()
            last_ports = None

            def host_manifest(self):
                return delegate.host_manifest()

            def build_router_ports(self, **kwargs):
                self.last_ports = replace(
                    delegate.build_router_ports(**kwargs),
                    artifacts=self.last_store,
                )
                return self.last_ports

            def build_conformance_probe(self):
                return delegate.build_conformance_probe()

        adapter = NormalizedAdapter()
        report = run_host_conformance(adapter, self.resources)
        case = report.case("artifact-protection")

        self.assertIs(adapter.last_store, adapter.last_ports.artifacts)
        self.assertEqual("passed-development-conformance", report.status)
        self.assertTrue(case.passed)
        self.assertEqual("protected-artifact-reference-confirmed", case.diagnostic)

    def test_self_declared_production_authority_is_never_reported_as_verified(self) -> None:
        delegate = self.reference.create_reference_adapter()

        class SelfDeclaredProductionAdapter:
            def host_manifest(self):
                return replace(
                    delegate.host_manifest(),
                    authority_label="self-declared-production-authority",
                    production_authority=True,
                )

            def build_router_ports(self, **kwargs):
                return delegate.build_router_ports(**kwargs)

            def build_conformance_probe(self):
                return delegate.build_conformance_probe()

        report = run_host_conformance(SelfDeclaredProductionAdapter(), self.resources)

        self.assertEqual("passed-development-conformance", report.status)
        self.assertTrue(report.production_authority_declared)
        self.assertFalse(report.production_authority_verified)
        self.assertFalse(report.host_pilot_verified)
        self.assertFalse(report.hybrid_full)
        public = report.to_public_dict()
        self.assertNotIn("production_authority", public)
        self.assertTrue(public["production_authority_declared"])
        self.assertFalse(public["production_authority_verified"])


if __name__ == "__main__":
    unittest.main()
