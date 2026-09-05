from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from workflow_skill_router.memory import (
    CandidateEngine,
    MemoryCommandConflict,
    MemoryMode,
    MemoryScope,
    MemoryStore,
    ProfileMaterializationError,
    ProfileMaterializer,
    ProfileRevisionStore,
    ProfileWriteAuthority,
    WorkflowMemoryService,
    create_profile_update_proposal,
    transition_profile_update,
    automatic_promotion_reason_codes,
    managed_personal_profile_path,
    managed_workspace_profile_path,
    verify_workspace_root,
)
from workflow_skill_router.profiles.atomic_io import secure_read_json
from workflow_skill_router.profiles.storage import RoutingProfileRepository

from memory.m1c_fixture import M1CHistoryFixture, write_feedback_policy


_DATES = (
    "2026-09-01T10:00:00.000Z",
    "2026-09-02T10:00:00.000Z",
    "2026-09-03T10:00:00.000Z",
)


def prepare_automatic_candidate(root: Path):
    fixture = M1CHistoryFixture(root)
    write_feedback_policy(root, mode="automatic")
    fixture.insert_observations(
        count=5,
        dates=_DATES,
        route_sources=("builtin",) * 5,
        matcher_source="trusted-routing-context",
    )
    policy = fixture.effective_policy()
    store = MemoryStore.open_if_enabled(root, policy)
    assert store is not None
    with store:
        candidate = CandidateEngine(store, policy).rebuild(
            MemoryScope.PERSONAL,
            "2026-09-04T00:00:00.000Z",
        )[0]
    return fixture, policy, candidate


def write_conflicting_manual_profile(root: Path) -> None:
    directory = root / "profiles" / "personal"
    directory.mkdir(parents=True, exist_ok=True)
    document = {
        "schema_id": "workflow-skill-router/routing-profile",
        "schema_version": "1.0.0",
        "artifact_kind": "routing-profile",
        "profile_id": "personal:manual-api",
        "scope": "personal",
        "enabled": True,
        "rules": [
            {
                "rule_id": "manual-student-api",
                "priority": 1,
                "match": {
                    "objective_keywords": ["student api"],
                    "domains": ["api"],
                    "tags": [],
                    "work_modes": ["single"],
                },
                "route": {
                    "work_mode": "single",
                    "skill_tree": [
                        {
                            "phase_id": "single-work",
                            "primary_skill_id": "skill:manual-api",
                            "support_skill_ids": [],
                            "exit_gate": "manual-complete",
                        }
                    ],
                },
            }
        ],
    }
    (directory / "manual-api.json").write_text(
        json.dumps(document), encoding="utf-8"
    )


def write_conflicting_workspace_profile(workspace: Path) -> None:
    directory = workspace / ".codex"
    directory.mkdir(parents=True, exist_ok=True)
    document = {
        "schema_id": "workflow-skill-router/routing-profile",
        "schema_version": "1.0.0",
        "artifact_kind": "routing-profile",
        "profile_id": "workspace:manual-api",
        "scope": "workspace",
        "enabled": True,
        "rules": [
            {
                "rule_id": "manual-workspace-student-api",
                "priority": 1,
                "match": {
                    "objective_keywords": ["student api"],
                    "domains": ["api"],
                    "tags": [],
                    "work_modes": ["single"],
                },
                "route": {
                    "work_mode": "single",
                    "skill_tree": [
                        {
                            "phase_id": "single-work",
                            "primary_skill_id": "skill:manual-api",
                            "support_skill_ids": [],
                            "exit_gate": "manual-complete",
                        }
                    ],
                },
            }
        ],
    }
    (directory / "workflow-skill-router.json").write_text(
        json.dumps(document), encoding="utf-8"
    )


class AutomaticPromotionTests(unittest.TestCase):
    def test_gate_rejects_every_hard_automatic_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, policy, candidate = prepare_automatic_candidate(Path(directory))
            self.assertEqual(MemoryMode.AUTOMATIC, policy.mode)
            self.assertEqual((), automatic_promotion_reason_codes(candidate, policy))

            cases = (
                (
                    replace(candidate, policy_digest="sha256:" + "f" * 64),
                    policy,
                    "candidate-policy-drift",
                ),
                (
                    replace(candidate, target_profile_class="user-personal"),
                    policy,
                    "automatic-user-profile-write-forbidden",
                ),
                (
                    replace(candidate, confidence="medium"),
                    policy,
                    "candidate-confidence-not-high",
                ),
                (
                    replace(candidate, recommendation_mode="reviewed"),
                    policy,
                    "candidate-not-automatic",
                ),
                (
                    replace(
                        candidate,
                        matcher_seed=replace(candidate.matcher_seed, source="user-explicit"),
                        profile_source_class="user-explicit",
                    ),
                    policy,
                    "candidate-explicit-route",
                ),
                (
                    replace(
                        candidate,
                        metrics=replace(
                            candidate.metrics,
                            canonical_skill_ids=False,
                        ),
                    ),
                    policy,
                    "candidate-skill-id-invalid",
                ),
                (
                    replace(
                        candidate,
                        metrics=replace(
                            candidate.metrics,
                            hard_contract_violations=1,
                        ),
                    ),
                    policy,
                    "candidate-hard-violation",
                ),
                (
                    candidate,
                    replace(policy, mode=MemoryMode.REVIEWED),
                    "memory-mode-not-automatic",
                ),
                (
                    candidate,
                    replace(
                        policy,
                        policy=replace(
                            policy.policy,
                            eligibility=replace(
                                policy.policy.eligibility,
                                minimum_distinct_runs_automatic=4,
                            ),
                        ),
                    ),
                    "automatic-threshold-weaker",
                ),
                (
                    candidate,
                    replace(
                        policy,
                        policy=replace(
                            policy.policy,
                            features=replace(
                                policy.policy.features,
                                profile_promotion=replace(
                                    policy.policy.features.profile_promotion,
                                    require_backtest=False,
                                ),
                            ),
                        ),
                    ),
                    "backtest-required",
                ),
            )
            for guarded_candidate, guarded_policy, reason in cases:
                with self.subTest(reason=reason):
                    self.assertIn(
                        reason,
                        automatic_promotion_reason_codes(
                            guarded_candidate, guarded_policy
                        ),
                    )

    def test_r3_evidence_never_creates_a_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = M1CHistoryFixture(root)
            write_feedback_policy(root, mode="automatic")
            fixture.insert_observations(
                count=5,
                dates=_DATES,
                route_sources=("builtin",) * 5,
                matcher_source="trusted-routing-context",
                risk_class="r3",
            )
            policy = fixture.effective_policy()
            store = MemoryStore.open_if_enabled(root, policy)
            assert store is not None
            with store:
                self.assertEqual(
                    (),
                    CandidateEngine(store, policy).rebuild(
                        MemoryScope.PERSONAL,
                        "2026-09-04T00:00:00.000Z",
                    ),
                )

    def test_unknown_skill_is_review_only_and_never_automatically_written(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = M1CHistoryFixture(root)
            write_feedback_policy(root, mode="automatic")
            fixture.insert_observations(
                count=5,
                dates=_DATES,
                route_sources=("builtin",) * 5,
                matcher_source="trusted-routing-context",
                primary_skill_id="skill:",
            )
            policy = fixture.effective_policy()
            store = MemoryStore.open_if_enabled(root, policy)
            assert store is not None
            with store:
                candidates = CandidateEngine(store, policy).rebuild(
                    MemoryScope.PERSONAL,
                    "2026-09-04T00:00:00.000Z",
                )
            self.assertEqual(1, len(candidates))
            self.assertEqual("reviewed", candidates[0].recommendation_mode)
            self.assertIn(
                "candidate-skill-id-invalid",
                automatic_promotion_reason_codes(candidates[0], policy),
            )
            result = fixture.service.promote_eligible_candidates(
                MemoryScope.PERSONAL,
                actor_id="developer",
                session_id="session-unknown-skill",
                idempotency_key="promote-unknown-skill",
                correlation_id="corr-promote-unknown-skill",
                now="2026-09-04T00:10:00.000Z",
            )
            self.assertEqual(0, result.promoted_count)
            self.assertEqual(1, result.skipped_count)
            self.assertIn(
                "candidate-skill-id-invalid",
                result.notifications[0].reason_codes,
            )
            self.assertFalse(managed_personal_profile_path(root).exists())

    def test_reviewed_mode_never_promotes_or_creates_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = M1CHistoryFixture(root)
            fixture.insert_observations(
                count=5,
                dates=_DATES,
                route_sources=("builtin",) * 5,
                matcher_source="trusted-routing-context",
            )
            fixture.service.rebuild_candidates(MemoryScope.PERSONAL)
            result = fixture.service.promote_eligible_candidates(
                MemoryScope.PERSONAL,
                actor_id="developer",
                session_id="session-reviewed",
                idempotency_key="promote-reviewed",
                correlation_id="corr-promote-reviewed",
                now="2026-09-04T00:10:00.000Z",
            )
            self.assertEqual("not-automatic", result.status)
            self.assertEqual(0, result.promoted_count)
            self.assertFalse(managed_personal_profile_path(root).exists())
            store = MemoryStore.open_if_enabled(root, fixture.effective_policy())
            assert store is not None
            with store:
                self.assertEqual(
                    0,
                    int(
                        store._require_open()
                        .execute("SELECT COUNT(*) FROM profile_revisions")
                        .fetchone()[0]
                    ),
                )

    def test_five_consistent_runs_promote_one_managed_profile_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture, _, candidate = prepare_automatic_candidate(root)
            result = fixture.service.promote_eligible_candidates(
                MemoryScope.PERSONAL,
                actor_id="developer",
                session_id="session-m3b",
                idempotency_key="promote-personal",
                correlation_id="corr-promote-personal",
                now="2026-09-04T00:10:00.000Z",
            )
            self.assertEqual("completed", result.status)
            self.assertEqual(MemoryScope.PERSONAL, result.scope)
            self.assertEqual(1, result.promoted_count)
            self.assertEqual(0, result.suppressed_count)
            self.assertEqual(0, result.skipped_count)
            self.assertEqual("explicit-local", result.operation_mode)
            self.assertEqual("router-local", result.authority_mode)
            self.assertEqual(1, len(result.notifications))
            notification = result.notifications[0]
            self.assertEqual("promoted", notification.status)
            self.assertEqual(candidate.candidate_id, notification.candidate_id)
            self.assertEqual(("automatic-promotion-applied",), notification.reason_codes)

            target = managed_personal_profile_path(root)
            stored = secure_read_json(target, root)
            self.assertIsNotNone(stored)
            self.assertEqual("personal:adaptive-memory", stored["profile_id"])

            policy = fixture.effective_policy()
            store = MemoryStore.open_if_enabled(root, policy)
            assert store is not None
            with store:
                promoted = store.load_workflow_candidate(candidate.candidate_id)
                self.assertIsNotNone(promoted)
                self.assertEqual("auto-promoted", promoted.status)
                revisions = ProfileRevisionStore(root, store).list(
                    "personal:adaptive-memory"
                )
                self.assertEqual(1, len(revisions))
                self.assertEqual("applied", revisions[0].status)

            replay = fixture.service.promote_eligible_candidates(
                MemoryScope.PERSONAL,
                actor_id="developer",
                session_id="session-m3b",
                idempotency_key="promote-personal",
                correlation_id="corr-promote-personal",
                now="2026-09-04T00:10:00.000Z",
            )
            self.assertEqual(1, replay.promoted_count)
            self.assertTrue(replay.replayed)
            original_document = result.to_dict()
            replay_document = replay.to_dict()
            self.assertFalse(original_document.pop("replayed"))
            self.assertTrue(replay_document.pop("replayed"))
            self.assertEqual(original_document, replay_document)

            with self.assertRaisesRegex(
                MemoryCommandConflict, "memory-idempotency-conflict"
            ):
                fixture.service.promote_eligible_candidates(
                    MemoryScope.PERSONAL,
                    actor_id="developer",
                    session_id="session-m3b",
                    idempotency_key="promote-personal",
                    correlation_id="corr-promote-personal-changed",
                    now="2026-09-04T00:10:00.000Z",
                )

            store = MemoryStore.open_if_enabled(root, fixture.effective_policy())
            assert store is not None
            with store:
                self.assertEqual(
                    1,
                    len(
                        ProfileRevisionStore(root, store).list(
                            "personal:adaptive-memory"
                        )
                    ),
                )

    def test_materializer_rechecks_manual_conflict_immediately_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture, policy, candidate = prepare_automatic_candidate(root)
            store = MemoryStore.open_if_enabled(root, policy)
            assert store is not None
            with store:
                proposal = create_profile_update_proposal(
                    store,
                    candidate,
                    current_profile=None,
                    policy=policy,
                    now="2026-09-04T00:05:00.000Z",
                    manual_profiles=(),
                    automatic=True,
                )
                approved = transition_profile_update(
                    store,
                    proposal.proposal_id,
                    action="approve",
                    expected_state_version=proposal.state_version,
                    idempotency_key="approve-before-race",
                    correlation_id="corr-before-race",
                    now="2026-09-04T00:06:00.000Z",
                )
                write_conflicting_manual_profile(root)
                manual_profiles = RoutingProfileRepository(root).list_personal()
                with self.assertRaisesRegex(
                    ProfileMaterializationError, "candidate-conflict"
                ):
                    ProfileMaterializer(store, root, policy).apply_approved(
                        approved.proposal_id,
                        authority=ProfileWriteAuthority.router_local_managed(
                            "developer", "session-race"
                        ),
                        expected_state_version=approved.state_version,
                        idempotency_key="apply-after-race",
                        correlation_id="corr-after-race",
                        now="2026-09-04T00:07:00.000Z",
                        manual_profiles=manual_profiles,
                        candidate_final_status="auto-promoted",
                    )
                stale = store.load_profile_update_proposal(proposal.proposal_id)
                self.assertIsNotNone(stale)
                self.assertEqual("stale", stale.status)
                current_candidate = store.load_workflow_candidate(candidate.candidate_id)
                self.assertIsNotNone(current_candidate)
                self.assertEqual("proposed", current_candidate.status)
                self.assertFalse(managed_personal_profile_path(root).exists())


    def test_workspace_promotion_is_bound_to_the_verified_workspace_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            other_workspace = root / "other-workspace"
            workspace.mkdir()
            other_workspace.mkdir()
            identity = verify_workspace_root(workspace)
            fixture = M1CHistoryFixture(root)
            write_feedback_policy(
                root,
                mode="automatic",
                promotion_target="managed-workspace-local",
            )
            fixture.insert_observations(
                count=5,
                dates=_DATES,
                route_sources=("builtin",) * 5,
                matcher_source="trusted-routing-context",
                target_profile_class="managed-workspace-local",
                workspaces=(identity.digest,) * 5,
            )
            fixture.service.rebuild_candidates(
                MemoryScope.WORKSPACE,
                workspace_root=workspace,
            )

            blocked = fixture.service.promote_eligible_candidates(
                MemoryScope.WORKSPACE,
                workspace_root=other_workspace,
                actor_id="developer",
                session_id="session-workspace-wrong",
                idempotency_key="promote-workspace-wrong",
                correlation_id="corr-promote-workspace-wrong",
                now="2026-09-04T00:10:00.000Z",
            )
            self.assertEqual(0, blocked.promoted_count)
            self.assertEqual(1, blocked.skipped_count)
            self.assertEqual(
                ("workspace-root-unverified",),
                blocked.notifications[0].reason_codes,
            )
            target = managed_workspace_profile_path(root, identity.digest)
            self.assertFalse(target.exists())

            # A User-owned Personal Profile is below Managed Workspace-local in
            # the fixed M3-A ownership order and therefore cannot suppress it.
            write_conflicting_manual_profile(root)
            result = fixture.service.promote_eligible_candidates(
                MemoryScope.WORKSPACE,
                workspace_root=workspace,
                actor_id="developer",
                session_id="session-workspace",
                idempotency_key="promote-workspace",
                correlation_id="corr-promote-workspace",
                now="2026-09-04T00:11:00.000Z",
            )
            self.assertEqual(1, result.promoted_count)
            self.assertEqual("managed-workspace-local", result.notifications[0].target_profile_class)
            stored = secure_read_json(target, root)
            self.assertIsNotNone(stored)
            self.assertEqual("workspace:adaptive-memory", stored["profile_id"])
            self.assertNotIn(str(workspace), json.dumps(result.to_dict()))


    def test_user_workspace_conflict_suppresses_managed_workspace_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            workspace.mkdir()
            identity = verify_workspace_root(workspace)
            fixture = M1CHistoryFixture(root)
            write_feedback_policy(
                root,
                mode="automatic",
                promotion_target="managed-workspace-local",
            )
            fixture.insert_observations(
                count=5,
                dates=_DATES,
                route_sources=("builtin",) * 5,
                matcher_source="trusted-routing-context",
                target_profile_class="managed-workspace-local",
                workspaces=(identity.digest,) * 5,
            )
            fixture.service.rebuild_candidates(
                MemoryScope.WORKSPACE,
                workspace_root=workspace,
            )
            write_conflicting_workspace_profile(workspace)

            result = fixture.service.promote_eligible_candidates(
                MemoryScope.WORKSPACE,
                workspace_root=workspace,
                actor_id="developer",
                session_id="session-workspace-conflict",
                idempotency_key="promote-workspace-conflict",
                correlation_id="corr-promote-workspace-conflict",
                now="2026-09-04T00:10:00.000Z",
            )
            self.assertEqual(0, result.promoted_count)
            self.assertEqual(1, result.suppressed_count)
            self.assertEqual(
                ("candidate-conflict", "candidate-suppressed"),
                result.notifications[0].reason_codes,
            )
            self.assertFalse(
                managed_workspace_profile_path(root, identity.digest).exists()
            )

    def test_automatic_recovery_finalizes_candidate_without_rewriting_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture, policy, candidate = prepare_automatic_candidate(root)
            store = MemoryStore.open_if_enabled(root, policy)
            assert store is not None
            with store:
                proposal = create_profile_update_proposal(
                    store,
                    candidate,
                    current_profile=None,
                    policy=policy,
                    now="2026-09-04T00:05:00.000Z",
                    manual_profiles=(),
                    automatic=True,
                )
                approved = transition_profile_update(
                    store,
                    proposal.proposal_id,
                    action="approve",
                    expected_state_version=proposal.state_version,
                    idempotency_key="approve-auto-recovery",
                    correlation_id="corr-auto-recovery",
                    now="2026-09-04T00:06:00.000Z",
                )
                materializer = ProfileMaterializer(store, root, policy)
                authority = ProfileWriteAuthority.router_local_managed(
                    "developer", "session-auto-recovery"
                )
                original_finalize = materializer._finalize
                with patch.object(
                    materializer,
                    "_finalize",
                    side_effect=ProfileMaterializationError(
                        "simulated-finalize-failure"
                    ),
                ):
                    with self.assertRaisesRegex(
                        ProfileMaterializationError,
                        "simulated-finalize-failure",
                    ):
                        materializer.apply_approved(
                            approved.proposal_id,
                            authority=authority,
                            expected_state_version=approved.state_version,
                            idempotency_key="apply-auto-recovery",
                            correlation_id="corr-auto-recovery",
                            now="2026-09-04T00:07:00.000Z",
                            manual_profiles=(),
                            candidate_final_status="auto-promoted",
                        )
                target = managed_personal_profile_path(root)
                before = target.read_bytes()
                materializer._finalize = original_finalize
                recovered = materializer.apply_approved(
                    approved.proposal_id,
                    authority=authority,
                    expected_state_version=approved.state_version,
                    idempotency_key="apply-auto-recovery",
                    correlation_id="corr-auto-recovery",
                    now="2026-09-04T00:07:00.000Z",
                    manual_profiles=(),
                    candidate_final_status="auto-promoted",
                )
                self.assertEqual("applied", recovered.status)
                self.assertEqual(before, target.read_bytes())
                promoted = store.load_workflow_candidate(candidate.candidate_id)
                self.assertIsNotNone(promoted)
                self.assertEqual("auto-promoted", promoted.status)

    def test_manual_profile_conflict_suppresses_without_write_or_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture, _, candidate = prepare_automatic_candidate(root)
            write_conflicting_manual_profile(root)

            result = fixture.service.promote_eligible_candidates(
                MemoryScope.PERSONAL,
                actor_id="developer",
                session_id="session-m3b",
                idempotency_key="promote-conflict",
                correlation_id="corr-promote-conflict",
                now="2026-09-04T00:10:00.000Z",
            )
            self.assertEqual(0, result.promoted_count)
            self.assertEqual(1, result.suppressed_count)
            self.assertEqual("suppressed", result.notifications[0].status)
            self.assertEqual(
                ("candidate-conflict", "candidate-suppressed"),
                result.notifications[0].reason_codes,
            )
            self.assertFalse(managed_personal_profile_path(root).exists())

            store = MemoryStore.open_if_enabled(root, fixture.effective_policy())
            assert store is not None
            with store:
                suppressed = store.load_workflow_candidate(candidate.candidate_id)
                self.assertIsNotNone(suppressed)
                self.assertEqual("suppressed", suppressed.status)
                self.assertTrue(
                    store.is_candidate_suppressed(
                        candidate.pattern_id,
                        candidate.material_evidence_digest,
                        "2026-09-05T00:00:00.000Z",
                    )
                )
                self.assertEqual(
                    0,
                    int(
                        store._require_open()
                        .execute("SELECT COUNT(*) FROM profile_update_proposals")
                        .fetchone()[0]
                    ),
                )
                self.assertEqual(
                    0,
                    int(
                        store._require_open()
                        .execute("SELECT COUNT(*) FROM profile_revisions")
                        .fetchone()[0]
                    ),
                )


if __name__ == "__main__":
    unittest.main()
