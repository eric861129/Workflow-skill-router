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

    def test_demo_exposes_classification_profile_and_activation_evidence(self):
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
                self.assertEqual(plan["route_source"], evidence["profile_match_source"])
                self.assertEqual(plan["planned_skill_ids"], evidence["planned_skill_ids"])
                self.assertEqual("unverified", evidence["actual_activation"])
                self.assertFalse(evidence["authority"]["native_goal_mutation"])
                self.assertFalse(evidence["authority"]["deployment"])
                self.assertFalse(evidence["authority"]["production"])

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
            "personal-profile",
            by_id["personal-skill-tree"]["routing_evidence"]
            ["profile_match_source"],
        )
        self.assertEqual(
            "native-goal-binding",
            by_id["goal-work-graph"]["routing_evidence"]
            ["classification"]["source"],
        )
        self.assertTrue(
            by_id["medium-explicit-phase-consent"]["routing_evidence"]
            ["explicit_skill_lock"]
        )
        self.assertEqual(
            "phase-scoped-user-decision",
            by_id["medium-explicit-phase-consent"]["routing_evidence"]
            ["consent_boundary"],
        )

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
