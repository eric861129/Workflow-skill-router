from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.local_control import LocalControlPlaneService
from workflow_skill_router.persistence.sqlite_store import (
    ConcurrencyConflict,
    IdempotencyConflict,
)
from workflow_skill_router.routing.consent import ConsentPolicyError
from workflow_skill_router.service_models import (
    PlanWork,
    ProposeSupportConsent,
    RequestContext,
    TransitionSupportConsent,
)


class LocalConsentControlPlaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.database = Path(self.directory.name) / "router.db"
        self.service = LocalControlPlaneService(self.database)
        self.context = RequestContext("session-1", "developer", "policy-1")
        self.plan = self.service.plan_work(PlanWork(
            context=self.context,
            objective="使用指定 API SKILL 完成目前 Phase",
            goal_binding_id=None,
            requested_work_mode="phased",
            explicit_skill_ids=("skill:api-designer",),
            explicit_semantics="use",
            expected_state_version=0,
            idempotency_key="plan-1",
            correlation_id="correlation-plan",
        ))

    def tearDown(self) -> None:
        self.directory.cleanup()

    def proposal_command(
        self,
        *,
        support_skill_ids: tuple[str, ...] = ("skill:qa-test-planner",),
        idempotency_key: str = "proposal-1",
    ) -> ProposeSupportConsent:
        return ProposeSupportConsent(
            context=self.context,
            workflow_run_id=self.plan.workflow_run_id,
            phase_id="phase-contract-verification",
            scope_anchor_id="scope:phase-contract-verification",
            goal_revision=None,
            plan_revision=1,
            primary_skill_id="skill:api-designer",
            support_skill_ids=support_skill_ids,
            context_fingerprint="sha256:" + "a" * 64,
            expected_state_version=1,
            idempotency_key=idempotency_key,
            correlation_id="correlation-proposal",
        )

    def transition_command(
        self,
        proposal_id: str,
        *,
        action: str = "approve",
        phase_id: str = "phase-contract-verification",
        scope_anchor_id: str = "scope:phase-contract-verification",
        goal_revision: int | None = None,
        plan_revision: int = 1,
        context_fingerprint: str = "sha256:" + "a" * 64,
        idempotency_key: str = "transition-1",
    ) -> TransitionSupportConsent:
        return TransitionSupportConsent(
            context=self.context,
            proposal_id=proposal_id,
            action=action,
            current_phase_id=phase_id,
            current_scope_anchor_id=scope_anchor_id,
            current_goal_revision=goal_revision,
            current_plan_revision=plan_revision,
            current_context_fingerprint=context_fingerprint,
            expected_state_version=1,
            idempotency_key=idempotency_key,
            correlation_id="correlation-transition",
        )

    def test_approval_preserves_bound_route_and_complete_support_set(self) -> None:
        proposed = self.service.propose_support_consent(self.proposal_command(
            support_skill_ids=("skill:qa-test-planner", "skill:playwright"),
        ))

        approved = self.service.transition_support_consent(
            self.transition_command(proposed.proposal_id)
        )

        self.assertEqual("approved", approved.status)
        self.assertEqual("phased", approved.routing_envelope)
        self.assertEqual("explicit-locked", approved.selection_mode)
        self.assertEqual("skill:api-designer", approved.primary_skill)
        self.assertEqual(
            ("skill:playwright", "skill:qa-test-planner"),
            approved.support_skills,
        )
        self.assertEqual("approved", approved.consent_action)
        self.assertEqual("none", approved.goal_relation)
        self.assertEqual(2, approved.state_version)
        self.assertFalse(approved.replayed)

    def test_rejection_clears_active_support_but_preserves_primary(self) -> None:
        proposed = self.service.propose_support_consent(self.proposal_command())

        rejected = self.service.transition_support_consent(
            self.transition_command(proposed.proposal_id, action="reject")
        )

        self.assertEqual("rejected", rejected.status)
        self.assertEqual("skill:api-designer", rejected.primary_skill)
        self.assertEqual((), rejected.support_skills)
        self.assertEqual("rejected", rejected.consent_action)

    def test_transition_fails_closed_when_phase_scope_revision_or_context_drifts(self) -> None:
        mismatches = (
            {"phase_id": "phase-other"},
            {"scope_anchor_id": "scope:phase-other"},
            {"goal_revision": 2},
            {"plan_revision": 2},
            {"context_fingerprint": "sha256:" + "b" * 64},
        )
        for index, mismatch in enumerate(mismatches):
            with self.subTest(mismatch=mismatch):
                proposal_context = "sha256:" + chr(ord("a") + index) * 64
                proposed = self.service.propose_support_consent(
                    replace(
                        self.proposal_command(idempotency_key=f"proposal-{index + 2}"),
                        context_fingerprint=proposal_context,
                    )
                )
                transition_values = {"context_fingerprint": proposal_context, **mismatch}
                with self.assertRaises(ConcurrencyConflict):
                    self.service.transition_support_consent(self.transition_command(
                        proposed.proposal_id,
                        idempotency_key=f"transition-{index + 2}",
                        **transition_values,
                    ))

    def test_transition_is_idempotent_and_conflicting_replay_is_rejected(self) -> None:
        proposed = self.service.propose_support_consent(self.proposal_command())
        command = self.transition_command(proposed.proposal_id)

        first = self.service.transition_support_consent(command)
        replay = self.service.transition_support_consent(command)

        self.assertFalse(first.replayed)
        self.assertTrue(replay.replayed)
        with self.assertRaises(IdempotencyConflict):
            self.service.transition_support_consent(self.transition_command(
                proposed.proposal_id,
                action="reject",
            ))

    def test_support_proposal_requires_explicit_use_plan_and_current_phase_scope(self) -> None:
        automatic = self.service.plan_work(PlanWork(
            context=self.context,
            objective="自動選擇 SKILL",
            goal_binding_id=None,
            requested_work_mode="single",
            explicit_skill_ids=(),
            explicit_semantics=None,
            expected_state_version=0,
            idempotency_key="plan-auto",
            correlation_id="correlation-auto",
        ))
        command = self.proposal_command()
        command = ProposeSupportConsent(
            context=command.context,
            workflow_run_id=automatic.workflow_run_id,
            phase_id=command.phase_id,
            scope_anchor_id=command.scope_anchor_id,
            goal_revision=command.goal_revision,
            plan_revision=command.plan_revision,
            primary_skill_id=command.primary_skill_id,
            support_skill_ids=command.support_skill_ids,
            context_fingerprint=command.context_fingerprint,
            expected_state_version=command.expected_state_version,
            idempotency_key="proposal-auto",
            correlation_id=command.correlation_id,
        )

        with self.assertRaises(ConsentPolicyError):
            self.service.propose_support_consent(command)

    def test_support_set_is_nonempty_distinct_and_limited_to_three(self) -> None:
        invalid_sets = (
            (),
            ("skill:qa-test-planner", "skill:qa-test-planner"),
            ("skill:a", "skill:b", "skill:c", "skill:d"),
            ("skill:api-designer",),
        )
        for index, support_set in enumerate(invalid_sets):
            with self.subTest(support_set=support_set):
                with self.assertRaises(ConsentPolicyError):
                    self.service.propose_support_consent(self.proposal_command(
                        support_skill_ids=support_set,
                        idempotency_key=f"proposal-invalid-{index}",
                    ))

    def test_rejected_proposal_cannot_be_reasked_after_cosmetic_phase_rename(self) -> None:
        proposed = self.service.propose_support_consent(self.proposal_command())
        self.service.transition_support_consent(
            self.transition_command(proposed.proposal_id, action="reject")
        )

        renamed = replace(
            self.proposal_command(idempotency_key="proposal-renamed"),
            phase_id="phase-renamed-only",
        )
        with self.assertRaisesRegex(ConsentPolicyError, "不得重複提案"):
            self.service.propose_support_consent(renamed)

        changed_context = replace(
            renamed,
            context_fingerprint="sha256:" + "b" * 64,
            idempotency_key="proposal-material-change",
        )
        reproposed = self.service.propose_support_consent(changed_context)
        self.assertEqual("proposal-required", reproposed.status)

    def test_local_plan_revision_is_fixed_and_cannot_be_forged_in_proposal(self) -> None:
        with self.assertRaises(ConcurrencyConflict):
            self.service.propose_support_consent(replace(
                self.proposal_command(),
                plan_revision=2,
            ))

    def test_context_fingerprint_requires_a_complete_sha256_digest(self) -> None:
        for index, fingerprint in enumerate(("sha256:", "sha256:xyz", "md5:" + "a" * 32)):
            with self.subTest(fingerprint=fingerprint):
                with self.assertRaisesRegex(ConsentPolicyError, "fingerprint"):
                    self.service.propose_support_consent(replace(
                        self.proposal_command(
                            idempotency_key=f"proposal-invalid-fingerprint-{index}"
                        ),
                        context_fingerprint=fingerprint,
                    ))


if __name__ == "__main__":
    unittest.main()
