from __future__ import annotations

import importlib.util
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "evaluation/v2/pilots/validate_capability_unavailable_attestation.py"
SCHEMA_PATH = ROOT / "evaluation/v2/pilots/capability-unavailable-attestation.schema.json"
TEMPLATE_PATH = ROOT / "docs/evidence/capability-unavailable-attestation-template.md"


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_capability_unavailable_attestation", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CapabilityUnavailableAttestationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = _load_validator()

    def reviewed_record(self) -> dict[str, object]:
        return {
            "schema_version": "workflow-skill-router/capability-unavailable-attestation/1.0",
            "record_type": "reviewed-capability-unavailable-attestation",
            "attestation_status": "reviewed",
            "evidence_lane": "capability-unavailable",
            "claim_boundary": "unavailable-evidence-only-not-a-verified-host-pilot",
            "checked_capability": {
                "id": "sync_runtime_context",
                "authority_requirement": "verified-host-required",
            },
            "source_revision": "git:0a1b2c3d4e5f6a7b",
            "runtime": {
                "runtime_profile": "bundled-local-r0",
                "conformance_profile": None,
                "fallback_mode": "skill-only-fallback",
                "runtime_package_digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            },
            "authority_boundary": "real-host-apis-absent",
            "safe_diagnostic": "verified-host-capability-unavailable",
            "reviewer": "reviewer:550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2026-07-21T08:30:00Z",
            "claims": {
                "verified_host_pilot": False,
                "production_authority": False,
                "hybrid_full": False,
            },
        }

    def test_valid_reviewed_record_is_accepted(self) -> None:
        result = self.validator.validate_attestation(self.reviewed_record())

        self.assertEqual({"valid": True, "code": "capability-unavailable-attestation-valid"}, result.public_dict())

    def test_rejects_missing_or_noncanonical_reviewer_timestamp(self) -> None:
        for field, value, expected_code in (
            ("reviewer", None, "capability-unavailable-reviewer-invalid"),
            ("reviewer", "reviewer:ghp_abcdefghijklmnopqrstuvwxyz012345", "capability-unavailable-reviewer-invalid"),
            ("reviewer", "reviewer:deploy-production-now", "capability-unavailable-reviewer-invalid"),
            ("timestamp", "2026-07-21T08:30:00+08:00", "capability-unavailable-timestamp-invalid"),
            ("timestamp", "2026-02-30T08:30:00Z", "capability-unavailable-timestamp-invalid"),
        ):
            with self.subTest(field=field, value=value):
                record = self.reviewed_record()
                if value is None:
                    del record[field]
                else:
                    record[field] = value

                self.assertEqual(expected_code, self.validator.validate_attestation(record).code)

    def test_rejects_verified_host_production_or_hybrid_full_claims(self) -> None:
        for field in ("verified_host_pilot", "production_authority", "hybrid_full"):
            with self.subTest(field=field):
                record = self.reviewed_record()
                record["claims"][field] = True

                self.assertEqual(
                    "capability-unavailable-claim-boundary-invalid",
                    self.validator.validate_attestation(record).code,
                )

    def test_rejects_raw_or_unreviewed_evidence_fields(self) -> None:
        for field, value in (
            ("raw_host_receipts", ["receipt"]),
            ("host_secrets", ["secret"]),
            ("repository_paths", ["D:\\repo"]),
            ("workspace_paths", ["C:\\workspace"]),
            ("raw_transcripts", ["transcript"]),
            ("unreviewed_evidence", {"status": "draft-not-attested"}),
        ):
            with self.subTest(field=field):
                record = self.reviewed_record()
                record[field] = value

                self.assertEqual(
                    "capability-unavailable-structure-invalid",
                    self.validator.validate_attestation(record).code,
                )

    def test_rejects_wrong_runtime_or_evidence_lane_boundary(self) -> None:
        record = self.reviewed_record()
        record["source_revision"] = "main"
        self.assertEqual(
            "capability-unavailable-source-binding-invalid",
            self.validator.validate_attestation(record).code,
        )

        record = self.reviewed_record()
        record["runtime"]["fallback_mode"] = "host-enabled"
        self.assertEqual(
            "capability-unavailable-runtime-binding-invalid",
            self.validator.validate_attestation(record).code,
        )

        record = self.reviewed_record()
        record["runtime"]["runtime_package_digest"] = "sha256:not-a-digest"
        self.assertEqual(
            "capability-unavailable-runtime-binding-invalid",
            self.validator.validate_attestation(record).code,
        )

        record = self.reviewed_record()
        record["evidence_lane"] = "verified-host-pilot"
        self.assertEqual(
            "capability-unavailable-evidence-lane-invalid",
            self.validator.validate_attestation(record).code,
        )

        record = self.reviewed_record()
        record["claim_boundary"] = "verified-host-pilot"
        self.assertEqual(
            "capability-unavailable-claim-boundary-invalid",
            self.validator.validate_attestation(record).code,
        )

    def test_schema_and_template_define_reviewed_only_public_evidence(self) -> None:
        record = self.reviewed_record()
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        template = TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertFalse(schema["additionalProperties"])
        self.assertSetEqual(set(record), set(schema["required"]))
        self.assertSetEqual(set(record), set(schema["properties"]))
        self.assertEqual("reviewed", schema["properties"]["attestation_status"]["const"])
        self.assertEqual("capability-unavailable", schema["properties"]["evidence_lane"]["const"])

        for field in ("runtime", "claims"):
            field_schema = schema["properties"][field]
            self.assertFalse(field_schema["additionalProperties"])
            self.assertSetEqual(set(record[field]), set(field_schema["required"]))
            self.assertSetEqual(set(record[field]), set(field_schema["properties"]))

        self.assertTrue(
            all(
                value.get("const") is False
                for value in schema["properties"]["claims"]["properties"].values()
            )
        )
        self.assertIn("draft-not-attested", template)
        self.assertIn("not public evidence", template)
        self.assertIn("reviewed attestation", template)
        self.assertIn("does not establish `hybrid-full`", " ".join(template.split()))

    def test_draft_not_attested_record_is_rejected(self) -> None:
        draft = deepcopy(self.reviewed_record())
        draft["attestation_status"] = "draft-not-attested"
        del draft["reviewer"]
        del draft["timestamp"]

        self.assertFalse(self.validator.validate_attestation(draft).valid)


if __name__ == "__main__":
    unittest.main()
