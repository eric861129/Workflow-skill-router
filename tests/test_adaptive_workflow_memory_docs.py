
from __future__ import annotations

from collections import Counter
import importlib
import inspect
import json
from pathlib import Path
import pkgutil
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOC_ROOT = ROOT / "site" / "src" / "content" / "docs"
STARTER = ROOT / "starter" / "v2" / "workflow-skill-router"
PLUGIN = ROOT / "plugins" / "workflow-skill-router" / "skills" / "workflow-skill-router"
EXAMPLES = (
    Path("assets/memory-policy.disabled.example.yaml"),
    Path("assets/memory-policy.reviewed.example.yaml"),
    Path("assets/memory-policy.automatic.example.yaml"),
)


class AdaptiveWorkflowMemoryDocumentationTests(unittest.TestCase):
    def test_bilingual_concepts_and_guides_publish_required_boundaries(self) -> None:
        pages = (
            "concepts/adaptive-workflow-memory.md",
            "guides/configure-workflow-memory.md",
            "guides/migrate-to-workflow-memory.md",
        )
        required = (
            "default-off",
            "disabled < observe < reviewed < automatic",
            "Workspace cannot elevate Personal",
            "automatic-managed",
            "intended-unverified",
            "no telemetry",
            "no background learning",
            "User-owned Profile",
            "purge",
            "observe -> reviewed -> automatic",
            "skill-only",
        )
        for relative in pages:
            english = DOC_ROOT / relative
            chinese = DOC_ROOT / "zh-tw" / relative
            with self.subTest(relative=relative):
                self.assertTrue(english.is_file(), english)
                self.assertTrue(chinese.is_file(), chinese)
                combined = english.read_text("utf-8") + "\n" + chinese.read_text("utf-8")
                for term in required:
                    self.assertIn(term, combined, (relative, term))

    def test_navigation_and_readmes_expose_the_opt_in_memory_path(self) -> None:
        navigation = (ROOT / "site" / "astro.config.mjs").read_text("utf-8")
        for route in (
            "concepts/adaptive-workflow-memory",
            "guides/configure-workflow-memory",
            "guides/migrate-to-workflow-memory",
        ):
            self.assertIn(route, navigation)

        for readme in ("README.md", "README.zh-TW.md"):
            text = (ROOT / readme).read_text("utf-8")
            with self.subTest(readme=readme):
                self.assertIn("Adaptive Workflow Memory", text)
                self.assertIn("default-off", text)
                self.assertIn("observe -> reviewed -> automatic", text)
                self.assertIn("no background learning", text)

    def test_three_policy_examples_are_strict_private_and_source_synchronized(self) -> None:
        from workflow_skill_router.memory.policy import decode_policy_text

        modes = []
        for relative in EXAMPLES:
            source = STARTER / relative
            target = PLUGIN / relative
            with self.subTest(relative=relative.as_posix()):
                self.assertTrue(source.is_file(), source)
                self.assertEqual(source.read_bytes(), target.read_bytes())
                rendered = source.read_text("utf-8")
                policy = decode_policy_text(rendered, format="yaml")
                self.assertEqual("personal", policy.scope.value)
                self.assertTrue(policy.policy_id.startswith("personal:"))
                folded = rendered.casefold()
                self.assertNotIn("local_path", folded)
                self.assertNotIn("api_key", folded)
                self.assertNotIn("access_token", folded)
                if policy.mode.value != "disabled":
                    self.assertIn("secrets: never", folded)
                modes.append(policy.mode.value)
        self.assertEqual(["disabled", "reviewed", "automatic"], modes)

    def _decode_with_production_contract(self, document: dict[str, object]) -> None:
        package = importlib.import_module("workflow_skill_router.memory")
        modules = [package]
        for info in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
            if any(token in info.name for token in ("cli", "history", "automatic")):
                continue
            try:
                modules.append(importlib.import_module(info.name))
            except Exception:
                continue

        attempts: list[str] = []
        for module in modules:
            for name, function in vars(module).items():
                folded = name.casefold()
                if not inspect.isfunction(function):
                    continue
                if "decode" not in folded or "policy" not in folded or "snapshot" in folded:
                    continue
                signature = inspect.signature(function)
                calls = [((document,), {})]
                if "expected_scope" in signature.parameters:
                    calls.insert(0, ((document,), {"expected_scope": "personal"}))
                calls.extend((((document, "personal"), {}),))
                for args, kwargs in calls:
                    try:
                        result = function(*args, **kwargs)
                    except TypeError:
                        continue
                    except Exception as exc:
                        attempts.append(f"{module.__name__}.{name}: {type(exc).__name__}")
                        continue
                    if result is not None:
                        return
        self.fail("No production Memory Policy decoder accepted the example: " + "; ".join(attempts[-8:]))

    def test_public_references_separate_storage_authority_and_receipt_evidence(self) -> None:
        pages = (
            "reference/cli.md",
            "reference/local-state.md",
            "reference/security-boundaries.md",
            "reference/mcp-tools.mdx",
            "showcase.md",
        )
        required = (
            "Operational DB",
            "Optional Memory DB",
            "managed-personal",
            "managed-workspace-local",
            "20",
            "Skill consistency",
            "receipt evidence",
            "unavailable",
            "deterministic-local-pilot",
            "not Model Evidence",
        )
        for relative in pages:
            for prefix in (Path(), Path("zh-tw")):
                path = DOC_ROOT / prefix / relative
                with self.subTest(path=path.as_posix()):
                    self.assertTrue(path.is_file(), path)
                    text = path.read_text("utf-8")
                    for term in required:
                        self.assertIn(term, text, (path, term))

    def test_flight_recorder_and_twenty_record_pilot_are_sanitized(self) -> None:
        path = ROOT / "site" / "src" / "data" / "memory-flight-recorder.generated.json"
        self.assertTrue(path.is_file(), path)
        payload = json.loads(path.read_text("utf-8"))
        scenarios = payload["scenarios"]
        pilot = payload["pilot"]
        self.assertEqual(5, len(scenarios))
        self.assertEqual(
            {"policy-resolution", "observe", "reviewed-proposal", "automatic-managed-promotion", "purge"},
            {scenario["id"] for scenario in scenarios},
        )
        self.assertTrue(all(
            scenario["evidence_class"] in {"fixture-trace", "sanitized-runtime-trace"}
            for scenario in scenarios
        ))
        self.assertEqual("deterministic-local-pilot", pilot["evidence_class"])
        self.assertEqual("not-model-evidence", pilot["claim"])
        records = pilot["records"]
        self.assertEqual(20, len(records))
        self.assertEqual(
            Counter({"single": 6, "phased": 8, "goal-like": 6}),
            Counter(record["shape"] for record in records),
        )
        self.assertGreaterEqual(sum(bool(record["profile_used"]) for record in records), 8)
        scenarios_covered = {record["scenario"] for record in records}
        for required in (
            "default-off", "observe-metrics", "reviewed-approval",
            "automatic-managed-write", "correction", "suppression", "rollback", "purge",
        ):
            self.assertIn(required, scenarios_covered)
        serialized = json.dumps(payload, ensure_ascii=False).casefold()
        for forbidden in (
            "objective_text", "raw_objective", "free_text_feedback", "profile_body",
            "/users/", "c:\\\\users\\\\", "api_key", "access_token",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_demo_inputs_schema_and_builder_own_the_memory_evidence(self) -> None:
        inputs = json.loads((ROOT / "demo" / "v2-scenarios" / "inputs.json").read_text("utf-8"))
        schema = json.loads((ROOT / "demo" / "v2-scenarios" / "schema.json").read_text("utf-8"))
        self.assertIn("memory_flight_recorder", inputs)
        self.assertIn("memory_pilot", inputs)
        self.assertIn("memory_flight_recorder", schema["properties"])
        self.assertIn("memory_pilot", schema["properties"])
        builder = (ROOT / "scripts" / "build-v2-demo-data.py").read_text("utf-8")
        self.assertIn("memory-flight-recorder.generated.json", builder)
        subprocess.run(
            [sys.executable, "scripts/build-v2-demo-data.py", "--check"],
            cwd=ROOT,
            check=True,
        )

    def test_homepage_loads_a_read_only_switchable_flight_recorder(self) -> None:
        component = (ROOT / "site" / "src" / "components" / "HomeLanding.astro").read_text("utf-8")
        for marker in (
            "memory-flight-recorder.generated.json",
            "data-memory-flight-recorder",
            "data-memory-tab",
            "data-memory-panel",
            "aria-selected",
            "not Model Evidence",
            "deterministic-local-pilot",
        ):
            self.assertIn(marker, component)
        start = component.index("<!-- M4-B memory-flight-recorder:start -->")
        end = component.index("<!-- M4-B memory-flight-recorder:end -->")
        memory_block = component[start:end]
        self.assertNotIn("fetch('/api", memory_block)
        self.assertNotIn("localStorage", memory_block)


if __name__ == "__main__":
    unittest.main()
