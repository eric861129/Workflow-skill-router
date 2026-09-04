from __future__ import annotations

import copy
import json
import unittest

from workflow_skill_router.memory import (
    MemoryScope,
    decode_memory_policy,
    resolve_effective_policy,
)
from workflow_skill_router.memory.policy_io import PolicyLoadResult, PolicySource
from workflow_skill_router.memory.store import (
    MemoryPolicySnapshot,
    MemoryPolicySnapshotError,
    decode_memory_policy_snapshot,
)


def reviewed_effective_policy():
    policy = decode_memory_policy(
        {
            "schema_id": "workflow-skill-router/memory-policy",
            "schema_version": "1.0.0",
            "artifact_kind": "memory-policy",
            "policy_id": "personal:snapshot-test",
            "scope": "personal",
            "mode": "reviewed",
        }
    )
    return resolve_effective_policy(
        personal=PolicyLoadResult(
            status="valid",
            source=PolicySource(
                scope=MemoryScope.PERSONAL,
                format="json",
                source_class="personal-policy",
                policy=policy,
            ),
            reason_codes=(),
        ),
        workspace=None,
    )


class MemoryPolicySnapshotTests(unittest.TestCase):
    def test_snapshot_contains_only_bounded_effective_decisions(self) -> None:
        snapshot = MemoryPolicySnapshot.from_effective_policy(
            reviewed_effective_policy()
        )
        document = snapshot.to_dict()

        self.assertEqual(
            {
                "schema_id",
                "schema_version",
                "artifact_kind",
                "snapshot_id",
                "policy_digest",
                "mode",
                "personal_mode",
                "workspace_requested_mode",
                "policy_source",
                "capture_enabled",
                "candidate_generation_enabled",
                "profile_promotion",
                "allowed_targets",
                "features",
                "reason_codes",
            },
            set(document),
        )
        self.assertRegex(snapshot.snapshot_id, r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(snapshot.policy_digest, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual("reviewed", document["mode"])
        self.assertEqual("personal-policy", document["policy_source"])

        serialized = json.dumps(document, ensure_ascii=False, sort_keys=True)
        for forbidden in (
            "source_path",
            "policy_document",
            "raw_prompt",
            "file_paths",
            "file_content",
            "tool_arguments",
            "secrets",
            "/Users/",
            "C:\\",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_snapshot_round_trips_and_tampering_is_rejected(self) -> None:
        original = MemoryPolicySnapshot.from_effective_policy(
            reviewed_effective_policy()
        )
        decoded = decode_memory_policy_snapshot(original.to_dict())

        self.assertEqual(original, decoded)
        self.assertEqual(original.canonical_json(), decoded.canonical_json())

        tampered = copy.deepcopy(original.to_dict())
        tampered["mode"] = "observe"
        with self.assertRaisesRegex(
            MemoryPolicySnapshotError,
            "memory-policy-snapshot-id-mismatch",
        ):
            decode_memory_policy_snapshot(tampered)

    def test_unknown_fields_paths_and_unbounded_reason_codes_fail_closed(self) -> None:
        original = MemoryPolicySnapshot.from_effective_policy(
            reviewed_effective_policy()
        ).to_dict()

        unknown = copy.deepcopy(original)
        unknown["source_path"] = "/tmp/private/workflow-memory.yaml"
        with self.assertRaisesRegex(
            MemoryPolicySnapshotError,
            "unknown-field:source_path",
        ):
            decode_memory_policy_snapshot(unknown)

        path_reason = copy.deepcopy(original)
        path_reason["reason_codes"] = ["/tmp/private"]
        with self.assertRaisesRegex(
            MemoryPolicySnapshotError,
            "invalid-reason-code",
        ):
            decode_memory_policy_snapshot(path_reason)

        raw_feature = copy.deepcopy(original)
        raw_feature["features"]["route_feedback"]["free_text"] = "private"
        with self.assertRaisesRegex(
            MemoryPolicySnapshotError,
            "invalid-features",
        ):
            decode_memory_policy_snapshot(raw_feature)


if __name__ == "__main__":
    unittest.main()
