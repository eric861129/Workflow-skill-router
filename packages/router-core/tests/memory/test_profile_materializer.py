from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from workflow_skill_router.memory.candidates import CandidateEngine
from workflow_skill_router.memory.managed_profiles import verify_workspace_root
from workflow_skill_router.memory.materializer import (
    ProfileMaterializationError,
    ProfileMaterializer,
)
from workflow_skill_router.memory.models import MemoryMode, MemoryScope
from workflow_skill_router.memory.policy_io import MemoryPolicyRepository
from workflow_skill_router.memory.policy_resolver import resolve_effective_policy
from workflow_skill_router.memory.proposals import (
    create_profile_update_proposal,
    transition_profile_update,
)
from workflow_skill_router.memory.revisions import ProfileWriteAuthority
from workflow_skill_router.memory.store import MemoryStore
from workflow_skill_router.profiles.atomic_io import (
    atomic_write_canonical_json,
    current_json_digest,
    secure_read_json,
)
from workflow_skill_router.profiles.contract import decode_routing_profile

from memory.m1c_fixture import M1CHistoryFixture, write_feedback_policy


def prepare_approved(root: Path, *, mode: str = "reviewed"):
    write_feedback_policy(root, mode=mode)
    fixture = M1CHistoryFixture(root)
    # The fixture constructor writes a reviewed policy; restore the requested mode.
    write_feedback_policy(root, mode=mode)
    fixture.insert_observations(
        count=5 if mode == "automatic" else 3,
        dates=(
            "2026-09-01T00:00:00.000Z",
            "2026-09-02T00:00:00.000Z",
            "2026-09-03T00:00:00.000Z",
        ),
    )
    policy = resolve_effective_policy(
        personal=MemoryPolicyRepository(root).inspect_personal(), workspace=None
    )
    store = MemoryStore.open_if_enabled(root, policy)
    assert store is not None
    candidate = CandidateEngine(store, policy).rebuild(
        MemoryScope.PERSONAL, "2026-09-04T00:00:00.000Z"
    )[0]
    proposal = create_profile_update_proposal(
        store,
        candidate,
        current_profile=None,
        policy=policy,
        now="2026-09-04T00:00:00.000Z",
    )
    proposal = transition_profile_update(
        store,
        proposal.proposal_id,
        action="approve",
        expected_state_version=proposal.state_version,
        idempotency_key="approve-materialization",
        correlation_id="corr-approve-materialization",
    )
    return fixture, policy, store, candidate, proposal


class ProfileMaterializerTests(unittest.TestCase):
    def test_approved_managed_personal_proposal_is_atomically_applied_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, policy, store, _, proposal = prepare_approved(root)
            with store:
                materializer = ProfileMaterializer(store, root, policy)
                authority = ProfileWriteAuthority.router_local_managed(
                    "developer", "session-m2c"
                )
                revision = materializer.apply_approved(
                    proposal.proposal_id,
                    authority=authority,
                    expected_state_version=proposal.state_version,
                    idempotency_key="apply-proposal",
                    correlation_id="corr-apply-proposal",
                    now="2026-09-04T00:10:00.000Z",
                )
                replay = materializer.apply_approved(
                    proposal.proposal_id,
                    authority=authority,
                    expected_state_version=proposal.state_version,
                    idempotency_key="apply-proposal",
                    correlation_id="corr-apply-proposal",
                    now="2026-09-04T00:10:00.000Z",
                )

                self.assertEqual("applied", revision.status)
                self.assertEqual(revision, replay)
                self.assertEqual("applied", store.load_profile_update_proposal(proposal.proposal_id).status)
                target = materializer.target_path(proposal, authority)[0]
                stored = secure_read_json(target, root)
                self.assertEqual(proposal.proposed_profile, stored)
                self.assertEqual(proposal.proposed_profile_digest, current_json_digest(target, root))
                self.assertEqual(proposal.proposed_profile, materializer.revisions.load_snapshot(revision.revision_id))
                self.assertEqual((revision,), materializer.revisions.list("personal:adaptive-memory"))

    def test_profile_drift_marks_proposal_stale_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, policy, store, _, proposal = prepare_approved(root)
            with store:
                materializer = ProfileMaterializer(store, root, policy)
                authority = ProfileWriteAuthority.router_local_managed("developer", "session-m2c")
                target, fixed_root = materializer.target_path(proposal, authority)
                changed = dict(proposal.proposed_profile)
                changed["enabled"] = False
                changed = decode_routing_profile(changed)
                changed_document = {
                    **proposal.proposed_profile,
                    "enabled": changed.enabled,
                }
                atomic_write_canonical_json(target, fixed_root, changed_document, "missing")

                with self.assertRaisesRegex(ProfileMaterializationError, "profile-drift"):
                    materializer.apply_approved(
                        proposal.proposal_id,
                        authority=authority,
                        expected_state_version=proposal.state_version,
                        idempotency_key="apply-drifted",
                        correlation_id="corr-apply-drifted",
                        now="2026-09-04T00:10:00.000Z",
                    )

                self.assertEqual(changed_document, secure_read_json(target, fixed_root))
                self.assertEqual("stale", store.load_profile_update_proposal(proposal.proposal_id).status)
                self.assertEqual((), materializer.revisions.list("personal:adaptive-memory"))

    def test_target_authority_and_automatic_user_owned_boundaries_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, policy, store, _, proposal = prepare_approved(root)
            with store:
                materializer = ProfileMaterializer(store, root, policy)
                wrong = ProfileWriteAuthority.reviewed_user_local("developer", "session-m2c")
                with self.assertRaisesRegex(ProfileMaterializationError, "profile-authority-mismatch"):
                    materializer.apply_approved(
                        proposal.proposal_id,
                        authority=wrong,
                        expected_state_version=proposal.state_version,
                        idempotency_key="wrong-authority",
                        correlation_id="corr-wrong-authority",
                        now="2026-09-04T00:10:00.000Z",
                    )

            automatic_root = root / "automatic"
            _, automatic, automatic_store, _, automatic_proposal = prepare_approved(
                automatic_root, mode="automatic"
            )
            self.assertEqual(MemoryMode.AUTOMATIC, automatic.mode)
            user_proposal = replace(
                automatic_proposal,
                target_profile_class="user-personal",
            )
            with automatic_store:
                # A caller cannot turn an automatic managed proposal into a user-owned write.
                materializer = ProfileMaterializer(automatic_store, automatic_root, automatic)
                with self.assertRaisesRegex(ProfileMaterializationError, "automatic-user-profile-forbidden"):
                    materializer.target_path(
                        user_proposal,
                        ProfileWriteAuthority.reviewed_user_local("developer", "session-m2c"),
                    )

    def test_atomic_write_failure_marks_revision_and_proposal_failed_without_recovery_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, policy, store, _, proposal = prepare_approved(root)
            with store:
                materializer = ProfileMaterializer(store, root, policy)
                authority = ProfileWriteAuthority.router_local_managed(
                    "developer", "session-m2c"
                )
                with patch(
                    "workflow_skill_router.memory.materializer.atomic_write_canonical_json",
                    side_effect=RuntimeError("simulated-atomic-write-failure"),
                ):
                    with self.assertRaisesRegex(
                        ProfileMaterializationError,
                        "profile-atomic-write-failed",
                    ):
                        materializer.apply_approved(
                            proposal.proposal_id,
                            authority=authority,
                            expected_state_version=proposal.state_version,
                            idempotency_key="atomic-write-failure",
                            correlation_id="corr-atomic-write-failure",
                            now="2026-09-04T00:10:00.000Z",
                        )

                self.assertEqual(
                    "failed",
                    store.load_profile_update_proposal(proposal.proposal_id).status,
                )
                revisions = materializer.revisions.list("personal:adaptive-memory")
                self.assertEqual(1, len(revisions))
                self.assertEqual("failed", revisions[0].status)
                marker = store._require_open().execute(
                    "SELECT 1 FROM profile_recovery_markers WHERE proposal_id=?",
                    (proposal.proposal_id,),
                ).fetchone()
                self.assertIsNone(marker)
                target = materializer.target_path(proposal, authority)[0]
                self.assertFalse(target.exists())

    def test_recovery_finalizes_exact_written_profile_without_rewriting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, policy, store, _, proposal = prepare_approved(root)
            with store:
                materializer = ProfileMaterializer(store, root, policy)
                authority = ProfileWriteAuthority.router_local_managed("developer", "session-m2c")
                original_finalize = materializer._finalize
                with patch.object(materializer, "_finalize", side_effect=ProfileMaterializationError("simulated-finalize-failure")):
                    with self.assertRaisesRegex(ProfileMaterializationError, "simulated-finalize-failure"):
                        materializer.apply_approved(
                            proposal.proposal_id,
                            authority=authority,
                            expected_state_version=proposal.state_version,
                            idempotency_key="recover-apply",
                            correlation_id="corr-recover-apply",
                            now="2026-09-04T00:10:00.000Z",
                        )
                target, fixed_root = materializer.target_path(proposal, authority)
                before = target.read_bytes()
                materializer._finalize = original_finalize
                recovered = materializer.apply_approved(
                    proposal.proposal_id,
                    authority=authority,
                    expected_state_version=proposal.state_version,
                    idempotency_key="recover-apply",
                    correlation_id="corr-recover-apply",
                    now="2026-09-04T00:10:00.000Z",
                )
                self.assertEqual("applied", recovered.status)
                self.assertEqual(before, target.read_bytes())
                self.assertEqual(proposal.proposed_profile_digest, current_json_digest(target, fixed_root))


    def test_reviewed_managed_workspace_proposal_uses_fixed_digest_scoped_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy_path = root / "config/workflow-memory.json"
            policy_path.parent.mkdir(parents=True, exist_ok=True)
            policy_path.write_text(
                '{"schema_id":"workflow-skill-router/memory-policy","schema_version":"1.0.0","artifact_kind":"memory-policy","policy_id":"personal:workspace-managed","scope":"personal","mode":"reviewed","features":{"remember_this_workflow":{"default_target":"managed-workspace-local"},"profile_promotion":{"target":"managed-workspace-local"}}}',
                encoding="utf-8",
            )
            fixture = M1CHistoryFixture(root)
            # The fixture writes its default Policy; restore this test's target.
            policy_path.write_text(
                '{"schema_id":"workflow-skill-router/memory-policy","schema_version":"1.0.0","artifact_kind":"memory-policy","policy_id":"personal:workspace-managed","scope":"personal","mode":"reviewed","features":{"remember_this_workflow":{"default_target":"managed-workspace-local"},"profile_promotion":{"target":"managed-workspace-local"}}}',
                encoding="utf-8",
            )
            workspace = root / "workspace"
            workspace.mkdir()
            workspace_digest = verify_workspace_root(workspace).digest
            fixture.insert_observations(
                count=3,
                dates=("2026-09-01T00:00:00.000Z", "2026-09-02T00:00:00.000Z"),
                workspaces=(workspace_digest,) * 3,
                target_profile_class="managed-workspace-local",
            )
            policy = fixture.effective_policy()
            store = MemoryStore.open_if_enabled(root, policy)
            assert store is not None
            with store:
                candidate = CandidateEngine(store, policy).rebuild(
                    MemoryScope.WORKSPACE, "2026-09-04T00:00:00.000Z"
                )[0]
                proposal = create_profile_update_proposal(
                    store, candidate, current_profile=None, policy=policy,
                    now="2026-09-04T00:00:00.000Z",
                )
                proposal = transition_profile_update(
                    store, proposal.proposal_id, action="approve",
                    expected_state_version=proposal.state_version,
                    idempotency_key="approve-workspace-managed",
                    correlation_id="corr-approve-workspace-managed",
                )
                materializer = ProfileMaterializer(store, root, policy)
                revision = materializer.apply_approved(
                    proposal.proposal_id,
                    authority=ProfileWriteAuthority.router_local_managed(
                        "developer", "session-m3a"
                    ),
                    expected_state_version=proposal.state_version,
                    idempotency_key="apply-workspace-managed",
                    correlation_id="corr-apply-workspace-managed",
                    now="2026-09-04T00:10:00.000Z",
                )
                target, fixed_root = materializer.target_path(
                    proposal,
                    ProfileWriteAuthority.router_local_managed(
                        "developer", "session-m3a"
                    ),
                )
                self.assertEqual("applied", revision.status)
                self.assertEqual(
                    root / "profiles/managed/workspace"
                    / workspace_digest.removeprefix("sha256:")
                    / "adaptive-memory.json",
                    target,
                )
                self.assertEqual(root, fixed_root)
                self.assertEqual("workspace", secure_read_json(target, root)["scope"])


if __name__ == "__main__":
    unittest.main()
