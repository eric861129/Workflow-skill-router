from __future__ import annotations

from pathlib import Path
import textwrap


ROOT = Path.cwd()


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected marker missing in {path}: {old!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def insert_before(path: str, marker: str, block: str, sentinel: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if sentinel in text:
        return
    if marker not in text:
        raise RuntimeError(f"Expected insertion marker missing in {path}: {marker!r}")
    text = text.replace(marker, block.rstrip() + "\n\n" + marker, 1)
    target.write_text(text, encoding="utf-8", newline="\n")


TEST_FILE = r'''
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
        modes = []
        for relative in EXAMPLES:
            source = STARTER / relative
            target = PLUGIN / relative
            with self.subTest(relative=relative.as_posix()):
                self.assertTrue(source.is_file(), source)
                self.assertEqual(source.read_bytes(), target.read_bytes())
                document = json.loads(source.read_text("utf-8"))
                self.assertEqual("personal", document["scope"])
                self.assertTrue(str(document["policy_id"]).startswith("personal:"))
                self.assertNotIn("objective", json.dumps(document).casefold())
                self.assertNotIn("local_path", json.dumps(document).casefold())
                self.assertNotIn("secret", json.dumps(document).casefold())
                modes.append(document["mode"])
                self._decode_with_production_contract(document)
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
        self.assertNotIn("fetch('/api", component)
        self.assertNotIn("localStorage", component)


if __name__ == "__main__":
    unittest.main()
'''

write("tests/test_adaptive_workflow_memory_docs.py", textwrap.dedent(TEST_FILE))

replace_once(
    "tests/test_doc_parity.py",
    '            "concepts/personal-routing-profiles",\n            "reference/mcp-tools",',
    '            "concepts/personal-routing-profiles",\n            "concepts/adaptive-workflow-memory",\n            "guides/configure-workflow-memory",\n            "guides/migrate-to-workflow-memory",\n            "reference/mcp-tools",',
)

insert_before(
    "tests/test_v2_documentation.py",
    '\n\nif __name__=="__main__":unittest.main()',
    r'''
    def test_adaptive_workflow_memory_is_default_off_bilingual_and_non_elevating(self):
        pages = (
            "site/src/content/docs/concepts/adaptive-workflow-memory.md",
            "site/src/content/docs/zh-tw/concepts/adaptive-workflow-memory.md",
            "site/src/content/docs/guides/configure-workflow-memory.md",
            "site/src/content/docs/zh-tw/guides/configure-workflow-memory.md",
            "site/src/content/docs/guides/migrate-to-workflow-memory.md",
            "site/src/content/docs/zh-tw/guides/migrate-to-workflow-memory.md",
        )
        for relative in pages:
            text = (ROOT / relative).read_text("utf-8")
            with self.subTest(relative=relative):
                self.assertIn("default-off", text)
                self.assertIn("disabled < observe < reviewed < automatic", text)
                self.assertIn("Workspace cannot elevate Personal", text)
                self.assertIn("automatic-managed", text)
                self.assertIn("intended-unverified", text)
                self.assertIn("no telemetry", text)
                self.assertIn("no background learning", text)
                self.assertIn("User-owned Profile", text)
''',
    "test_adaptive_workflow_memory_is_default_off_bilingual_and_non_elevating",
)

replace_once(
    "tests/test_skill_source_sync.py",
    '    Path("assets/workspace-routing-profile.example.json"),\n',
    '    Path("assets/workspace-routing-profile.example.json"),\n'
    '    Path("assets/memory-policy.disabled.example.yaml"),\n'
    '    Path("assets/memory-policy.reviewed.example.yaml"),\n'
    '    Path("assets/memory-policy.automatic.example.yaml"),\n',
)

insert_before(
    "tests/test_skill_source_sync.py",
    '\nif __name__ == "__main__":\n    unittest.main()',
    r'''
    def test_memory_policy_examples_are_packaged_and_default_off_capable(self) -> None:
        import json

        expected = ("disabled", "reviewed", "automatic")
        actual = []
        for name in (
            "memory-policy.disabled.example.yaml",
            "memory-policy.reviewed.example.yaml",
            "memory-policy.automatic.example.yaml",
        ):
            source = SOURCE / "assets" / name
            target = TARGET / "assets" / name
            self.assertEqual(source.read_bytes(), target.read_bytes(), name)
            document = json.loads(source.read_text("utf-8"))
            actual.append(document["mode"])
            self.assertEqual("personal", document["scope"])
        self.assertEqual(expected, tuple(actual))
''',
    "test_memory_policy_examples_are_packaged_and_default_off_capable",
)
