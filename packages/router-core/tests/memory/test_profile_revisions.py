from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from workflow_skill_router.memory.revisions import (
    ProfileRevisionError,
    ProfileRevisionStore,
    ProfileTarget,
    ProfileWriteAuthority,
    create_profile_revision,
    decode_profile_revision,
)
from workflow_skill_router.memory.policy_io import MemoryPolicyRepository
from workflow_skill_router.memory.policy_resolver import resolve_effective_policy
from workflow_skill_router.memory.store import MemoryStore

from memory.m1c_fixture import write_feedback_policy


def profile_document() -> dict[str, object]:
    return {
        "schema_id": "workflow-skill-router/routing-profile",
        "schema_version": "1.0.0",
        "artifact_kind": "routing-profile",
        "profile_id": "personal:adaptive-memory",
        "scope": "personal",
        "enabled": True,
        "rules": [{
            "rule_id": "memory-api",
            "priority": 100,
            "match": {
                "objective_keywords": ["student api"],
                "domains": ["api"],
                "tags": [],
                "work_modes": ["single"],
            },
            "route": {
                "work_mode": "single",
                "skill_tree": [{
                    "phase_id": "delivery",
                    "primary_skill_id": "skill:api-designer",
                    "support_skill_ids": [],
                    "exit_gate": "delivery-complete",
                }],
            },
        }],
    }


class ProfileRevisionTests(unittest.TestCase):
    def test_revision_contract_round_trips_and_detects_tampering(self) -> None:
        revision = create_profile_revision(
            profile_id="personal:adaptive-memory",
            target=ProfileTarget("managed-personal", "personal:adaptive-memory", None),
            previous_profile_digest="missing",
            new_profile_digest="sha256:" + "1" * 64,
            proposal_id="proposal:" + "2" * 32,
            proposal_digest="sha256:" + "3" * 64,
            candidate_id="candidate:" + "4" * 32,
            candidate_digest="sha256:" + "5" * 64,
            policy_digest="sha256:" + "6" * 64,
            semantic_diff_digest="sha256:" + "7" * 64,
            backtest_digest="sha256:" + "8" * 64,
            authority=ProfileWriteAuthority.router_local_managed("developer", "session-m2c"),
            snapshot_digest="sha256:" + "9" * 64,
            status="pending",
            created_at="2026-09-04T12:00:00.000Z",
        )

        decoded = decode_profile_revision(revision.to_dict())
        self.assertEqual(revision, decoded)
        self.assertRegex(revision.revision_id, r"^revision:[0-9a-f]{32}$")
        self.assertRegex(revision.revision_digest, r"^sha256:[0-9a-f]{64}$")

        tampered = revision.to_dict()
        tampered["new_profile_digest"] = "sha256:" + "a" * 64
        with self.assertRaisesRegex(ProfileRevisionError, "revision-digest-mismatch"):
            decode_profile_revision(tampered)

    def test_snapshot_store_uses_fixed_immutable_path_and_revision_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_feedback_policy(root, mode="reviewed")
            policy = resolve_effective_policy(
                personal=MemoryPolicyRepository(root).inspect_personal(), workspace=None
            )
            store = MemoryStore.open_if_enabled(root, policy)
            assert store is not None
            with store:
                revisions = ProfileRevisionStore(root, store)
                document = profile_document()
                snapshot_digest = revisions.snapshot_digest(document)
                revision = create_profile_revision(
                    profile_id="personal:adaptive-memory",
                    target=ProfileTarget("managed-personal", "personal:adaptive-memory", None),
                    previous_profile_digest="missing",
                    new_profile_digest=snapshot_digest,
                    proposal_id="proposal:" + "2" * 32,
                    proposal_digest="sha256:" + "3" * 64,
                    candidate_id="candidate:" + "4" * 32,
                    candidate_digest="sha256:" + "5" * 64,
                    policy_digest=policy.policy_digest,
                    semantic_diff_digest="sha256:" + "7" * 64,
                    backtest_digest="sha256:" + "8" * 64,
                    authority=ProfileWriteAuthority.router_local_managed("developer", "session-m2c"),
                    snapshot_digest=snapshot_digest,
                    status="pending",
                    created_at="2026-09-04T12:00:00.000Z",
                )
                revisions.write_snapshot(revision, document)
                revisions.record(revision)

                self.assertEqual(document, revisions.load_snapshot(revision.revision_id))
                self.assertEqual((revision,), revisions.list("personal:adaptive-memory"))
                with self.assertRaisesRegex(ProfileRevisionError, "revision-snapshot-already-exists"):
                    revisions.write_snapshot(revision, {**document, "enabled": False})

                snapshot = revisions.snapshot_path(revision)
                self.assertTrue(snapshot.is_file())
                self.assertNotIn("..", snapshot.relative_to(root).parts)


if __name__ == "__main__":
    unittest.main()
