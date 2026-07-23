from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from workflow_skill_router.evaluation.contracts import EvaluationIntegrityError, SealingRoots
from workflow_skill_router.evaluation.sealing import load_scoring_key, seal_authoring_case, verify_scoring_binding


CASE = {
    "execution": {
        "prompt": "請只使用指定 SKILL",
        "profile": "behavior",
        "allowed_tools": [],
        "attempt_nonce": "nonce-2.3",
        "instruction_digest": "sha256:" + "1" * 64,
        "case_payload_digest": "sha256:" + "2" * 64,
        "model_version": "gpt-5.6-sol",
    },
    "driver": {"replies": ["不同意輔助技能"]},
    "scoring": {"expected_envelope": "single", "hard_invariants": ["explicit-skill-preserved"]},
}


class SealingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.roots = SealingRoots(root / "worker", root / "driver", root / "scorer")

    def tearDown(self): self.temp.cleanup()

    def test_execution_directory_has_no_scoring_material(self):
        paths = seal_authoring_case(CASE, self.roots)
        self.assertEqual({"payload.json", "execution-manifest.json"}, {p.name for p in paths.execution_dir.iterdir()})
        self.assertNotIn("expected_envelope", paths.execution_payload.read_text("utf-8"))
        self.assertNotEqual(paths.execution_dir, paths.scoring_dir)
        execution = json.loads(paths.execution_payload.read_text("utf-8"))
        for name in (
            "attempt_nonce",
            "allowed_tools",
            "instruction_digest",
            "case_payload_digest",
            "model_version",
        ):
            self.assertIn(name, execution)

    def test_scoring_key_rejects_result_from_other_payload(self):
        paths = seal_authoring_case(CASE, self.roots)
        manifest = json.loads(paths.execution_manifest.read_text("utf-8"))
        result = {"opaque_run_case_id": paths.opaque_run_case_id, **manifest}
        result["execution_payload_hash"] = "0" * 64
        with self.assertRaisesRegex(EvaluationIntegrityError, "execution_payload_hash_mismatch"):
            verify_scoring_binding(result, load_scoring_key(paths.scoring_key))

    def test_driver_change_changes_identity_and_cross_scoring_fails(self):
        first = seal_authoring_case(CASE, self.roots)
        changed = {**CASE, "driver": {"replies": ["同意"]}}
        second = seal_authoring_case(changed, self.roots)
        self.assertNotEqual(first.opaque_run_case_id, second.opaque_run_case_id)
        first_manifest = json.loads(first.execution_manifest.read_text("utf-8"))
        result = {"opaque_run_case_id": first.opaque_run_case_id, **first_manifest}
        with self.assertRaisesRegex(EvaluationIntegrityError, "opaque_run_case_id_mismatch"):
            verify_scoring_binding(result, load_scoring_key(second.scoring_key))

    def test_existing_path_with_different_bytes_fails_closed(self):
        paths = seal_authoring_case(CASE, self.roots)
        paths.driver_package.write_text('{"tampered":true}\n', encoding="utf-8")
        with self.assertRaisesRegex(EvaluationIntegrityError, "sealed_path_collision"):
            seal_authoring_case(CASE, self.roots)


if __name__ == "__main__": unittest.main()
