import json
import importlib.util
from pathlib import Path
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
            "goal-work-graph",
            "verified-host-flow",
            "real-model-evaluation",
        },{item["id"] for item in data["presets"]})
        source=json.loads((ROOT/"demo/v2-scenarios/inputs.json").read_text("utf-8"))
        forbidden={"request_decision","route","active_selections","policy_result","events"}
        self.assertTrue(all(forbidden.isdisjoint(item) for item in source["presets"]))

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

    def test_auto_route_selects_minimal_support_without_consent_branch(self):
        preset=next(item for item in build_demo_data(ROOT)["presets"] if item["id"]=="medium-auto")
        self.assertEqual(["default"],[branch["branch_id"] for branch in preset["branches"]])
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


if __name__=="__main__":unittest.main()
