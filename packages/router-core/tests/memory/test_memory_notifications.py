from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from workflow_skill_router.memory import (
    AutomaticPromotionNotification,
    AutomaticPromotionResult,
    MemoryScope,
)

from memory.m1c_fixture import M1CHistoryFixture, write_feedback_policy


class MemoryNotificationTests(unittest.TestCase):
    def test_notification_contract_is_strict_and_public_safe(self) -> None:
        digest = "sha256:" + "a" * 64
        notification = AutomaticPromotionNotification(
            status="promoted",
            candidate_id="candidate:" + "b" * 32,
            candidate_digest=digest,
            policy_digest=digest,
            target_profile_class="managed-personal",
            proposal_id="proposal:" + "c" * 32,
            proposal_digest=digest,
            revision_id="revision:" + "d" * 32,
            revision_digest=digest,
            new_profile_digest=digest,
            reason_codes=("automatic-promotion-applied",),
        )
        document = notification.to_dict()
        self.assertEqual(
            {
                "status",
                "candidate_id",
                "candidate_digest",
                "policy_digest",
                "target_profile_class",
                "proposal_id",
                "proposal_digest",
                "revision_id",
                "revision_digest",
                "new_profile_digest",
                "reason_codes",
            },
            set(document),
        )
        serialized = json.dumps(document, sort_keys=True)
        for forbidden in (
            "/private/",
            "workspace_root",
            "raw_prompt",
            "objective_keywords",
            "skill_tree",
            "proposed_profile",
        ):
            self.assertNotIn(forbidden, serialized)

        with self.assertRaisesRegex(ValueError, "invalid-automatic-promotion-candidate-id"):
            AutomaticPromotionNotification(
                status="blocked",
                candidate_id="/private/candidate",
                candidate_digest=digest,
                policy_digest=digest,
                target_profile_class="managed-personal",
                proposal_id=None,
                proposal_digest=None,
                revision_id=None,
                revision_digest=None,
                new_profile_digest=None,
                reason_codes=("candidate-conflict",),
            )

    def test_notification_and_result_decoders_reject_coercion(self) -> None:
        digest = "sha256:" + "a" * 64
        notification = AutomaticPromotionNotification(
            status="blocked",
            candidate_id="candidate:" + "b" * 32,
            candidate_digest=digest,
            policy_digest=digest,
            target_profile_class="managed-personal",
            proposal_id=None,
            proposal_digest=None,
            revision_id=None,
            revision_digest=None,
            new_profile_digest=None,
            reason_codes=("candidate-conflict",),
        ).to_dict()
        malformed_notifications = (
            {**notification, "candidate_id": 1},
            {**notification, "reason_codes": [1]},
            {**notification, "unexpected": True},
        )
        for malformed in malformed_notifications:
            with self.subTest(malformed=malformed):
                with self.assertRaises(ValueError):
                    AutomaticPromotionNotification.from_dict(malformed)

        result = AutomaticPromotionResult(
            status="completed",
            scope=MemoryScope.PERSONAL,
            promoted_count=0,
            suppressed_count=0,
            skipped_count=1,
            notifications=(AutomaticPromotionNotification.from_dict(notification),),
        ).to_dict()
        malformed_results = (
            {**result, "promoted_count": True},
            {**result, "notifications": [1]},
            {**result, "reason_codes": [1]},
            {**result, "replayed": 1},
        )
        for malformed in malformed_results:
            with self.subTest(malformed=malformed):
                with self.assertRaises((TypeError, ValueError)):
                    AutomaticPromotionResult.from_dict(malformed)

    def test_cli_promote_eligible_is_explicit_local_and_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = M1CHistoryFixture(root)
            write_feedback_policy(root, mode="automatic")
            fixture.insert_observations(
                count=5,
                dates=(
                    "2026-09-01T10:00:00.000Z",
                    "2026-09-02T10:00:00.000Z",
                    "2026-09-03T10:00:00.000Z",
                ),
                route_sources=("builtin",) * 5,
                matcher_source="trusted-routing-context",
            )
            fixture.service.rebuild_candidates(MemoryScope.PERSONAL)

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "workflow_skill_router.cli",
                    "memory",
                    "candidates",
                    "promote-eligible",
                    "--database",
                    str(fixture.database),
                    "--data-dir",
                    str(root),
                    "--scope",
                    "personal",
                    "--actor",
                    "developer",
                    "--session-id",
                    "session-m3b-cli",
                    "--idempotency-key",
                    "promote-cli",
                    "--correlation-id",
                    "corr-promote-cli",
                    "--now",
                    "2026-09-04T00:10:00.000Z",
                ],
                cwd=Path(__file__).resolve().parents[4],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, process.returncode, process.stderr)
            payload = json.loads(process.stdout)
            self.assertEqual("completed", payload["status"])
            self.assertEqual("explicit-local", payload["operation_mode"])
            self.assertEqual("router-local", payload["authority_mode"])
            self.assertEqual(1, payload["promoted_count"])
            output = process.stdout
            self.assertNotIn(str(root), output)
            self.assertNotIn("background", output)
            self.assertNotIn("scheduler", output)
            self.assertNotIn("objective_keywords", output)
            self.assertNotIn("skill_tree", output)


if __name__ == "__main__":
    unittest.main()
