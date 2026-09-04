from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from workflow_skill_router.memory.materializer import ProfileMaterializer
from workflow_skill_router.memory.proposals import transition_profile_update
from workflow_skill_router.memory.revisions import ProfileWriteAuthority
from workflow_skill_router.profiles.atomic_io import (
    atomic_write_canonical_json,
    current_json_digest,
    secure_read_json,
)

from memory.test_profile_materializer import prepare_approved


class ProfileRollbackTests(unittest.TestCase):
    def test_rollback_creates_a_new_forward_revision_and_preserves_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, policy, store, _, proposal = prepare_approved(root)
            with store:
                authority = ProfileWriteAuthority.router_local_managed(
                    "developer", "session-m2c"
                )
                materializer = ProfileMaterializer(store, root, policy)
                first = materializer.apply_approved(
                    proposal.proposal_id,
                    authority=authority,
                    expected_state_version=proposal.state_version,
                    idempotency_key="apply-first",
                    correlation_id="corr-apply-first",
                    now="2026-09-04T00:10:00.000Z",
                )
                first_snapshot = materializer.revisions.load_snapshot(first.revision_id)
                target, fixed_root = materializer.target_path(proposal, authority)

                changed = dict(first_snapshot)
                changed_rules = list(changed["rules"])
                changed_rules.append({
                    "rule_id": "manual-extra",
                    "priority": 10,
                    "match": {
                        "objective_keywords": ["manual"],
                        "domains": ["docs"],
                        "tags": [],
                        "work_modes": ["single"],
                    },
                    "route": {
                        "work_mode": "single",
                        "skill_tree": [{
                            "phase_id": "manual",
                            "primary_skill_id": "skill:documentation",
                            "support_skill_ids": [],
                            "exit_gate": "documented",
                        }],
                    },
                })
                changed["rules"] = changed_rules
                changed_digest = atomic_write_canonical_json(
                    target,
                    fixed_root,
                    changed,
                    expected_digest=first.new_profile_digest,
                )

                rollback = materializer.create_rollback_proposal(
                    first.revision_id,
                    authority=authority,
                    expected_profile_digest=changed_digest,
                    now="2026-09-04T01:00:00.000Z",
                )
                self.assertEqual("pending", rollback.status)
                self.assertEqual(changed_digest, rollback.expected_profile_digest)
                self.assertEqual(first_snapshot, rollback.proposed_profile)

                approved = transition_profile_update(
                    store,
                    rollback.proposal_id,
                    action="approve",
                    expected_state_version=rollback.state_version,
                    idempotency_key="approve-rollback",
                    correlation_id="corr-approve-rollback",
                )
                restored = materializer.apply_approved(
                    approved.proposal_id,
                    authority=authority,
                    expected_state_version=approved.state_version,
                    idempotency_key="apply-rollback",
                    correlation_id="corr-apply-rollback",
                    now="2026-09-04T01:10:00.000Z",
                )

                self.assertEqual("rollback", restored.status)
                self.assertEqual(first.revision_id, restored.rollback_source_revision_id)
                self.assertEqual(first_snapshot, secure_read_json(target, fixed_root))
                self.assertEqual(first.new_profile_digest, current_json_digest(target, fixed_root))
                revisions = materializer.revisions.list(first.profile_id)
                self.assertEqual((first.revision_id, restored.revision_id), tuple(item.revision_id for item in revisions))
                self.assertEqual("applied", revisions[0].status)
                self.assertEqual(first_snapshot, materializer.revisions.load_snapshot(first.revision_id))


if __name__ == "__main__":
    unittest.main()
