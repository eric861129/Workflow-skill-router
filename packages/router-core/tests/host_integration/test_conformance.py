from __future__ import annotations

import importlib.util
import sys
import json
from pathlib import Path
import tempfile
import unittest

from workflow_skill_router.composition import RouterCompositionPorts, open as open_router
from workflow_skill_router.host_integration import (
    HostIntegrationContractError,
    REQUIRED_HOST_PORTS,
    run_host_conformance,
    validate_host_manifest,
)
from workflow_skill_router.ports import HostIntegrationAdapterPort


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

        report = self.report()

        self.assertEqual("passed-development-conformance", report.status)
        self.assertEqual(
            "workflow_skill_router.composition.open", report.composition_root,
        )
        self.assertEqual("RouterService", report.service_type)
        self.assertEqual(1, self.adapter.build_count)
        self.assertIsInstance(self.adapter.last_ports, RouterCompositionPorts)
        self.assertTrue(report.case("composition-happy-path").passed)

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

    def test_artifact_protection_failure_never_returns_an_artifact_location(self) -> None:
        case = self.report().case("artifact-protection-failure")
        self.assertTrue(case.passed)
        self.assertEqual("artifact-protection-failed", case.diagnostic)
        self.assertEqual((), case.private_details)
        self.assertNotIn("artifact", " ".join(case.evidence).lower())

    def test_reference_conformance_never_claims_host_pilot_or_hybrid_full(self) -> None:
        report = self.report()

        self.assertEqual("reference-not-production-authority", report.authority_label)
        self.assertFalse(report.production_authority)
        self.assertFalse(report.host_pilot_verified)
        self.assertFalse(report.hybrid_full)


if __name__ == "__main__":
    unittest.main()
