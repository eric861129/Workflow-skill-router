from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PLAN = ROOT / "evaluation/v2/pilots/local-work-loop-plan.json"
HOST_PLAN = ROOT / "evaluation/v2/pilots/host-conformance-plan.json"
PILOT_TEMPLATE = ROOT / "docs/evidence/v2-beta5-pilot-template.md"
EVALUATION_README = ROOT / "evaluation/v2/README.md"
ENGLISH_PAGE = ROOT / "site/src/content/docs/reference/model-evaluation.md"
CHINESE_PAGE = ROOT / "site/src/content/docs/zh-tw/reference/model-evaluation.md"
ADR = ROOT / "docs/adr/0004-explainable-classification-and-runtime-modes.md"


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
            ("tasks-with-manual-envelope-correction", "eligible-real-local-tasks"),
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
            ("successful-router-local-resumes", "eligible-router-local-resume-attempts"),
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
                "reviewer",
                "timestamp",
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
            {"sanitized-aggregate", "case-safe-diagnostic"},
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
            "prepared, unpublished beta.4",
            "unreleased beta.5",
        ):
            self.assertIn(phrase, combined)
        self.assertIn("local-work-loop-plan.json", readme)
        self.assertIn("host-conformance-plan.json", readme)
        self.assertIn("v2-beta5-pilot-template.md", readme)
        self.assertNotIn("Pilot result: passed", combined)

        release = self.read_json(ROOT / "release/version.json")
        self.assertEqual("2.0.0-beta.3", release["published_v2_version"])
        self.assertEqual("2.0.0-beta.4", release["target_prerelease"])

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
