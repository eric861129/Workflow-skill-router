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
        self.assertEqual({"small-auto","small-explicit-reject-support","medium-explicit-phase-consent","medium-auto","goal-work-graph","real-model-evaluation"},{item["id"] for item in data["presets"]})
        source=json.loads((ROOT/"demo/v2-scenarios/inputs.json").read_text("utf-8"))
        forbidden={"request_decision","route","active_selections","policy_result","events"}
        self.assertTrue(all(forbidden.isdisjoint(item) for item in source["presets"]))

    def test_rejected_support_is_audited_but_never_activated(self):
        preset=next(item for item in build_demo_data(ROOT)["presets"] if item["id"]=="small-explicit-reject-support")
        branch=next(item for item in preset["branches"] if item["branch_id"]=="support-rejected")
        self.assertEqual([],branch["route"]["support_selections"])
        self.assertIn("SUPPORT_SKILL_PROPOSED",{event["event_type"] for event in branch["events"]})
        self.assertNotIn("CAPABILITY_ACTIVATION_OBSERVED",{event["event_type"] for event in branch["events"]})

    def test_public_evaluation_is_honest(self):
        preset=next(item for item in build_demo_data(ROOT)["presets"] if item["id"]=="real-model-evaluation")
        self.assertIn(preset["evaluation"]["status"],{"manual-required","review-required"})
        self.assertNotIn("score",preset["evaluation"])


if __name__=="__main__":unittest.main()
