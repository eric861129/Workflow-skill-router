from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def load_route_case_tools():
    module_path = SCRIPTS_DIR / "route_case_tools.py"
    spec = importlib.util.spec_from_file_location("route_case_tools", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["route_case_tools"] = module
    spec.loader.exec_module(module)
    return module


def write_case(path: Path, **overrides) -> None:
    route_case = {
        "id": path.stem,
        "title": "Public example",
        "domain": "frontend",
        "task": "Fix a public sample interface bug.",
        "context": "The sample page renders stale data after a filter change.",
        "route": {
            "path": "Frontend / Sample > Regression",
            "primary": "frontend-debugging-workflow",
            "supporting": ["qa-test-planner"],
            "reason": "Start with the visible regression and keep verification focused.",
        },
        "omitted_skills": [
            {
                "skill": "database-optimizer",
                "reason": "No query performance problem is described.",
            }
        ],
        "tags": ["frontend", "regression"],
        "public_safety": {
            "fictionalized": True,
            "no_private_paths": True,
            "no_secrets": True,
            "no_customer_names": True,
            "no_live_credentials": True,
            "review_notes": "Uses fictional public sample language.",
        },
    }
    route_case.update(overrides)
    path.write_text(json.dumps(route_case, ensure_ascii=False, indent=2), encoding="utf-8")


class RouteCaseTests(unittest.TestCase):
    def test_repository_route_cases_are_valid_and_generated(self) -> None:
        tools = load_route_case_tools()
        cases, errors = tools.load_route_cases(REPO_ROOT / "route-cases")

        self.assertEqual(errors, [])
        self.assertGreaterEqual(len(cases), 10)
        gallery_data = tools.build_gallery_data(cases)
        self.assertEqual(gallery_data["case_count"], len(cases))
        self.assertIn("api", gallery_data["domains"])
        self.assertIn("anti-over-routing", gallery_data["tags"])

    def test_generator_check_passes_for_tracked_outputs(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "build-route-gallery.py"), "--check"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_selected_primary_in_supporting(self) -> None:
        tools = load_route_case_tools()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_case(
                root / "duplicate-primary.json",
                route={
                    "path": "Frontend / Sample > Regression",
                    "primary": "frontend-debugging-workflow",
                    "supporting": ["frontend-debugging-workflow"],
                    "reason": "This intentionally repeats the primary skill.",
                },
            )

            _cases, errors = tools.load_route_cases(root)

        self.assertTrue(any("route.primary must not be repeated" in error for error in errors))

    def test_rejects_private_network_text(self) -> None:
        tools = load_route_case_tools()
        private_address = ".".join(["10", "0", "0", "5"])
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_case(root / "unsafe-context.json", context=f"Debug a sample service at {private_address}.")

            _cases, errors = tools.load_route_cases(root)

        self.assertTrue(any("private IP address" in error for error in errors))

    def test_rejects_unchecked_public_safety(self) -> None:
        tools = load_route_case_tools()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_case(
                root / "unchecked-safety.json",
                public_safety={
                    "fictionalized": True,
                    "no_private_paths": True,
                    "no_secrets": False,
                    "no_customer_names": True,
                    "no_live_credentials": True,
                },
            )

            _cases, errors = tools.load_route_cases(root)

        self.assertTrue(any("public_safety.no_secrets must be true" in error for error in errors))

    def test_generated_scenarios_keep_route_expectations(self) -> None:
        tools = load_route_case_tools()
        cases, errors = tools.load_route_cases(REPO_ROOT / "route-cases")

        self.assertEqual(errors, [])
        scenarios = tools.build_evaluation_scenarios(cases)
        self.assertEqual(len(scenarios), len(cases))
        self.assertTrue(all(scenario["id"].startswith("route-case-") for scenario in scenarios))
        self.assertTrue(all(scenario["max_skills"] == 4 for scenario in scenarios))


if __name__ == "__main__":
    unittest.main()
