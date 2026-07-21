from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import hmac
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
VERIFIER_PATH = ROOT / "evaluation/v2/pilots/verify_restricted_manifest.py"
SECRET = bytes(range(32))
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
SLOT_SPECS = (
    *((f"single-{index:02d}", False, True, False, False) for index in range(1, 7)),
    *((f"phased-{index:02d}", True, False, index <= 4, True) for index in range(1, 9)),
    *((f"goal-{index:02d}", False, index <= 4, False, index >= 5) for index in range(1, 7)),
)


def load_verifier():
    spec = importlib.util.spec_from_file_location("beta5_pilot_verifier", VERIFIER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("verifier-module-unloadable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Beta5PilotManifestVerifierTests(unittest.TestCase):
    def verifier(self):
        self.assertTrue(VERIFIER_PATH.is_file(), "missing executable Pilot verifier")
        return load_verifier()

    def record_for(self, index: int, spec: tuple[str, bool, bool, bool, bool]) -> dict:
        slot_id, profile_backed, no_explicit, explicit_lock, resume = spec
        profile = {"profile_backed": False}
        if profile_backed:
            profile = {
                "profile_backed": True,
                "profile_id": f"profile:{index:016d}",
                "profile_revision_digest": DIGEST_B,
                "profile_identity_commitment": "",
            }
        return {
            "slot_id": slot_id,
            "task_identity": f"task:{index:016d}",
            "task_identity_commitment": "",
            "source_identity": f"source:{index:016d}",
            "source_identity_commitment": "",
            "profile_binding": profile,
            "metric_population_flags": {
                "manual_envelope": True,
                "no_explicit_skill": no_explicit,
                "explicit_lock": explicit_lock,
                "router_local_resume": resume,
            },
            "record_integrity_commitment": "",
        }

    def resign_record(self, verifier, manifest: dict, record: dict) -> None:
        run_id = manifest["run_id"]
        slot_id = record["slot_id"]
        record["task_identity_commitment"] = verifier.compute_commitment(
            SECRET,
            "task-identity",
            (run_id, slot_id, record["task_identity"]),
        )
        record["source_identity_commitment"] = verifier.compute_commitment(
            SECRET,
            "source-identity",
            (run_id, slot_id, record["source_identity"]),
        )
        profile = record["profile_binding"]
        profile_commitment = ""
        profile_revision = ""
        if profile["profile_backed"]:
            profile_revision = profile["profile_revision_digest"]
            profile_commitment = verifier.compute_commitment(
                SECRET,
                "profile-identity",
                (run_id, slot_id, profile["profile_id"], profile_revision),
            )
            profile["profile_identity_commitment"] = profile_commitment
        flags = record["metric_population_flags"]
        record["record_integrity_commitment"] = verifier.compute_commitment(
            SECRET,
            "binding-record",
            (
                run_id,
                slot_id,
                record["task_identity_commitment"],
                record["source_identity_commitment"],
                profile_commitment,
                profile_revision,
                verifier.boolean_field(flags["manual_envelope"]),
                verifier.boolean_field(flags["no_explicit_skill"]),
                verifier.boolean_field(flags["explicit_lock"]),
                verifier.boolean_field(flags["router_local_resume"]),
            ),
        )

    def resign_aggregate(self, verifier, manifest: dict) -> None:
        records = manifest["bindings"]
        manifest["task_set_commitment"] = verifier.compute_commitment(
            SECRET,
            "task-set",
            (manifest["run_id"], *(item["record_integrity_commitment"] for item in records)),
        )
        attestation = manifest["reviewer_attestation"]
        attestation["reviewer_attestation_commitment"] = verifier.compute_commitment(
            SECRET,
            "reviewer-attestation",
            (
                manifest["run_id"],
                manifest["source_revision"],
                manifest["runtime_package_digest"],
                manifest["protocol_digest"],
                manifest["task_set_commitment"],
                attestation["reviewer_id"],
                attestation["attested_at"],
                verifier.boolean_field(attestation["reviewed_before_task_1"]),
                verifier.boolean_field(attestation["real_task_status_human_reviewed"]),
                verifier.boolean_field(attestation["commitments_verified_with_run_secret"]),
            ),
        )
        manifest["binding_manifest_commitment"] = verifier.compute_commitment(
            SECRET,
            "binding-manifest",
            (
                manifest["run_id"],
                manifest["frozen_at"],
                manifest["source_revision"],
                manifest["runtime_package_digest"],
                manifest["protocol_digest"],
                manifest["task_set_commitment"],
                attestation["reviewer_attestation_commitment"],
                *(item["record_integrity_commitment"] for item in records),
            ),
        )

    def valid_manifest(self, verifier) -> dict:
        manifest = {
            "schema_version": "workflow-skill-router/restricted-pilot-binding-manifest/1.0",
            "execution_status": "restricted-binding-frozen-before-task-1",
            "run_id": "run:beta5-pilot-0001",
            "frozen_at": "2026-07-21T08:30:00Z",
            "protocol_digest": DIGEST_A,
            "source_revision": "abcdef0123456789",
            "runtime_package_digest": DIGEST_B,
            "commitment_scheme": {
                "specification": "wsr-beta5-pilot-hmac-v1",
                "secret_length_bytes": 32,
                "secret_storage": "restricted-reviewer-access-only",
                "publicly_reversible": False,
            },
            "bindings": [
                self.record_for(index, spec)
                for index, spec in enumerate(SLOT_SPECS, start=1)
            ],
            "task_set_commitment": "",
            "binding_manifest_commitment": "",
            "reviewer_attestation": {
                "reviewer_id": "reviewer:000000000001",
                "attested_at": "2026-07-21T08:00:00Z",
                "reviewed_before_task_1": True,
                "real_task_status_human_reviewed": True,
                "commitments_verified_with_run_secret": True,
                "reviewer_attestation_commitment": "",
            },
        }
        for record in manifest["bindings"]:
            self.resign_record(verifier, manifest, record)
        self.resign_aggregate(verifier, manifest)
        return manifest

    def test_valid_frozen_manifest_passes_with_public_safe_result(self) -> None:
        verifier = self.verifier()
        manifest = self.valid_manifest(verifier)

        result = verifier.verify_manifest(manifest, SECRET)

        self.assertTrue(result.valid)
        self.assertEqual("pilot-binding-valid", result.code)
        self.assertEqual({"valid": True, "code": "pilot-binding-valid"}, result.public_dict())

    def test_exact_hmac_bytes_use_domain_and_utf8_byte_lengths(self) -> None:
        verifier = self.verifier()
        fields = ("run:1", "slot:1", "é")
        message = (
            b"workflow-skill-router/beta5-pilot/v1\x00task-identity\x00"
            b"5:run:1"
            b"6:slot:1"
            b"2:\xc3\xa9"
        )
        expected = "hmac-sha256:" + hmac.new(SECRET, message, sha256).hexdigest()

        self.assertEqual(expected, verifier.compute_commitment(SECRET, "task-identity", fields))
        self.assertNotEqual(
            verifier.compute_commitment(SECRET, "task-identity", ("run:1", "slot:1", " value")),
            verifier.compute_commitment(SECRET, "task-identity", ("run:1", "slot:1", "value")),
        )
        self.assertNotEqual(
            verifier.compute_commitment(SECRET, "task-identity", fields),
            verifier.compute_commitment(SECRET, "source-identity", fields),
        )

    def test_duplicate_or_reordered_slots_fail_even_when_resigned(self) -> None:
        verifier = self.verifier()
        duplicate = self.valid_manifest(verifier)
        duplicate["bindings"][1]["slot_id"] = duplicate["bindings"][0]["slot_id"]
        self.resign_record(verifier, duplicate, duplicate["bindings"][1])
        self.resign_aggregate(verifier, duplicate)
        reordered = self.valid_manifest(verifier)
        reordered["bindings"][0], reordered["bindings"][1] = (
            reordered["bindings"][1], reordered["bindings"][0]
        )
        self.resign_aggregate(verifier, reordered)

        self.assertEqual("pilot-binding-slot-order-invalid", verifier.verify_manifest(duplicate, SECRET).code)
        self.assertEqual("pilot-binding-slot-order-invalid", verifier.verify_manifest(reordered, SECRET).code)

    def test_duplicate_restricted_task_identity_fails_even_when_resigned(self) -> None:
        verifier = self.verifier()
        duplicate_task = self.valid_manifest(verifier)
        duplicate_task["bindings"][1]["task_identity"] = (
            duplicate_task["bindings"][0]["task_identity"]
        )
        self.resign_record(verifier, duplicate_task, duplicate_task["bindings"][1])
        self.resign_aggregate(verifier, duplicate_task)

        self.assertEqual(
            "pilot-binding-task-duplicate",
            verifier.verify_manifest(duplicate_task, SECRET).code,
        )

    def test_duplicate_task_specific_source_identity_fails_even_when_resigned(self) -> None:
        verifier = self.verifier()
        duplicate_source = self.valid_manifest(verifier)
        duplicate_source["bindings"][1]["source_identity"] = (
            duplicate_source["bindings"][0]["source_identity"]
        )
        self.resign_record(verifier, duplicate_source, duplicate_source["bindings"][1])
        self.resign_aggregate(verifier, duplicate_source)

        self.assertEqual(
            "pilot-binding-source-duplicate",
            verifier.verify_manifest(duplicate_source, SECRET).code,
        )

    def test_attestation_time_is_bound_and_must_be_canonical_utc(self) -> None:
        verifier = self.verifier()
        mutated = self.valid_manifest(verifier)
        mutated["reviewer_attestation"]["attested_at"] = "2026-07-21T07:59:59Z"
        self.assertEqual(
            "pilot-binding-review-invalid",
            verifier.verify_manifest(mutated, SECRET).code,
        )

        invalid_values = (
            "2026-07-21T08:00:00+00:00",
            "2026-07-21T08:00:00.000Z",
            " 2026-07-21T08:00:00Z",
            "2026-02-30T08:00:00Z",
            "２０２６-07-21T08:00:00Z",
        )
        for value in invalid_values:
            with self.subTest(value=value):
                invalid = self.valid_manifest(verifier)
                invalid["reviewer_attestation"]["attested_at"] = value
                self.resign_aggregate(verifier, invalid)
                self.assertEqual(
                    "pilot-binding-attested-at-invalid",
                    verifier.verify_manifest(invalid, SECRET).code,
                )

    def test_attestation_must_not_be_after_bound_canonical_freeze_time(self) -> None:
        verifier = self.verifier()
        after_freeze = self.valid_manifest(verifier)
        after_freeze["reviewer_attestation"]["attested_at"] = (
            "2026-07-21T08:30:01Z"
        )
        self.resign_aggregate(verifier, after_freeze)
        self.assertEqual(
            "pilot-binding-attestation-order-invalid",
            verifier.verify_manifest(after_freeze, SECRET).code,
        )

        invalid_freeze = self.valid_manifest(verifier)
        invalid_freeze["frozen_at"] = "2026-07-21T08:30:00+00:00"
        self.resign_aggregate(verifier, invalid_freeze)
        self.assertEqual(
            "pilot-binding-frozen-at-invalid",
            verifier.verify_manifest(invalid_freeze, SECRET).code,
        )

    def test_freeze_time_is_bound_into_manifest_commitment(self) -> None:
        verifier = self.verifier()
        manifest = self.valid_manifest(verifier)
        manifest["frozen_at"] = "2026-07-21T08:31:00Z"

        self.assertEqual(
            "pilot-binding-manifest-commitment-invalid",
            verifier.verify_manifest(manifest, SECRET).code,
        )

    def test_profile_and_population_adversaries_fail_even_when_resigned(self) -> None:
        verifier = self.verifier()
        wrong_profile = self.valid_manifest(verifier)
        wrong_profile["bindings"][6]["profile_binding"] = {"profile_backed": False}
        self.resign_record(verifier, wrong_profile, wrong_profile["bindings"][6])
        self.resign_aggregate(verifier, wrong_profile)
        altered_flags = self.valid_manifest(verifier)
        altered_flags["bindings"][0]["metric_population_flags"]["no_explicit_skill"] = False
        self.resign_record(verifier, altered_flags, altered_flags["bindings"][0])
        self.resign_aggregate(verifier, altered_flags)
        incompatible = self.valid_manifest(verifier)
        incompatible["bindings"][0]["metric_population_flags"]["explicit_lock"] = True
        self.resign_record(verifier, incompatible, incompatible["bindings"][0])
        self.resign_aggregate(verifier, incompatible)
        zero_population = self.valid_manifest(verifier)
        for item in zero_population["bindings"]:
            flags = item["metric_population_flags"]
            flags["no_explicit_skill"] = False
            flags["explicit_lock"] = False
            flags["router_local_resume"] = False
            self.resign_record(verifier, zero_population, item)
        self.resign_aggregate(verifier, zero_population)
        non_boolean = self.valid_manifest(verifier)
        non_boolean["bindings"][0]["metric_population_flags"]["manual_envelope"] = 1

        self.assertEqual("pilot-binding-profile-invalid", verifier.verify_manifest(wrong_profile, SECRET).code)
        self.assertEqual("pilot-binding-population-invalid", verifier.verify_manifest(altered_flags, SECRET).code)
        self.assertEqual("pilot-binding-population-invalid", verifier.verify_manifest(incompatible, SECRET).code)
        self.assertEqual("pilot-binding-population-invalid", verifier.verify_manifest(zero_population, SECRET).code)
        self.assertEqual("pilot-binding-population-invalid", verifier.verify_manifest(non_boolean, SECRET).code)

    def test_cross_domain_substitution_and_detached_review_fail(self) -> None:
        verifier = self.verifier()
        cross_domain = self.valid_manifest(verifier)
        record = cross_domain["bindings"][0]
        record["task_identity_commitment"] = verifier.compute_commitment(
            SECRET,
            "source-identity",
            (cross_domain["run_id"], record["slot_id"], record["task_identity"]),
        )
        flags = record["metric_population_flags"]
        record["record_integrity_commitment"] = verifier.compute_commitment(
            SECRET,
            "binding-record",
            (
                cross_domain["run_id"], record["slot_id"],
                record["task_identity_commitment"], record["source_identity_commitment"],
                "", "", "true", verifier.boolean_field(flags["no_explicit_skill"]),
                "false", "false",
            ),
        )
        self.resign_aggregate(verifier, cross_domain)
        detached = self.valid_manifest(verifier)
        other = deepcopy(detached)
        other["run_id"] = "run:beta5-pilot-0002"
        for item in other["bindings"]:
            self.resign_record(verifier, other, item)
        self.resign_aggregate(verifier, other)
        detached["reviewer_attestation"]["reviewer_attestation_commitment"] = (
            other["reviewer_attestation"]["reviewer_attestation_commitment"]
        )
        detached["binding_manifest_commitment"] = verifier.compute_commitment(
            SECRET,
            "binding-manifest",
            (
                detached["run_id"], detached["source_revision"],
                detached["runtime_package_digest"], detached["protocol_digest"],
                detached["task_set_commitment"],
                detached["reviewer_attestation"]["reviewer_attestation_commitment"],
                *(item["record_integrity_commitment"] for item in detached["bindings"]),
            ),
        )

        self.assertEqual("pilot-binding-task-commitment-invalid", verifier.verify_manifest(cross_domain, SECRET).code)
        self.assertEqual("pilot-binding-review-invalid", verifier.verify_manifest(detached, SECRET).code)

    def test_wrong_secret_length_and_cli_output_fail_safely(self) -> None:
        verifier = self.verifier()
        manifest = self.valid_manifest(verifier)
        result = verifier.verify_manifest(manifest, b"short")
        self.assertEqual({"valid": False, "code": "pilot-binding-secret-invalid"}, result.public_dict())

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            secret_path = root / "secret.bin"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            secret_path.write_bytes(SECRET)
            completed = subprocess.run(
                [sys.executable, str(VERIFIER_PATH), "--manifest", str(manifest_path), "--secret-file", str(secret_path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(0, completed.returncode)
        self.assertEqual({"valid": True, "code": "pilot-binding-valid"}, json.loads(completed.stdout))
        self.assertNotIn(manifest["bindings"][0]["task_identity"], completed.stdout + completed.stderr)
        self.assertNotIn(SECRET.hex(), completed.stdout + completed.stderr)

    def test_schema_invalid_run_metadata_fails_closed_even_when_resigned(self) -> None:
        verifier = self.verifier()
        manifest = self.valid_manifest(verifier)
        manifest["run_id"] = "short"
        for record in manifest["bindings"]:
            self.resign_record(verifier, manifest, record)
        self.resign_aggregate(verifier, manifest)

        self.assertEqual(
            "pilot-binding-structure-invalid",
            verifier.verify_manifest(manifest, SECRET).code,
        )


if __name__ == "__main__":
    unittest.main()
