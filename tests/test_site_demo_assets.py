import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO_DATA = ROOT / "site/src/data/router-demo-v2.generated.json"
MANIFEST = ROOT / "site/public/assets/workflow-skill-router-demo-manifest.json"
BUILDER = ROOT / "site/scripts/generate-demo-assets.mjs"


class SiteDemoAssetTests(unittest.TestCase):
    def test_manifest_binds_only_whitelisted_runtime_boundary_fields(self) -> None:
        data = json.loads(DEMO_DATA.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        presets = {preset["id"]: preset for preset in data["presets"]}

        local = presets["router-local-work-loop"]
        native_goal = presets["goal-work-graph"]
        expected = {
            "source_preset_ids": ["router-local-work-loop", "goal-work-graph"],
            "router_local": {
                "authority_mode": local["mcp_results"][1]["result"]["authority_mode"],
                "host_goal_mutated": local["mcp_results"][1]["result"]["host_goal_mutated"],
                "evidence_class": local["mcp_results"][2]["result"]["evidence_class"],
                "host_transition_authorized": local["mcp_results"][2]["result"]["host_transition_authorized"],
                "gate_scope": local["mcp_results"][4]["result"]["gate_scope"],
            },
            "native_goal": {
                "code": native_goal["mcp_results"][1]["error"]["code"],
                "availability": native_goal["mcp_results"][1]["error"]["availability"],
                "required_capabilities": native_goal["mcp_results"][1]["error"]["required_capabilities"],
            },
        }
        self.assertEqual(expected, manifest["presentation"])
        serialized = json.dumps(manifest["presentation"], ensure_ascii=False).lower()
        for forbidden in ("request", "objective", "instruction", "workspace", "path", "secret"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, serialized)

    def test_builder_renders_runtime_boundary_data_not_a_hand_authored_route(self) -> None:
        source = BUILDER.read_text(encoding="utf-8")
        self.assertIn("selectPublicBoundaryData", source)
        self.assertIn("router-local-work-loop", source)
        self.assertIn("goal-work-graph", source)
        self.assertIn("Router-local advisory", source)
        self.assertIn("Native Goal requires verified Host", source)
        for invented in (
            "Fuzzy request in.",
            "api-designer",
            "database-optimizer",
            "qa-test-planner",
            "Add audit tables",
        ):
            with self.subTest(invented=invented):
                self.assertNotIn(invented, source)


if __name__ == "__main__":
    unittest.main()
