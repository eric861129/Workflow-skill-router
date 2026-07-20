from __future__ import annotations

from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.profiles.contract import decode_routing_profile
from workflow_skill_router.profiles.resolver import RoutingMatchContext, resolve_profile_route

from .test_contract import profile_document


class RoutingProfileResolverTests(unittest.TestCase):
    def test_workspace_profile_wins_as_one_complete_tree_without_deep_merge(self) -> None:
        personal_document = profile_document(scope="personal")
        workspace_document = profile_document(scope="workspace")
        workspace_document["profile_id"] = "workspace:kcis-api"
        workspace_document["rules"][0]["route"]["skill_tree"][0]["primary_skill_id"] = (
            "skill:kcislk-apicenter-core"
        )

        result = resolve_profile_route(
            (
                decode_routing_profile(personal_document),
                decode_routing_profile(workspace_document),
            ),
            objective="Deliver an OpenAPI contract for the API",
            default_work_mode="phased",
            context=RoutingMatchContext(domains=("api",), tags=("delivery",)),
        )

        self.assertIsNotNone(result)
        self.assertEqual("workspace-profile", result.route_source)
        self.assertEqual("workspace:kcis-api", result.profile_id)
        self.assertEqual("skill:kcislk-apicenter-core", result.skill_tree[0].primary_skill_id)
        self.assertNotIn("personal:api-delivery", result.applied_profile_ids)

    def test_current_phase_exposes_only_current_primary_and_support(self) -> None:
        result = resolve_profile_route(
            (decode_routing_profile(profile_document()),),
            objective="API delivery",
            default_work_mode="phased",
            context=RoutingMatchContext(
                domains=("api",),
                tags=("delivery",),
                current_phase_id="verification",
            ),
        )

        self.assertEqual("verification", result.current_phase.phase_id)
        self.assertEqual(
            ("skill:qa-test-planner", "skill:playwright"),
            result.current_skill_ids,
        )

    def test_declared_unknown_skill_remains_intended_instead_of_falling_back(self) -> None:
        document = profile_document()
        document["rules"][0]["route"]["skill_tree"][0]["primary_skill_id"] = (
            "skill:not-installed-yet"
        )

        result = resolve_profile_route(
            (decode_routing_profile(document),),
            objective="API delivery",
            default_work_mode="phased",
            context=RoutingMatchContext(domains=("api",), tags=("delivery",)),
        )

        self.assertEqual("skill:not-installed-yet", result.current_phase.primary_skill_id)
        self.assertEqual("intended-unverified", result.activation_status)

    def test_resolution_is_deterministic_by_scope_priority_rule_priority_and_id(self) -> None:
        lower = profile_document()
        lower["profile_id"] = "personal:z-last"
        lower["rules"][0]["priority"] = 10
        higher = profile_document()
        higher["profile_id"] = "personal:a-first"
        higher["rules"][0]["priority"] = 20

        forward = resolve_profile_route(
            (decode_routing_profile(lower), decode_routing_profile(higher)),
            objective="API delivery",
            default_work_mode="phased",
            context=RoutingMatchContext(domains=("api",), tags=("delivery",)),
        )
        reverse = resolve_profile_route(
            (decode_routing_profile(higher), decode_routing_profile(lower)),
            objective="API delivery",
            default_work_mode="phased",
            context=RoutingMatchContext(domains=("api",), tags=("delivery",)),
        )

        self.assertEqual("personal:a-first", forward.profile_id)
        self.assertEqual(forward, reverse)


if __name__ == "__main__":
    unittest.main()
