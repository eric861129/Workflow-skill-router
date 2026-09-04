from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from workflow_skill_router.memory import (
    CompletedWorkflowReader,
    MatcherSeed,
    MemoryPolicyRepository,
    MemoryRequestContext,
    ObservationEligibility,
    RouteObservationError,
    build_route_observation,
    decode_route_observation,
    evaluate_observation_eligibility,
    resolve_effective_policy,
)
from workflow_skill_router.memory.store import MemoryPolicySnapshot
from workflow_skill_router.service_models import RequestContext

from memory.workflow_fixture import WorkflowFixture, write_personal_memory_policy


class RouteObservationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.database = self.root / "router-v2.sqlite3"
        self.context = RequestContext("session-observation", "developer", "runtime-policy-1")
        self.fixture = WorkflowFixture(self.database, self.context)
        plan = self.fixture.plan_single(key="observation")
        self.fixture.complete(plan)
        self.completed = CompletedWorkflowReader(self.database).read(
            MemoryRequestContext(
                self.context.session_id,
                self.context.actor,
                self.context.runtime_policy_snapshot_id,
            ),
            plan.workflow_run_id,
        )
        write_personal_memory_policy(self.root, "reviewed")
        repository = MemoryPolicyRepository(self.root)
        self.effective = resolve_effective_policy(
            personal=repository.inspect_personal(),
            workspace=None,
        )
        self.policy_snapshot = MemoryPolicySnapshot.from_effective_policy(self.effective)
        self.seed = MatcherSeed(("student api",), ("api",), ("backend",), "user-explicit")

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_matcher_seed_is_normalized_and_strict(self) -> None:
        seed = MatcherSeed(
            (" Student API ",),
            ("API",),
            ("Backend",),
            "user-explicit",
        )
        self.assertEqual(("student api",), seed.objective_keywords)
        self.assertEqual(("api",), seed.domains)
        self.assertEqual(("backend",), seed.tags)
        with self.assertRaisesRegex(RouteObservationError, "duplicate-matcher-value"):
            MatcherSeed(("api", " API "), (), (), "user-explicit")
        with self.assertRaisesRegex(RouteObservationError, "invalid-matcher-source"):
            MatcherSeed((), ("api",), (), "model-inferred")
        with self.assertRaisesRegex(RouteObservationError, "sensitive-matcher-value"):
            MatcherSeed(("/private/project",), (), (), "user-explicit")
        with self.assertRaisesRegex(RouteObservationError, "invalid-matcher-identifier"):
            MatcherSeed((), ("api domain",), (), "trusted-routing-context")

    def test_route_observation_round_trips_without_sensitive_content(self) -> None:
        observation = build_route_observation(
            self.completed,
            self.seed,
            self.policy_snapshot,
            target_profile_class="managed-personal",
            risk_class="r1",
            side_effect_outcome="none",
            observed_at="2026-09-04T01:00:00.000Z",
        )

        replay = decode_route_observation(observation.to_dict())

        self.assertEqual(observation, replay)
        self.assertRegex(observation.observation_digest, r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(observation.route_signature_digest, r"^sha256:[0-9a-f]{64}$")
        serialized = observation.canonical_json()
        for forbidden in (
            "confidential student",
            "/private/project",
            "sensitive reported outcome",
            "raw_prompt",
            "tool_arguments",
            "file_content",
            "secrets",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual("unverified", observation.activation_status)
        self.assertFalse(observation.automatic_promotion_eligible)

    def test_tampered_observation_is_rejected(self) -> None:
        observation = build_route_observation(
            self.completed,
            self.seed,
            self.policy_snapshot,
            target_profile_class="managed-personal",
            risk_class="r1",
            side_effect_outcome="none",
            observed_at="2026-09-04T01:00:00.000Z",
        )
        document = observation.to_dict()
        document["risk_class"] = "r2"
        with self.assertRaisesRegex(RouteObservationError, "observation-digest-mismatch"):
            decode_route_observation(document)

    def test_eligibility_applies_mode_risk_side_effect_consent_and_matcher_rules(self) -> None:
        accepted = evaluate_observation_eligibility(
            self.completed,
            self.effective,
            self.seed,
            target_profile_class="managed-personal",
            risk_class="r1",
            side_effect_outcome="none",
            one_shot="none",
        )
        self.assertEqual(ObservationEligibility(True, ()), accepted)

        cases = (
            ({"risk_class": "r3"}, "risk-excluded"),
            ({"side_effect_outcome": "unknown"}, "side-effect-unknown"),
            ({"side_effect_outcome": "known-failure"}, "side-effect-failed"),
            ({"matcher_seed": None}, "insufficient-match-signal"),
            ({"one_shot": "no-memory"}, "explicit-no-memory"),
            ({"target_profile_class": "workspace-file"}, "target-not-allowed"),
        )
        defaults = {
            "matcher_seed": self.seed,
            "target_profile_class": "managed-personal",
            "risk_class": "r1",
            "side_effect_outcome": "none",
            "one_shot": "none",
        }
        for changes, reason in cases:
            values = {**defaults, **changes}
            with self.subTest(reason=reason):
                result = evaluate_observation_eligibility(
                    self.completed,
                    self.effective,
                    values["matcher_seed"],
                    target_profile_class=values["target_profile_class"],
                    risk_class=values["risk_class"],
                    side_effect_outcome=values["side_effect_outcome"],
                    one_shot=values["one_shot"],
                )
                self.assertFalse(result.eligible)
                self.assertIn(reason, result.reason_codes)

        pending = replace(self.completed, pending_consent=True)
        result = evaluate_observation_eligibility(
            pending,
            self.effective,
            self.seed,
            target_profile_class="managed-personal",
            risk_class="r1",
            side_effect_outcome="none",
            one_shot="none",
        )
        self.assertIn("pending-consent", result.reason_codes)


if __name__ == "__main__":
    unittest.main()
