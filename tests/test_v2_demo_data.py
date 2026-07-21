import json
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("build_v2_demo_data",ROOT/"scripts/build-v2-demo-data.py")
module=importlib.util.module_from_spec(SPEC);sys.modules[SPEC.name]=module;SPEC.loader.exec_module(module)
build_demo_data=module.build_demo_data
validate_routing_evidence=module._validate_routing_evidence


class DemoDataTests(unittest.TestCase):
    def test_required_sanitized_presets_and_no_hand_authored_outputs(self):
        data=build_demo_data(ROOT)
        self.assertEqual({
            "small-auto",
            "small-explicit-reject-support",
            "medium-explicit-phase-consent",
            "medium-auto",
            "personal-skill-tree",
            "goal-work-graph",
            "verified-host-flow",
            "real-model-evaluation",
        },{item["id"] for item in data["presets"]})
        source=json.loads((ROOT/"demo/v2-scenarios/inputs.json").read_text("utf-8"))
        forbidden={"request_decision","route","active_selections","policy_result","events"}
        self.assertTrue(all(forbidden.isdisjoint(item) for item in source["presets"]))

    def test_personal_skill_tree_is_resolved_by_router_core_not_hand_authored(self):
        preset = next(
            item
            for item in build_demo_data(ROOT)["presets"]
            if item["id"] == "personal-skill-tree"
        )
        plan = preset["mcp_results"][0]["result"]
        self.assertEqual("personal-profile", plan["route_source"])
        self.assertEqual(["personal:demo-api"], plan["routing_profile_ids"])
        self.assertEqual("demo-api", plan["matched_profile_rule_id"])
        self.assertEqual("intended-unverified", plan["activation_status"])
        self.assertEqual(
            ["contract", "implementation", "verification"],
            [phase["phase_id"] for phase in plan["planned_skill_tree"]],
        )
        route = preset["branches"][0]["route"]
        self.assertEqual("personal-profile", route["primary_selection_source"])
        self.assertEqual("skill:api-designer", route["primary_selection"])
        self.assertEqual(["skill:api-guidelines-skill"], route["support_selections"])

    def test_every_scenario_exposes_ordered_sanitized_mcp_trace(self):
        data=build_demo_data(ROOT)
        for preset in data["presets"]:
            with self.subTest(preset=preset["id"]):
                self.assertTrue(preset["mcp_calls"])
                self.assertEqual(len(preset["mcp_calls"]),len(preset["mcp_results"]))
                self.assertIn(preset["runtime_profile"],{"bundled-local-r0","verified-host-fixture"})
                self.assertIn(preset["evidence_class"],{"runtime-trace","fixture-trace"})
                self.assertIn(preset["trace_source"],{"router-core","verified-core-fixture"})
                self.assertEqual("sanitized",preset["trace_status"])
                self.assertEqual(
                    [call["request_id"] for call in preset["mcp_calls"]],
                    [result["request_id"] for result in preset["mcp_results"]],
                )

    def test_bundled_managed_goal_reports_scheduler_capability_boundary(self):
        preset=next(item for item in build_demo_data(ROOT)["presets"] if item["id"]=="goal-work-graph")
        self.assertEqual("bundled-local-r0",preset["runtime_profile"])
        self.assertEqual(["plan_work","get_next_work","get_router_status"],[call["tool"] for call in preset["mcp_calls"]])
        self.assertTrue(preset["mcp_results"][0]["ok"])
        self.assertFalse(preset["mcp_results"][1]["ok"])
        self.assertEqual("capability-unavailable",preset["mcp_results"][1]["error"]["code"])
        self.assertEqual("get_next_work",preset["mcp_results"][1]["error"]["tool_name"])

    def test_verified_host_fixture_is_separate_and_requires_host_capabilities(self):
        preset=next(item for item in build_demo_data(ROOT)["presets"] if item["id"]=="verified-host-flow")
        self.assertEqual("verified-host-fixture",preset["runtime_profile"])
        self.assertEqual("fixture-trace",preset["evidence_class"])
        self.assertEqual("verified-core-fixture",preset["trace_source"])
        self.assertTrue(preset["requires_host_capabilities"])
        self.assertEqual(["plan_work","get_next_work","get_router_status"],[call["tool"] for call in preset["mcp_calls"]])
        self.assertTrue(all(result["ok"] for result in preset["mcp_results"]))

    def test_rejected_support_is_audited_but_never_activated(self):
        preset=next(item for item in build_demo_data(ROOT)["presets"] if item["id"]=="small-explicit-reject-support")
        branch=next(item for item in preset["branches"] if item["branch_id"]=="support-rejected")
        self.assertEqual([],branch["route"]["support_selections"])
        self.assertIn("SUPPORT_SKILL_PROPOSED",{event["event_type"] for event in branch["events"]})
        self.assertNotIn("CAPABILITY_ACTIVATION_OBSERVED",{event["event_type"] for event in branch["events"]})

    def test_explicit_consent_demo_uses_real_persisted_mcp_transitions(self):
        data = build_demo_data(ROOT)
        for scenario_id in (
            "small-explicit-reject-support",
            "medium-explicit-phase-consent",
        ):
            with self.subTest(scenario_id=scenario_id):
                preset = next(item for item in data["presets"] if item["id"] == scenario_id)
                self.assertEqual([
                    "plan_work",
                    "propose_support_consent",
                    "transition_support_consent",
                    "plan_work",
                    "propose_support_consent",
                    "transition_support_consent",
                    "get_router_status",
                ], [call["tool"] for call in preset["mcp_calls"]])
                self.assertTrue(all(result["ok"] for result in preset["mcp_results"]))
                self.assertEqual(
                    ["rejected", "approved"],
                    [
                        preset["mcp_results"][index]["result"]["consent_action"]
                        for index in (2, 5)
                    ],
                )

    def test_auto_route_selects_minimal_support_without_consent_branch(self):
        preset=next(item for item in build_demo_data(ROOT)["presets"] if item["id"]=="medium-auto")
        self.assertEqual(["default"],[branch["branch_id"] for branch in preset["branches"]])
        self.assertIn("before diagnosis exits",preset["request"]["en"])
        self.assertEqual(["diagnose","implement"],preset["phases"])
        branch=preset["branches"][0]
        self.assertEqual(["skill:playwright"],branch["route"]["support_selections"])
        event_types={event["event_type"] for event in branch["events"]}
        self.assertIn("SUPPORT_SKILL_AUTO_SELECTED",event_types)
        self.assertNotIn("SUPPORT_SKILL_PROPOSED",event_types)

    def test_public_evaluation_is_honest(self):
        preset=next(item for item in build_demo_data(ROOT)["presets"] if item["id"]=="real-model-evaluation")
        self.assertIn(preset["evaluation"]["status"],{"manual-required","review-required"})
        self.assertEqual("review-required",preset["evaluation"]["publication_gate"])
        self.assertTrue(preset["evaluation"]["source_digest"].startswith("sha256:"))
        self.assertNotIn("score",preset["evaluation"])
        self.assertNotIn("raw_traces",preset["evaluation"])

    def test_demo_exposes_branch_scoped_planning_and_activation_evidence(self):
        data = build_demo_data(ROOT)
        allowed_sources = {
            "native-goal-binding",
            "caller-work-mode-hint",
            "deterministic-analyzer",
            "profile-route",
            "builtin-fallback",
            "legacy-replay",
        }
        for preset in data["presets"]:
            with self.subTest(preset=preset["id"]):
                plan = preset["mcp_results"][0]["result"]
                evidence = preset["routing_evidence"]
                self.assertEqual(plan["classification"], evidence["classification"])
                self.assertIn(evidence["classification"]["source"], allowed_sources)
                self.assertFalse(evidence["authority"]["native_goal_mutation"])
                self.assertFalse(evidence["authority"]["deployment"])
                self.assertFalse(evidence["authority"]["production"])
                self.assertNotIn("planned_skill_ids", evidence)
                for branch in preset["branches"]:
                    branch_evidence = branch["routing_evidence"]
                    route_selections = [
                        branch["route"]["primary_selection"],
                        *branch["route"]["support_selections"],
                    ]
                    self.assertEqual(
                        [item for item in route_selections if item.startswith("skill:")],
                        branch_evidence["planned_skill_ids"],
                    )
                    self.assertEqual(
                        [item for item in route_selections if not item.startswith("skill:")],
                        branch_evidence["planned_non_skill_selection_ids"],
                    )
                    self.assertEqual("unverified", branch_evidence["actual_activation"])

        by_id = {item["id"]: item for item in data["presets"]}
        self.assertEqual(
            "deterministic-analyzer",
            by_id["medium-explicit-phase-consent"]["routing_evidence"]
            ["classification"]["source"],
        )
        self.assertEqual(
            "caller-work-mode-hint",
            by_id["personal-skill-tree"]["routing_evidence"]
            ["classification"]["source"],
        )
        self.assertEqual(
            {
                "status": "applied",
                "source": "personal-profile",
                "profile_ids": ["personal:demo-api"],
                "matched_rule_id": "demo-api",
            },
            by_id["personal-skill-tree"]["routing_evidence"]["profile_match"],
        )
        self.assertEqual(
            "native-goal-binding",
            by_id["goal-work-graph"]["routing_evidence"]
            ["classification"]["source"],
        )
        for preset_id, preset in by_id.items():
            if preset_id == "personal-skill-tree":
                continue
            self.assertEqual(
                {
                    "status": "not-applied",
                    "source": None,
                    "profile_ids": [],
                    "matched_rule_id": None,
                },
                preset["routing_evidence"]["profile_match"],
            )

        consent = by_id["medium-explicit-phase-consent"]
        rejected = next(
            branch for branch in consent["branches"]
            if branch["branch_id"] == "support-rejected"
        )
        approved = next(
            branch for branch in consent["branches"]
            if branch["branch_id"] == "support-approved"
        )
        self.assertEqual(
            "phase-scoped-user-decision",
            approved["routing_evidence"]["consent_boundary"],
        )
        self.assertEqual(
            {
                "status": "locked",
                "skill_ids": ["skill:api-designer"],
            },
            approved["routing_evidence"]["explicit_skill_lock"],
        )
        self.assertEqual(
            ["skill:api-designer"],
            rejected["routing_evidence"]["planned_skill_ids"],
        )
        self.assertEqual(
            ["skill:api-designer", "skill:qa-support"],
            approved["routing_evidence"]["planned_skill_ids"],
        )

        automatic = by_id["medium-auto"]["branches"][0]
        self.assertEqual(
            ["skill:systematic-debugging", "skill:playwright"],
            automatic["routing_evidence"]["planned_skill_ids"],
        )
        self.assertEqual(
            {"status": "not-applied", "skill_ids": []},
            automatic["routing_evidence"]["explicit_skill_lock"],
        )

        evaluation = by_id["real-model-evaluation"]["branches"][0]
        self.assertEqual([], evaluation["routing_evidence"]["planned_skill_ids"])
        self.assertEqual(
            ["evaluation:runner"],
            evaluation["routing_evidence"]["planned_non_skill_selection_ids"],
        )

    def test_routing_evidence_rejects_misclassified_or_lost_selections(self):
        data = build_demo_data(ROOT)
        evaluation_index = next(
            index for index, preset in enumerate(data["presets"])
            if preset["id"] == "real-model-evaluation"
        )

        misclassified = json.loads(json.dumps(data))
        evidence = misclassified["presets"][evaluation_index]["branches"][0][
            "routing_evidence"
        ]
        evidence["planned_skill_ids"] = ["evaluation:runner"]
        evidence["planned_non_skill_selection_ids"] = []
        with self.assertRaisesRegex(ValueError, "planned selection"):
            validate_routing_evidence(misclassified)

        lost = json.loads(json.dumps(data))
        lost_evidence = lost["presets"][evaluation_index]["branches"][0][
            "routing_evidence"
        ]
        lost_evidence["planned_non_skill_selection_ids"] = []
        with self.assertRaisesRegex(ValueError, "planned selection"):
            validate_routing_evidence(lost)

        invalid_skill_namespace = json.loads(json.dumps(data))
        invalid_branch = invalid_skill_namespace["presets"][0]["branches"][0]
        invalid_branch["route"]["primary_selection"] = "skill:"
        invalid_branch["routing_evidence"]["planned_skill_ids"] = ["skill:"]
        with self.assertRaisesRegex(ValueError, "selection identifier"):
            validate_routing_evidence(invalid_skill_namespace)

    def test_authority_evidence_requires_exact_false_booleans(self):
        data = build_demo_data(ROOT)
        authority = data["presets"][0]["routing_evidence"]["authority"]
        self.assertEqual(
            {"native_goal_mutation", "deployment", "production"},
            set(authority),
        )

        for invalid in (0, None, "", {}, []):
            with self.subTest(invalid=invalid):
                candidate = json.loads(json.dumps(data))
                candidate["presets"][0]["routing_evidence"]["authority"][
                    "deployment"
                ] = invalid
                with self.assertRaisesRegex(ValueError, "authority"):
                    validate_routing_evidence(candidate)

        missing = json.loads(json.dumps(data))
        del missing["presets"][0]["routing_evidence"]["authority"]["production"]
        with self.assertRaisesRegex(ValueError, "authority"):
            validate_routing_evidence(missing)

    def test_profile_match_rejects_generic_route_sources(self):
        data = build_demo_data(ROOT)
        profile = next(
            preset for preset in data["presets"]
            if preset["id"] == "personal-skill-tree"
        )
        for generic_source in ("user-explicit", "builtin-default"):
            with self.subTest(generic_source=generic_source):
                candidate = json.loads(json.dumps(data))
                candidate_profile = next(
                    preset for preset in candidate["presets"]
                    if preset["id"] == profile["id"]
                )
                candidate_profile["routing_evidence"]["profile_match"][
                    "source"
                ] = generic_source
                with self.assertRaisesRegex(ValueError, "profile match"):
                    validate_routing_evidence(candidate)

    def test_committed_demo_matches_the_generator(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/build-v2-demo-data.py"), "--check"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__=="__main__":unittest.main()
