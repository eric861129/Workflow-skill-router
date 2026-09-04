import json
from pathlib import Path
import unittest


SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "src/workflow_skill_router/schemas/json/v2"
EXPECTED_SCHEMA_FILES = {
    "artifact-envelope.schema.json",
    "capability-drift.schema.json",
    "capability-snapshot.schema.json",
    "capability.schema.json",
    "memory-policy.schema.json",
    "memory-policy-snapshot.schema.json",
    "routing-profile.schema.json",
    "route-observation.schema.json",
    "route-feedback.schema.json",
}


class SchemaDocumentTests(unittest.TestCase):
    def test_all_documents_are_utf8_draft_2020_12_with_unique_ids(self) -> None:
        paths = sorted(SCHEMA_ROOT.glob("*.json"))
        self.assertEqual(EXPECTED_SCHEMA_FILES, {path.name for path in paths})
        documents = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in paths
        ]
        self.assertEqual(len(documents), len({item["$id"] for item in documents}))
        self.assertTrue(all(
            item["$schema"] == "https://json-schema.org/draft/2020-12/schema"
            for item in documents
        ))

    def test_snapshot_schema_requires_immutable_identity_fields(self) -> None:
        document = json.loads(
            (SCHEMA_ROOT / "capability-snapshot.schema.json").read_text(encoding="utf-8")
        )
        self.assertTrue({
            "snapshot_id", "schema_version", "created_at", "runtime_fingerprint",
            "provider_revisions", "capabilities", "freshness",
        }.issubset(document["required"]))

    def test_capability_schema_matches_content_and_risk_availability_model(self) -> None:
        document = json.loads(
            (SCHEMA_ROOT / "capability.schema.json").read_text(encoding="utf-8")
        )
        self.assertTrue(
            {"installer_content_digest", "availability_by_risk"}.issubset(
                document["required"]
            )
        )
        availability = document["properties"]["availability_by_risk"]
        self.assertEqual(4, availability["minItems"])
        self.assertEqual(4, availability["maxItems"])
        self.assertEqual(["R0", "R1", "R2", "R3"], availability["x-risk-order"])

    def test_drift_schema_freezes_snapshot_and_change_identity(self) -> None:
        document = json.loads(
            (SCHEMA_ROOT / "capability-drift.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(False, document["additionalProperties"])
        self.assertTrue({
            "drift_id", "previous_snapshot_id", "current_snapshot_id", "capability_id",
            "kind", "changed_fields", "before_fingerprint", "after_fingerprint", "detected_at",
        }.issubset(document["required"]))

    def test_routing_profile_schema_has_no_free_form_instruction_surface(self) -> None:
        document = json.loads(
            (SCHEMA_ROOT / "routing-profile.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(False, document["additionalProperties"])
        self.assertNotIn("instructions", document["properties"])
        phase = document["$defs"]["skillTreePhase"]
        self.assertEqual(3, phase["properties"]["support_skill_ids"]["maxItems"])
        self.assertEqual(False, phase["additionalProperties"])

    def test_memory_policy_schema_is_strict_and_default_off_capable(self) -> None:
        document = json.loads(
            (SCHEMA_ROOT / "memory-policy.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(False, document["additionalProperties"])
        self.assertEqual(
            "workflow-skill-router/memory-policy",
            document["properties"]["schema_id"]["const"],
        )
        self.assertEqual(
            ["disabled", "observe", "reviewed", "automatic"],
            document["properties"]["mode"]["enum"],
        )
        self.assertNotIn("instructions", document["properties"])
        self.assertNotIn("raw_prompt", document["properties"])

    def test_memory_policy_snapshot_schema_is_strict_and_redacted(self) -> None:
        document = json.loads(
            (SCHEMA_ROOT / "memory-policy-snapshot.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(False, document["additionalProperties"])
        self.assertEqual(
            "workflow-skill-router/memory-policy-snapshot",
            document["properties"]["schema_id"]["const"],
        )
        self.assertTrue(
            {
                "snapshot_id",
                "policy_digest",
                "mode",
                "personal_mode",
                "workspace_requested_mode",
                "policy_source",
                "features",
                "reason_codes",
            }.issubset(document["required"])
        )
        serialized = json.dumps(document, sort_keys=True)
        for forbidden in (
            "source_path",
            "policy_document",
            "raw_prompt",
            "file_paths",
            "file_content",
            "tool_arguments",
            "secrets",
            "metadata_json",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_route_observation_schema_is_strict_and_redacted(self) -> None:
        document = json.loads(
            (SCHEMA_ROOT / "route-observation.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(False, document["additionalProperties"])
        self.assertEqual(
            "workflow-skill-router/route-observation",
            document["properties"]["schema_id"]["const"],
        )
        serialized = json.dumps(document, sort_keys=True)
        for forbidden in (
            "raw_prompt", "raw_objective", "source_path", "file_content",
            "tool_arguments", "secrets", "reported_outcome", "metadata_json",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_route_feedback_schema_is_strict_and_redacted(self) -> None:
        document = json.loads(
            (SCHEMA_ROOT / "route-feedback.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(False, document["additionalProperties"])
        self.assertEqual(
            "workflow-skill-router/route-feedback",
            document["properties"]["schema_id"]["const"],
        )
        self.assertEqual(
            [
                "accepted", "corrected", "rejected", "support-rejected",
                "capability-unavailable", "gate-failed", "completed",
                "abandoned", "no-memory",
            ],
            document["properties"]["feedback_type"]["enum"],
        )
        serialized = json.dumps(document, sort_keys=True)
        for forbidden in (
            "raw_prompt", "raw_objective", "source_path", "file_content",
            "tool_arguments", "secrets", "metadata_json",
        ):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
