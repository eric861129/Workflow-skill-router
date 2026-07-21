from __future__ import annotations

from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.profiles.contract import decode_routing_profile
from workflow_skill_router.profiles.resolver import (
    RoutingMatchContext,
    explain_profile_route,
    lint_profile,
    resolve_profile_route,
)

if __package__:
    from .test_contract import profile_document
else:
    from test_contract import profile_document


class RoutingProfileResolverTests(unittest.TestCase):
    def test_explain_returns_public_safe_trace_for_every_candidate_rule(self) -> None:
        document = profile_document()
        document["rules"][0]["match"] = {
            "objective_keywords": ["應用程式介面"],
            "domains": [],
            "tags": [],
            "work_modes": ["phased"],
        }
        matched_rule = profile_document()["rules"][0]
        matched_rule["rule_id"] = "backend-api"
        matched_rule["match"] = {
            "objective_keywords": ["api"],
            "domains": [],
            "tags": [],
            "work_modes": ["phased"],
        }
        document["rules"].append(matched_rule)

        traces = explain_profile_route(
            (decode_routing_profile(document),),
            objective=r"Inspect C:\Users\developer\private API instructions",
            default_work_mode="phased",
            context=RoutingMatchContext(lock_work_mode=True),
        )

        self.assertEqual(
            [
                {
                    "rule_id": "api-delivery",
                    "matched": False,
                    "matched_dimensions": ["work_modes"],
                    "unmatched_dimensions": ["objective_keywords"],
                    "reason_codes": ["objective-keyword-miss"],
                },
                {
                    "rule_id": "backend-api",
                    "matched": True,
                    "matched_dimensions": ["objective_keywords", "work_modes"],
                    "unmatched_dimensions": [],
                    "reason_codes": [],
                },
            ],
            [trace.to_dict() for trace in traces],
        )
        serialized = repr([trace.to_dict() for trace in traces])
        self.assertNotIn(r"C:\Users\developer", serialized)
        self.assertNotIn("private API instructions", serialized)

    def test_lint_reports_deterministic_rule_conflicts_and_shadowing(self) -> None:
        document = profile_document()
        duplicate = profile_document()["rules"][0]
        duplicate["rule_id"] = "api-copy"
        document["rules"].append(duplicate)

        issues = lint_profile(decode_routing_profile(document))

        self.assertEqual(
            ["duplicate-rule"],
            [issue.code for issue in issues if issue.severity == "error"],
        )

        shadowed_document = profile_document()
        shadowed = profile_document()["rules"][0]
        shadowed["rule_id"] = "openapi-lower-priority"
        shadowed["priority"] = 10
        shadowed["match"]["objective_keywords"] = ["openapi"]
        shadowed_document["rules"].append(shadowed)

        issues = lint_profile(decode_routing_profile(shadowed_document))

        self.assertIn("shadowed-rule", [issue.code for issue in issues])

        conflict_document = profile_document()
        conflict = profile_document()["rules"][0]
        conflict["rule_id"] = "service-contract"
        conflict["match"]["objective_keywords"] = ["service"]
        conflict["route"]["skill_tree"][0]["primary_skill_id"] = "skill:architecture-designer"
        conflict_document["rules"].append(conflict)

        issues = lint_profile(decode_routing_profile(conflict_document))

        self.assertIn("equal-rank-conflict", [issue.code for issue in issues])

    def test_lint_reports_missing_current_phase_and_alias_omission(self) -> None:
        issues = lint_profile(
            decode_routing_profile(profile_document()),
            current_phase_id="implementation",
        )

        self.assertIn("missing-current-phase", [issue.code for issue in issues])
        alias_issue = next(issue for issue in issues if issue.code == "lexical-alias-omission")
        self.assertEqual("advisory", alias_issue.severity)
        self.assertIn("應用程式介面", alias_issue.message)

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
