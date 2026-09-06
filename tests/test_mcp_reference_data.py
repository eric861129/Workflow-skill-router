import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE_SOURCE = ROOT / "packages" / "router-core" / "src"
if str(CORE_SOURCE) not in sys.path:
    sys.path.insert(0, str(CORE_SOURCE))
OUTPUT = ROOT / "site" / "src" / "data" / "mcp-tools.generated.json"
SCRIPT = ROOT / "scripts" / "build-mcp-reference-data.mjs"


class McpReferenceDataTests(unittest.TestCase):
    def test_generated_reference_matches_public_tools_and_runtime_readiness(self) -> None:
        from workflow_skill_router.runtime_readiness import RUNTIME_READINESS
        from workflow_skill_router.tool_dispatch import PUBLIC_TOOLS

        document = json.loads(OUTPUT.read_text(encoding="utf-8"))
        self.assertEqual("1.0", document["schema_version"])
        self.assertEqual(list(PUBLIC_TOOLS), [tool["name"] for tool in document["tools"]])
        self.assertEqual(set(PUBLIC_TOOLS), set(document["runtime_readiness"]))

        for tool in document["tools"]:
            readiness = RUNTIME_READINESS[tool["name"]]
            self.assertEqual(readiness.availability, tool["availability"])
            self.assertEqual(readiness.risk_class, tool["risk_class"])
            self.assertEqual(
                list(readiness.required_capabilities),
                tool["required_capabilities"],
            )
            self.assertEqual(readiness.fallback_action, tool["fallback_action"])
            self.assertEqual(
                list(readiness.local_conditions),
                tool["local_conditions"],
            )
            self.assertGreaterEqual(len(tool["title"]), 8)
            self.assertGreaterEqual(len(tool["description"]), 80)
            self.assertIn("readOnlyHint", tool["annotations"])
            self.assertIn("idempotentHint", tool["annotations"])
            self.assertIsInstance(tool["inputSchema"], dict)
            self.assertIsInstance(tool["outputSchema"], dict)

        by_name = {tool["name"]: tool for tool in document["tools"]}
        self.assertEqual(
            {
                "get_next_work",
                "record_work_event",
                "evaluate_gate",
                "transition_profile_update",
                "rollback_profile_revision",
            },
            {
                name
                for name, tool in by_name.items()
                if tool["runtime_requirement"] == "conditional-local"
            },
        )
        for name in (
            "get_next_work",
            "record_work_event",
            "evaluate_gate",
        ):
            with self.subTest(name=name):
                self.assertEqual(
                    [
                        "router-owned-work-graph",
                        "no-native-goal-authority-required",
                    ],
                    by_name[name]["local_conditions"],
                )
                self.assertIn("Router-owned", by_name[name]["description"])
                self.assertIn("Native Goal", by_name[name]["description"])

        serialized = OUTPUT.read_text(encoding="utf-8")
        self.assertNotIn(str(ROOT), serialized)
        self.assertNotIn("WORKFLOW_SKILL_ROUTER_DATA_DIR", serialized)

    def test_plugin_embedded_profile_contract_matches_core(self) -> None:
        core = ROOT / "packages/router-core/src/workflow_skill_router/schemas/json/v2/routing-profile.schema.json"
        plugin = ROOT / "plugins/workflow-skill-router/mcp/src/routing-profile-contract.json"
        self.assertEqual(json.loads(core.read_text(encoding="utf-8")), json.loads(plugin.read_text(encoding="utf-8")))

    def test_memory_tools_are_exactly_eight_with_strict_intents_and_readiness(self) -> None:
        document = json.loads(OUTPUT.read_text(encoding="utf-8"))
        tools = {tool["name"]: tool for tool in document["tools"]}
        names = {"get_memory_status", "remember_workflow", "record_route_feedback",
                 "list_workflow_candidates", "preview_profile_update", "transition_profile_update",
                 "rollback_profile_revision", "purge_workflow_memory"}
        self.assertEqual(20, len(tools))
        self.assertTrue(names <= set(tools))
        for name in names:
            self.assertFalse(tools[name]["inputSchema"]["additionalProperties"])
            self.assertFalse(tools[name]["outputSchema"]["additionalProperties"])
        for name in {"get_memory_status", "list_workflow_candidates", "preview_profile_update"}:
            self.assertTrue(tools[name]["annotations"]["readOnlyHint"])
        self.assertTrue(tools["purge_workflow_memory"]["annotations"]["destructiveHint"])
        self.assertEqual("R1", tools["purge_workflow_memory"]["risk_class"])
        for field in ("candidate_id", "target_profile_class", "profile", "matcher_seed", "authority", "target_path"):
            self.assertNotIn(field, tools["transition_profile_update"]["inputSchema"]["properties"])
        for relative in ("site/src/content/docs/reference/mcp-tools.mdx", "site/src/content/docs/zh-tw/reference/mcp-tools.mdx"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("20", text)
            self.assertIn("10 local-ready", text)
            self.assertIn("5 conditional-local", text)

    def test_reference_generator_reports_no_drift(self) -> None:
        result = subprocess.run(
            ["node", str(SCRIPT), "--check"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_plan_work_contract_exposes_deterministic_sources_and_boundaries(self) -> None:
        document = json.loads(OUTPUT.read_text(encoding="utf-8"))
        plan_work = next(tool for tool in document["tools"] if tool["name"] == "plan_work")
        description = plan_work["description"]
        self.assertIn("deterministic automatic classification", description)
        self.assertIn("optional deterministic Profile", description)
        self.assertIn("Explicit Skill Lock", description)
        self.assertIn("consent", description)
        self.assertIn("activation remains unverified", description)

        input_properties = plan_work["inputSchema"]["properties"]
        self.assertIn(
            "deterministic automatic classification",
            input_properties["requested_work_mode"]["description"],
        )
        self.assertIn(
            "optional deterministic Profile",
            input_properties["routing_context"]["description"],
        )

        output_schema = plan_work["outputSchema"]
        output_properties = output_schema["properties"]
        self.assertIn("classification", output_schema["required"])
        self.assertFalse(output_properties["classification"]["additionalProperties"])
        self.assertEqual(
            {
                "native-goal-binding",
                "caller-work-mode-hint",
                "deterministic-analyzer",
                "profile-route",
                "builtin-fallback",
                "legacy-replay",
            },
            set(output_properties["classification"]["properties"]["source"]["enum"]),
        )
        self.assertIn(
            "does not prove runtime activation",
            output_properties["planned_skill_ids"]["description"],
        )
        self.assertIn(
            "never proves actual activation",
            output_properties["activation_status"]["description"],
        )

    def test_committed_server_bundle_matches_mcp_source(self) -> None:
        plugin = ROOT / "plugins/workflow-skill-router"
        committed = plugin / "mcp/server.bundle.mjs"
        with tempfile.TemporaryDirectory() as directory:
            generated = Path(directory) / "server.bundle.mjs"
            result = subprocess.run(
                [
                    "node",
                    str(plugin / "scripts/build-mcp.mjs"),
                    "--output",
                    str(generated),
                ],
                cwd=plugin,
                text=True,
                capture_output=True,
                timeout=60,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(committed.read_bytes(), generated.read_bytes())


if __name__ == "__main__":
    unittest.main()
