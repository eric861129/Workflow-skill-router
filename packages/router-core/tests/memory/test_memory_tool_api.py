from __future__ import annotations

from contextlib import closing
from unittest.mock import patch
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from workflow_skill_router.local_control import LocalControlPlaneService
from workflow_skill_router.memory import MemoryScope, MemoryStore
from workflow_skill_router.runtime_readiness import CapabilityUnavailable
from workflow_skill_router.tool_dispatch import ToolDispatcher
from memory.m1c_fixture import M1CHistoryFixture, write_feedback_policy
from bridge.test_memory_tool_contracts import SAMPLES


class MemoryToolApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = M1CHistoryFixture(self.root)
        self.local = LocalControlPlaneService(self.fixture.database)
        self.dispatcher = ToolDispatcher(self.local)

    def call(self, name, **values):
        self.assertIn(name, type(self.local).__dict__, "M4-A local Memory delegation is missing")
        args = {**SAMPLES[name], "context": asdict(self.fixture.context), **values}
        return self.dispatcher.dispatch(name, args)

    def seed(self, target="managed-personal"):
        dates = tuple((datetime.now(timezone.utc) - timedelta(days=n)).isoformat(timespec="milliseconds").replace("+00:00", "Z") for n in (2, 1))
        self.fixture.insert_observations(count=3, dates=dates, target_profile_class=target)
        return self.fixture.service.rebuild_candidates(MemoryScope.PERSONAL, now=datetime.now(timezone.utc))[0]

    def db_state(self):
        database = self.root / "memory/workflow-memory.sqlite3"
        if not database.exists():
            return None
        with closing(sqlite3.connect(database)) as connection:
            return "\n".join(connection.iterdump())

    def approve(self, view, **changes):
        return self.call("transition_profile_update", proposal_id=view["proposal_id"], expected_proposal_digest=view["proposal_digest"], expected_profile_digest=view["expected_profile_digest"], expected_state_version=view["state_version"], **changes)

    def test_status_and_disabled_remember_do_not_create_optional_state(self):
        (self.root / "config/workflow-memory.json").unlink()
        status = self.call("get_memory_status")
        self.assertEqual("disabled", status["effective_mode"])
        self.assertFalse(status["memory_store_exists"])
        result = self.call("remember_workflow")
        self.assertEqual("memory-disabled", result["status"])
        self.assertFalse((self.root / "memory").exists())
        self.assertFalse((self.root / "profiles").exists())

    def test_status_list_and_preview_are_logically_read_only(self):
        candidate = self.seed()
        before = self.db_state()
        status = self.call("get_memory_status")
        listed = self.call("list_workflow_candidates")
        preview = self.call("preview_profile_update", candidate_id=candidate.candidate_id)
        self.assertEqual(3, status["eligible_workflow_count"])
        self.assertEqual("unavailable", status["actual_skill_consistency"])
        self.assertEqual(candidate.candidate_id, listed["candidates"][0]["candidate_id"])
        self.assertEqual("previewed", preview["status"])
        self.assertEqual(before, self.db_state())
        self.assertFalse((self.root / "profiles").exists())
        text = json.dumps((status, listed, preview))
        self.assertNotIn(str(self.root), text)
        self.assertNotIn("raw_prompt", text)

    def test_approve_materializes_exact_preview_and_replays_once(self):
        candidate = self.seed()
        view = self.call("preview_profile_update", candidate_id=candidate.candidate_id)["proposal"]
        first = self.approve(view)
        self.assertEqual("applied", first["status"])
        path = self.root / "profiles/managed/personal/adaptive-memory.json"
        before = path.read_bytes()
        replay = self.approve(view)
        self.assertTrue(replay["replayed"])
        self.assertEqual(first["revision_id"], replay["revision_id"])
        self.assertEqual(before, path.read_bytes())
        changed = self.approve(view, correlation_id="different-correlation")
        self.assertEqual("blocked", changed["status"])
        self.assertEqual(before, path.read_bytes())

    def test_profile_drift_after_preview_blocks_without_overwriting(self):
        candidate = self.seed()
        view = self.call("preview_profile_update", candidate_id=candidate.candidate_id)["proposal"]
        path = self.root / "profiles/managed/personal/adaptive-memory.json"
        path.parent.mkdir(parents=True)
        document = json.loads(view["proposed_profile_json"])
        document["rules"][0]["priority"] += 1
        path.write_text(json.dumps(document), encoding="utf-8")
        before = path.read_bytes()
        result = self.approve(view)
        self.assertEqual("blocked", result["status"])
        self.assertEqual(before, path.read_bytes())

    def test_policy_downgrade_after_preview_does_not_create_proposal(self):
        candidate = self.seed()
        view = self.call("preview_profile_update", candidate_id=candidate.candidate_id)["proposal"]
        write_feedback_policy(self.root, mode="observe")
        before = self.db_state()
        result = self.approve(view)
        self.assertEqual("blocked", result["status"])
        self.assertEqual(before, self.db_state())

    def test_reject_does_not_write_profile(self):
        candidate = self.seed()
        view = self.call("preview_profile_update", candidate_id=candidate.candidate_id)["proposal"]
        result = self.approve(view, action="reject")
        self.assertEqual("rejected", result["status"])
        self.assertIsNone(result["revision_id"])
        self.assertFalse((self.root / "profiles").exists())

    def test_purge_is_available_after_capture_is_disabled(self):
        self.seed()
        write_feedback_policy(self.root, mode="disabled")
        status = self.call("get_memory_status")
        self.assertEqual(3, status["eligible_workflow_count"])
        result = self.call("purge_workflow_memory", expected_summary_digest=status["history_summary_digest"])
        self.assertEqual("purged", result["status"])
        self.assertEqual(3, result["deleted_observations"])
        self.assertEqual(0, self.call("get_memory_status")["eligible_workflow_count"])

    def test_unsupported_purge_scopes_do_not_claim_success_or_delete_history(self):
        self.seed()
        status = self.call("get_memory_status")
        result = self.call("purge_workflow_memory", scope="managed-profiles-only", expected_summary_digest=status["history_summary_digest"])
        self.assertEqual("scope-not-available", result["status"])
        self.assertEqual(0, result["deleted_observations"])
        self.assertEqual(3, self.call("get_memory_status")["eligible_workflow_count"])

    def test_rollback_creates_reviewable_proposal_not_silent_write(self):
        candidate = self.seed()
        view = self.call("preview_profile_update", candidate_id=candidate.candidate_id)["proposal"]
        applied = self.approve(view)
        path = self.root / "profiles/managed/personal/adaptive-memory.json"
        before = path.read_bytes()
        result = self.call("rollback_profile_revision", source_revision_id=applied["revision_id"], expected_profile_digest=view["proposed_profile_digest"], idempotency_key="rollback-test")
        self.assertEqual("pending", result["status"])
        self.assertEqual(before, path.read_bytes())
        replay = self.call("rollback_profile_revision", source_revision_id=applied["revision_id"], expected_profile_digest=view["proposed_profile_digest"], idempotency_key="rollback-test")
        self.assertTrue(replay["replayed"])
        self.assertEqual(result["proposal"]["proposal_id"], replay["proposal"]["proposal_id"])

    def workspace_seed(self, target="managed-workspace-local"):
        from workflow_skill_router.memory.managed_profiles import verify_workspace_root
        root = self.root / "workspace"
        root.mkdir()
        write_feedback_policy(self.root, promotion_target=target)
        digest = verify_workspace_root(root).digest
        dates = tuple((datetime.now(timezone.utc) - timedelta(days=n)).isoformat(timespec="milliseconds").replace("+00:00", "Z") for n in (2, 1))
        self.fixture.insert_observations(count=3, dates=dates, workspaces=(digest,) * 3, target_profile_class=target)
        candidate = self.fixture.service.rebuild_candidates(MemoryScope.WORKSPACE, now=datetime.now(timezone.utc))[0]
        return root, candidate

    def test_workspace_candidate_is_isolated_and_materialized_only_locally(self):
        from workflow_skill_router.memory.managed_profiles import managed_workspace_profile_path
        root, candidate = self.workspace_seed()
        self.assertEqual([], self.call("list_workflow_candidates")["candidates"])
        listed = self.call("list_workflow_candidates", workspace_root=str(root))
        self.assertEqual(candidate.candidate_id, listed["candidates"][0]["candidate_id"])
        view = self.call("preview_profile_update", candidate_id=candidate.candidate_id, workspace_root=str(root))
        self.assertEqual("previewed", view["status"])
        other = self.root / "other"
        other.mkdir()
        denied = self.approve(view["proposal"], workspace_root=str(other))
        self.assertEqual("blocked", denied["status"])
        applied = self.approve(view["proposal"], workspace_root=str(root))
        self.assertEqual("applied", applied["status"])
        self.assertTrue(managed_workspace_profile_path(self.root, candidate.workspace_identity_digest).is_file())
        self.assertFalse((root / ".codex/workflow-skill-router.json").exists())

    def test_workspace_file_preview_does_not_grant_host_write_authority(self):
        root, candidate = self.workspace_seed("workspace-file")
        before = self.db_state()
        preview = self.call("preview_profile_update", candidate_id=candidate.candidate_id, workspace_root=str(root))
        self.assertEqual("previewed", preview["status"])
        with self.assertRaises(CapabilityUnavailable):
            self.approve(preview["proposal"], workspace_root=str(root))
        self.assertEqual(before, self.db_state())
        self.assertFalse((root / ".codex/workflow-skill-router.json").exists())

    def test_user_personal_profile_identity_cannot_redirect_write(self):
        write_feedback_policy(self.root, promotion_target="user-personal")
        candidate = self.seed("user-personal")
        preview = self.call("preview_profile_update", candidate_id=candidate.candidate_id)
        document = json.loads(preview["proposal"]["proposed_profile_json"])
        document["profile_id"] = "personal:another-file"
        path = self.root / "profiles/personal/adaptive-memory.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(document), encoding="utf-8")
        preview = self.call("preview_profile_update", candidate_id=candidate.candidate_id)
        self.assertEqual("blocked", preview["status"])
        self.assertFalse((path.parent / "another-file.json").exists())

    def test_rollback_of_old_revision_receives_fresh_review_window(self):
        candidate = self.seed()
        view = self.call("preview_profile_update", candidate_id=candidate.candidate_id)["proposal"]
        old = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        with patch("workflow_skill_router.memory.tool_api._now", return_value=old):
            applied = self.approve(view)
        result = self.call("rollback_profile_revision", source_revision_id=applied["revision_id"], expected_profile_digest=view["proposed_profile_digest"], idempotency_key="rollback-old")
        self.assertEqual("pending", result["status"])
        expires = datetime.fromisoformat(result["proposal"]["expires_at"].replace("Z", "+00:00"))
        self.assertGreater(expires, datetime.now(timezone.utc))
        final = self.approve(result["proposal"], idempotency_key="apply-rollback-old")
        self.assertEqual("applied", final["status"])

    def test_reject_suppresses_candidate_without_new_evidence(self):
        candidate = self.seed()
        view = self.call("preview_profile_update", candidate_id=candidate.candidate_id)["proposal"]
        result = self.approve(view, action="reject")
        self.assertEqual("rejected", result["status"])
        self.assertEqual("rejected", self.call("list_workflow_candidates")["candidates"][0]["status"])
        self.assertEqual((), self.fixture.service.rebuild_candidates(MemoryScope.PERSONAL))

    def test_feedback_change_invalidates_unpersisted_preview(self):
        from workflow_skill_router.memory.feedback import RouteFeedback
        candidate = self.seed()
        view = self.call("preview_profile_update", candidate_id=candidate.candidate_id)["proposal"]
        with self.fixture.service.open_store_for_current_policy() as store:
            observation = store.list_route_observations()[0]
            feedback = RouteFeedback.create(
                observation=observation, policy_snapshot=store.current_policy_snapshot,
                context=self.fixture.memory_context, feedback_type="gate-failed", reason_code="gate-failed",
                correction_dimensions=(), original_route_digest=None, corrected_route_digest=None, free_text=None,
                recorded_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            )
            store.record_route_feedback(feedback_document=feedback.to_dict(), result_document={}, idempotency_key="new-feedback", command_digest="sha256:" + "f" * 64)
        result = self.approve(view)
        self.assertEqual("blocked", result["status"])
        self.assertFalse((self.root / "profiles").exists())

    def test_interrupted_final_receipt_replays_materialization_without_another_revision(self):
        candidate = self.seed()
        view = self.call("preview_profile_update", candidate_id=candidate.candidate_id)["proposal"]
        with patch.object(self.local._memory_tools, "_save_receipt", side_effect=sqlite3.OperationalError("fixture failure")):
            result = self.approve(view)
        self.assertEqual("blocked", result["status"])
        path = self.root / "profiles/managed/personal/adaptive-memory.json"
        before = path.read_bytes()
        result = self.approve(view)
        self.assertEqual("applied", result["status"])
        self.assertEqual(before, path.read_bytes())
        with self.fixture.service.open_store_for_current_policy() as store:
            self.assertEqual(1, store._require_open().execute("SELECT COUNT(*) FROM profile_revisions").fetchone()[0])

    def test_automatic_revision_can_be_rolled_back_through_explicit_review(self):
        from memory.test_automatic_promotion import prepare_automatic_candidate
        fixture, policy, candidate = prepare_automatic_candidate(self.root)
        result = fixture.service.promote_eligible_candidates(
            scope=MemoryScope.PERSONAL, actor_id="developer", session_id="session-m1c",
            idempotency_key="automatic-for-rollback", correlation_id="auto-rollback",
            now="2026-09-04T00:01:00.000Z",
        )
        notification = result.notifications[0]
        rollback = self.call("rollback_profile_revision", source_revision_id=notification.revision_id,
            expected_profile_digest=notification.new_profile_digest, idempotency_key="rollback-automatic")
        self.assertEqual("pending", rollback["status"])
        applied = self.approve(rollback["proposal"], idempotency_key="apply-automatic-rollback")
        self.assertEqual("applied", applied["status"])
