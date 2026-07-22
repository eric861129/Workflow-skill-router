from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PLAN = ROOT / "evaluation/v2/pilots/local-work-loop-plan.json"
HOST_PLAN = ROOT / "evaluation/v2/pilots/host-conformance-plan.json"
BINDING_SCHEMA = ROOT / "evaluation/v2/pilots/restricted-binding-manifest.schema.json"
PILOT_TEMPLATE = ROOT / "docs/evidence/v2-beta5-pilot-template.md"
EVALUATION_README = ROOT / "evaluation/v2/README.md"
ENGLISH_PAGE = ROOT / "site/src/content/docs/reference/model-evaluation.md"
CHINESE_PAGE = ROOT / "site/src/content/docs/zh-tw/reference/model-evaluation.md"
ADR = ROOT / "docs/adr/0004-explainable-classification-and-runtime-modes.md"


def expected_slot_contracts() -> list[tuple[str, bool, bool, bool, bool]]:
    return [
        *((f"single-{index:02d}", False, True, False, False) for index in range(1, 7)),
        *((f"phased-{index:02d}", True, False, index <= 4, True) for index in range(1, 9)),
        *((f"goal-{index:02d}", False, index <= 4, False, index >= 5) for index in range(1, 7)),
    ]


class Beta5PilotProtocolTests(unittest.TestCase):
    def read_json(self, path: Path) -> dict:
        self.assertTrue(path.is_file(), f"missing protocol artifact: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_local_plan_freezes_real_task_mix_and_release_gates(self) -> None:
        plan = self.read_json(LOCAL_PLAN)

        self.assertEqual(
            "protocol-frozen-awaiting-real-pilot", plan["execution_status"]
        )
        tasks = plan["task_slots"]
        self.assertGreaterEqual(len(tasks), 20)
        envelopes = Counter(task["envelope"] for task in tasks)
        self.assertGreaterEqual(envelopes["single"], 6)
        self.assertGreaterEqual(envelopes["phased"], 8)
        self.assertGreaterEqual(envelopes["goal-like"], 6)
        self.assertGreaterEqual(sum(task["profile_backed"] for task in tasks), 8)
        self.assertEqual(len(tasks), len({task["task_id"] for task in tasks}))
        self.assertEqual(
            expected_slot_contracts(),
            [
                (
                    task["task_id"],
                    task["profile_backed"],
                    task["metric_population_flags"]["no_explicit_skill"],
                    task["metric_population_flags"]["explicit_lock"],
                    task["metric_population_flags"]["router_local_resume"],
                )
                for task in tasks
            ],
        )
        self.assertTrue(
            all(task["metric_population_flags"]["manual_envelope"] for task in tasks)
        )
        self.assertIn("task_binding_policy", plan)
        binding = plan["task_binding_policy"]
        self.assertTrue(binding["distinct_real_task_per_slot"])
        self.assertTrue(binding["freeze_all_inputs_before_first_task"])
        self.assertFalse(binding["synthetic_or_dry_run_is_countable"])
        for task in tasks:
            self.assertEqual("real-local-task-required", task["task_source"])
            self.assertEqual("restricted-run-manifest", task["input_ref"])
            self.assertNotIn("result", task)
            self.assertNotIn("outcome", task)

        metrics = {item["metric_id"]: item for item in plan["release_gates"]}
        self.assertEqual(
            (
                "tasks-with-manual-envelope-correction",
                "all-20-frozen-manual-envelope-slots",
            ),
            (
                metrics["manual-envelope-correction-rate"].get("numerator"),
                metrics["manual-envelope-correction-rate"].get("denominator"),
            ),
        )
        self.assertEqual(("<=", 0.10), (
            metrics["manual-envelope-correction-rate"]["operator"],
            metrics["manual-envelope-correction-rate"]["threshold"],
        ))
        self.assertEqual(("<=", 0.05), (
            metrics["unnecessary-consent-rate"]["operator"],
            metrics["unnecessary-consent-rate"]["threshold"],
        ))
        self.assertEqual(
            "no-explicit-skill-work",
            metrics["unnecessary-consent-rate"]["population"],
        )
        self.assertEqual(
            (
                "no-explicit-skill-tasks-with-unnecessary-consent",
                "eligible-no-explicit-skill-tasks",
            ),
            (
                metrics["unnecessary-consent-rate"].get("numerator"),
                metrics["unnecessary-consent-rate"].get("denominator"),
            ),
        )
        self.assertEqual(("==", 0), (
            metrics["unconsented-support-skill-under-explicit-lock"]["operator"],
            metrics["unconsented-support-skill-under-explicit-lock"]["threshold"],
        ))
        self.assertEqual(
            "explicit-lock-tasks-with-unconsented-support-skill",
            metrics["unconsented-support-skill-under-explicit-lock"].get("counted_event"),
        )
        self.assertEqual((">=", 0.95), (
            metrics["router-local-resume-success-rate"]["operator"],
            metrics["router-local-resume-success-rate"]["threshold"],
        ))
        self.assertEqual(
            ("successful-router-local-resumes", "attempted-resume-eligible-slots"),
            (
                metrics["router-local-resume-success-rate"].get("numerator"),
                metrics["router-local-resume-success-rate"].get("denominator"),
            ),
        )

    def test_local_plan_freezes_manifest_scoring_and_public_sanitization(self) -> None:
        plan = self.read_json(LOCAL_PLAN)
        manifest = plan["frozen_run_manifest"]

        self.assertTrue(manifest["required_before_first_task"])
        self.assertEqual(
            {
                "source_revision",
                "runtime_package_digest",
                "protocol_digest",
                "restricted_binding_manifest_digest",
                "binding_manifest_commitment",
                "task_set_commitment",
                "reviewer_attestation_commitment",
                "reviewer",
                "frozen_at",
            },
            set(manifest["required_fields"]),
        )
        self.assertTrue(manifest["immutable_after_freeze"])
        self.assertTrue(plan["scoring_policy"]["later_records_cannot_change_gates"])
        self.assertTrue(
            plan["scoring_policy"]["protocol_change_requires_new_digest_and_run"]
        )

        public = plan["public_artifact_policy"]
        self.assertEqual(
            {
                "sanitized-aggregate",
                "case-safe-diagnostic",
                "non-reversible-binding-commitment",
                "reviewer-attestation-commitment",
            },
            set(public["allowed_evidence_classes"]),
        )
        self.assertEqual(
            {
                "objectives",
                "raw_prompts",
                "repository_paths",
                "workspace_paths",
                "instruction_bodies",
                "secrets",
                "raw_transcripts",
                "expected_skill_values",
                "actual_skill_values",
                "unreviewed_evidence",
            },
            set(public["prohibited_public_fields"]),
        )
        for forbidden in ("results", "pass", "fail", "executed_task_count"):
            self.assertNotIn(forbidden, plan)

    def test_restricted_binding_schema_precommits_twenty_private_task_records(self) -> None:
        schema = self.read_json(BINDING_SCHEMA)
        plan = self.read_json(LOCAL_PLAN)

        self.assertEqual(
            "workflow-skill-router/restricted-pilot-binding-manifest/1.0",
            schema["$id"],
        )
        self.assertFalse(schema["additionalProperties"])
        bindings = schema["properties"]["bindings"]
        self.assertEqual(20, bindings["minItems"])
        self.assertEqual(20, bindings["maxItems"])
        self.assertTrue(bindings.get("uniqueItems"))
        self.assertIs(False, bindings["items"])
        self.assertEqual(20, len(bindings["prefixItems"]))
        record = schema["$defs"]["bindingRecord"]
        self.assertFalse(record["additionalProperties"])
        self.assertEqual(
            {
                "slot_id",
                "task_identity",
                "task_identity_commitment",
                "source_identity",
                "source_identity_commitment",
                "profile_binding",
                "metric_population_flags",
                "record_integrity_commitment",
            },
            set(record["required"]),
        )
        self.assertTrue(
            {
                "objective",
                "raw_prompt",
                "repository_path",
                "workspace_path",
                "instruction_body",
            }.isdisjoint(record["properties"])
        )
        hmac_pattern = r"^hmac-sha256:[0-9a-f]{64}$"
        for field in (
            "task_identity_commitment",
            "source_identity_commitment",
            "record_integrity_commitment",
        ):
            self.assertEqual(hmac_pattern, record["properties"][field]["pattern"])
        for definition in (
            "flagsNoExplicit",
            "flagsExplicitResume",
            "flagsResumeOnly",
        ):
            flags = schema["$defs"][definition]["properties"]
            self.assertIs(True, flags["manual_envelope"]["const"])
            for flag in ("no_explicit_skill", "explicit_lock", "router_local_resume"):
                self.assertIsInstance(flags[flag]["const"], bool)
        self.assertTrue(
            {
                "frozen_at",
                "binding_manifest_commitment",
                "task_set_commitment",
                "reviewer_attestation",
            }.issubset(schema["required"])
        )
        reviewer = schema["properties"]["reviewer_attestation"]
        self.assertTrue(
            {
                "reviewed_before_task_1",
                "real_task_status_human_reviewed",
                "reviewer_attestation_commitment",
            }.issubset(reviewer["required"])
        )
        canonical_utc = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
        self.assertEqual(canonical_utc, schema["properties"]["frozen_at"]["pattern"])
        self.assertEqual(
            canonical_utc,
            reviewer["properties"]["attested_at"]["pattern"],
        )
        self.assertIn(
            "task-specific source snapshot",
            record["properties"]["source_identity"]["description"],
        )
        scheme = schema["properties"]["commitment_scheme"]
        self.assertEqual(
            "wsr-beta5-pilot-hmac-v1",
            scheme["properties"]["specification"]["const"],
        )
        self.assertEqual(32, scheme["properties"]["secret_length_bytes"]["const"])

        expected_slots = [task["task_id"] for task in plan["task_slots"]]
        schema_slots = [
            item["allOf"][1]["properties"]["slot_id"]["const"]
            for item in bindings["prefixItems"]
        ]
        self.assertEqual(expected_slots, schema_slots)
        for item, (_, profile_backed, no_explicit, explicit_lock, _) in zip(
            bindings["prefixItems"], expected_slot_contracts(), strict=True
        ):
            slot_contract = item["allOf"][1]["properties"]
            self.assertEqual(
                "#/$defs/profileOn" if profile_backed else "#/$defs/profileOff",
                slot_contract["profile_binding"]["$ref"],
            )
            expected_flag_ref = (
                "#/$defs/flagsNoExplicit"
                if no_explicit
                else "#/$defs/flagsExplicitResume"
                if explicit_lock
                else "#/$defs/flagsResumeOnly"
            )
            self.assertEqual(
                expected_flag_ref,
                slot_contract["metric_population_flags"]["$ref"],
            )

        binding = plan["restricted_binding_manifest"]
        self.assertEqual(
            "pilots/restricted-binding-manifest.schema.json", binding["schema"]
        )
        self.assertTrue(binding["created_before_task_1"])
        self.assertTrue(binding["independently_reviewed_before_task_1"])
        self.assertEqual("wsr-beta5-pilot-hmac-v1", binding["commitment_scheme"])
        self.assertFalse(binding["public_commitments_are_reversible"])
        self.assertTrue(binding["human_review_of_real_task_status_required"])
        self.assertEqual(
            [
                "binding_manifest_commitment",
                "task_set_commitment",
                "reviewer_attestation_commitment",
            ],
            binding["public_safe_attestation_fields"],
        )
        self.assertIn("commitment_input_contract", binding)
        contract = binding["commitment_input_contract"]
        self.assertEqual("wsr-beta5-pilot-hmac-v1", contract["specification"])
        self.assertEqual(32, contract["run_secret_bytes"])
        self.assertEqual(
            "ASCII(decimal byte_length) + 0x3A + UTF-8 field bytes",
            contract["field_encoding"],
        )
        self.assertEqual(
            [task["task_id"] for task in plan["task_slots"]],
            contract["task_set_order"],
        )
        self.assertEqual(
            ["run_id", "slot_id", "task_identity"],
            contract["domain_fields"]["task-identity"],
        )
        self.assertEqual(
            [
                "run_id",
                "source_revision",
                "runtime_package_digest",
                "protocol_digest",
                "task_set_commitment",
                "reviewer_id",
                "attested_at",
                "reviewed_before_task_1",
                "real_task_status_human_reviewed",
                "commitments_verified_with_run_secret",
            ],
            contract["domain_fields"]["reviewer-attestation"],
        )
        self.assertEqual(
            [
                "run_id",
                "frozen_at",
                "source_revision",
                "runtime_package_digest",
                "protocol_digest",
                "task_set_commitment",
                "reviewer_attestation_commitment",
                "20 binding_record_commitments in frozen order",
            ],
            contract["domain_fields"]["binding-manifest"],
        )
        self.assertEqual(
            {
                "field": "task_1_started_at",
                "canonical_utc": "YYYY-MM-DDTHH:MM:SSZ",
                "operator": ">",
                "compared_to": "frozen_at",
                "enforced_by": "future-real-pilot-runner",
                "execution_status": "not-executed",
            },
            plan["task_1_start_requirement"],
        )

    def test_binding_integrity_and_metric_populations_fail_closed_non_vacuously(self) -> None:
        plan = self.read_json(LOCAL_PLAN)
        self.assertIn("binding_integrity", plan)
        self.assertIn("metric_population_freeze", plan)
        integrity = plan["binding_integrity"]
        populations = plan["metric_population_freeze"]

        self.assertEqual(20, integrity["exact_binding_record_count"])
        self.assertEqual(
            [task["task_id"] for task in plan["task_slots"]],
            integrity["exact_slot_ids"],
        )
        self.assertTrue(integrity["all_task_commitments_distinct"])
        self.assertTrue(integrity["all_restricted_task_identities_distinct"])
        self.assertTrue(integrity["all_source_commitments_present"])
        self.assertTrue(integrity["all_restricted_source_identities_distinct"])
        self.assertEqual(
            "opaque-task-specific-source-snapshot-or-brief-never-shared-repository-identity",
            integrity["source_identity_semantics"],
        )
        self.assertTrue(integrity["task_source_commitment_pairs_distinct"])
        self.assertTrue(integrity.get("profile_binding_matches_frozen_slot"))
        self.assertTrue(integrity["manifest_digest_matches_frozen_run_metadata"])
        self.assertTrue(integrity["post_start_modification_invalidates_run"])
        self.assertEqual(
            "invalid-entire-run",
            integrity["failure_disposition"],
        )

        self.assertTrue(populations["frozen_before_task_1"])
        self.assertTrue(populations["overlap_allowed"])
        self.assertEqual(
            {
                "manual_envelope": 20,
                "no_explicit_skill": 10,
                "explicit_lock": 4,
                "router_local_resume": 10,
            },
            populations["minimum_eligible_slots"],
        )
        self.assertTrue(populations["every_eligible_slot_requires_final_record"])
        self.assertTrue(populations["every_resume_eligible_slot_must_be_attempted"])
        self.assertEqual(
            "invalid",
            populations["missing_ambiguous_duplicate_or_digest_mismatch"],
        )
        self.assertEqual("invalid", populations["post_start_flag_change"])
        self.assertEqual(
            "gate-unmet-and-run-invalid",
            populations["zero_or_under_minimum_denominator"],
        )
        self.assertFalse(populations["zero_over_zero_can_pass"])
        self.assertIn("final_record_contract", plan)
        final_records = plan["final_record_contract"]
        self.assertEqual(
            [
                "slot_id",
                "binding_record_integrity_commitment",
                "manual_envelope_corrected",
                "final_record_integrity_commitment",
            ],
            final_records["required_for_every_slot"],
        )
        self.assertEqual(
            {
                "no_explicit_skill": ["unnecessary_consent_prompt"],
                "explicit_lock": ["unauthorized_support_event_count"],
                "router_local_resume": ["resume_attempted", "resume_succeeded"],
            },
            final_records["required_when_population_flag_true"],
        )
        self.assertEqual(
            "const-true", final_records["field_constraints"]["resume_attempted"]
        )
        self.assertEqual(
            "non-negative-integer",
            final_records["field_constraints"]["unauthorized_support_event_count"],
        )

    def test_public_docs_require_non_reversible_commitments_and_pre_start_review(self) -> None:
        texts = (
            PILOT_TEMPLATE.read_text(encoding="utf-8"),
            EVALUATION_README.read_text(encoding="utf-8"),
            ENGLISH_PAGE.read_text(encoding="utf-8"),
            CHINESE_PAGE.read_text(encoding="utf-8"),
        )
        combined = "\n".join(texts)

        for phrase in (
            "restricted binding manifest",
            "per-run secret HMAC-SHA-256",
            "wsr-beta5-pilot-hmac-v1",
            "verify_restricted_manifest.py",
            "goal-01",
            "canonical RFC3339 UTC",
            "attested_at <= frozen_at",
            "task-specific source snapshot",
            "task_1_started_at > frozen_at",
            "binding-manifest commitment",
            "task-set commitment",
            "reviewer attestation before task 1",
            "does not replace human review",
            "0/0",
            "invalid, never ineligible",
        ):
            self.assertIn(phrase, combined)
        for text in texts:
            self.assertNotIn("objective commitment input", text)

    def test_host_plan_keeps_reference_verified_and_unavailable_lanes_distinct(self) -> None:
        plan = self.read_json(HOST_PLAN)

        self.assertEqual(
            "protocol-frozen-awaiting-real-pilot", plan["execution_status"]
        )
        lanes = plan["evidence_lanes"]
        reference = lanes["offline-reference-conformance"]
        verified = lanes["verified-host-pilot"]
        unavailable = lanes["capability-unavailable"]
        self.assertEqual("development-evidence-only", reference["claim_limit"])
        self.assertFalse(reference["counts_as_verified_host_pilot"])
        self.assertTrue(verified["requires_actual_host_authority"])
        self.assertTrue(verified["requires_host_receipts"])
        self.assertTrue(verified["requires_human_review"])
        self.assertEqual("real-host-apis-absent", unavailable["condition"])
        self.assertTrue(unavailable["requires_reviewed_attestation"])
        self.assertFalse(plan["claims"]["hybrid_full_permitted"])
        self.assertNotIn("results", plan)

    def test_protocol_docs_preserve_beta_truth_and_define_semantic_gate(self) -> None:
        self.assertTrue(PILOT_TEMPLATE.is_file(), "missing Pilot evidence template")
        readme = EVALUATION_README.read_text(encoding="utf-8")
        template = PILOT_TEMPLATE.read_text(encoding="utf-8")
        english = ENGLISH_PAGE.read_text(encoding="utf-8")
        adr = ADR.read_text(encoding="utf-8")
        combined = "\n".join((readme, template, english, adr))

        for phrase in (
            "protocol-frozen-awaiting-real-pilot",
            "No real Pilot task has been executed or counted",
            "deterministic-default-no-semantic-recommender",
            ">=10%",
            "profile preview --explain",
            "server-configured advisory-only adapter",
            "No Pilot data means the gate is unmet",
            "published beta.3",
            "prepared, unpublished beta.5",
            "prepared beta.5 candidate",
        ):
            self.assertIn(phrase, combined)
        self.assertIn("local-work-loop-plan.json", readme)
        self.assertIn("host-conformance-plan.json", readme)
        self.assertIn("v2-beta5-pilot-template.md", readme)
        self.assertNotIn("Pilot result: passed", combined)

        release = self.read_json(ROOT / "release/version.json")
        self.assertEqual("2.0.0-beta.3", release["published_v2_version"])
        self.assertEqual("2.0.0-beta.5", release["target_prerelease"])

    def test_traditional_chinese_evaluation_page_is_clear_utf8_without_mojibake(self) -> None:
        page = CHINESE_PAGE.read_text(encoding="utf-8")

        self.assertEqual("---", page.splitlines()[0])
        for phrase in (
            "title: 真實模型評測邊界",
            "# 評測證據",
            "尚未執行或計入任何真實 Pilot 任務",
            "離線參考適配器",
            "真實 Host Pilot",
            "能力不可用",
            "語意推薦器",
            "明確指定 Skill",
        ):
            self.assertIn(phrase, page)
        self.assertIsNone(re.search(r"[\ue000-\uf8ff]", page))
        self.assertNotIn(chr(0xFFFD), page)
        self.assertNotIn(chr(0x929D), page)
        self.assertNotIn(chr(0x5697), page)


if __name__ == "__main__":
    unittest.main()
