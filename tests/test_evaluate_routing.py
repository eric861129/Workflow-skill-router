from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_evaluator():
    module_path = REPO_ROOT / "scripts" / "evaluate-routing.py"
    spec = importlib.util.spec_from_file_location("evaluate_routing", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def scenario(
    scenario_id: str = "frontend-api-regression",
    primary: str = "frontend-debugging",
    supporting: list[str] | None = None,
    forbidden: list[str] | None = None,
    max_skills: int = 3,
) -> dict:
    return {
        "id": scenario_id,
        "task": "Fix a Vue page that broke after an API response changed.",
        "context": "The rendered page is empty after a backend contract change.",
        "expected": {
            "primary": primary,
            "supporting": supporting if supporting is not None else ["api-contract-review", "test-repair"],
        },
        "forbidden": forbidden if forbidden is not None else ["database-migration"],
        "max_skills": max_skills,
        "tags": ["frontend", "api", "regression"],
        "notes": "The router should start with frontend debugging and verify the API contract.",
    }


def prediction(
    scenario_id: str = "frontend-api-regression",
    primary: str = "frontend-debugging",
    supporting: list[str] | None = None,
    explanation: str = "Reproduce the frontend regression, verify the API contract, and repair tests.",
) -> dict:
    return {
        "id": scenario_id,
        "selected": {
            "primary": primary,
            "supporting": supporting if supporting is not None else ["api-contract-review", "test-repair"],
        },
        "explanation": explanation,
        "stage_split": False,
    }


class EvaluateRoutingTests(unittest.TestCase):
    def run_evaluator(
        self,
        scenarios: list[dict],
        predictions: list[dict],
        *extra_args: str,
    ) -> tuple[int, dict, str]:
        evaluator = load_evaluator()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            scenarios_path = root / "scenarios.jsonl"
            predictions_path = root / "predictions.jsonl"
            report_path = root / "report.md"
            json_report_path = root / "report.json"
            write_jsonl(scenarios_path, scenarios)
            write_jsonl(predictions_path, predictions)

            with redirect_stderr(io.StringIO()):
                code = evaluator.main(
                    [
                        "--scenarios",
                        str(scenarios_path),
                        "--predictions",
                        str(predictions_path),
                        "--report",
                        str(report_path),
                        "--json-report",
                        str(json_report_path),
                        *extra_args,
                    ]
                )

            report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
            report_json = json.loads(json_report_path.read_text(encoding="utf-8")) if json_report_path.exists() else {}
            return code, report_json, report_text

    def test_perfect_match_metrics(self) -> None:
        code, report_json, report_text = self.run_evaluator(
            [scenario()],
            [prediction(primary=" Frontend-Debugging ", supporting=["api-contract-review", "TEST-REPAIR"])],
            "--strict",
            "--fail-on-violations",
        )

        self.assertEqual(code, 0)
        metrics = report_json["metrics"]
        self.assertEqual(metrics["Scenario Count"], 1)
        self.assertEqual(metrics["Prediction Count"], 1)
        self.assertEqual(metrics["Primary Accuracy"], 1.0)
        self.assertEqual(metrics["Supporting Recall"], 1.0)
        self.assertEqual(metrics["Supporting Precision"], 1.0)
        self.assertEqual(metrics["Exact Route Match Rate"], 1.0)
        self.assertIn("# Routing Evaluation Report", report_text)

    def test_primary_mismatch_fails_in_strict_mode(self) -> None:
        code, report_json, report_text = self.run_evaluator(
            [scenario()],
            [prediction(primary="backend-endpoint-update")],
            "--strict",
        )

        self.assertEqual(code, 1)
        self.assertEqual(report_json["metrics"]["Primary Accuracy"], 0.0)
        self.assertIn("primary mismatch", report_text)

    def test_supporting_partial_recall_and_precision(self) -> None:
        code, report_json, _report_text = self.run_evaluator(
            [scenario(supporting=["api-contract-review", "test-repair"])],
            [prediction(supporting=["api-contract-review", "documentation-update"])],
        )

        self.assertEqual(code, 0)
        self.assertEqual(report_json["metrics"]["Supporting Recall"], 0.5)
        self.assertEqual(report_json["metrics"]["Supporting Precision"], 0.5)

    def test_forbidden_violation_fails_on_violations(self) -> None:
        code, report_json, report_text = self.run_evaluator(
            [scenario(forbidden=["database-migration"])],
            [prediction(supporting=["api-contract-review", "database-migration"])],
            "--fail-on-violations",
        )

        self.assertEqual(code, 1)
        self.assertEqual(report_json["metrics"]["Forbidden Skill Violation Rate"], 1.0)
        self.assertIn("database-migration", report_text)

    def test_max_skill_violation_fails_on_violations(self) -> None:
        code, report_json, report_text = self.run_evaluator(
            [scenario(max_skills=2)],
            [prediction(supporting=["api-contract-review", "test-repair"])],
            "--fail-on-violations",
        )

        self.assertEqual(code, 1)
        self.assertEqual(report_json["metrics"]["Max Skill Count Violation Rate"], 1.0)
        self.assertIn("| frontend-api-regression | 2 | 3 |", report_text)

    def test_missing_prediction_fails_on_violations(self) -> None:
        code, report_json, report_text = self.run_evaluator(
            [scenario("a"), scenario("b")],
            [prediction("a")],
            "--fail-on-violations",
        )

        self.assertEqual(code, 1)
        self.assertEqual(report_json["metrics"]["Missing Prediction Count"], 1)
        self.assertIn("missing prediction", report_text)

    def test_unknown_prediction_fails_on_violations(self) -> None:
        code, report_json, report_text = self.run_evaluator(
            [scenario("a")],
            [prediction("a"), prediction("unknown")],
            "--fail-on-violations",
        )

        self.assertEqual(code, 1)
        self.assertEqual(report_json["metrics"]["Unknown Prediction Count"], 1)
        self.assertIn("unknown prediction", report_text)

    def test_duplicate_scenario_id_is_schema_error(self) -> None:
        code, report_json, _report_text = self.run_evaluator(
            [scenario("duplicate"), scenario("duplicate")],
            [prediction("duplicate")],
        )

        self.assertEqual(code, 1)
        self.assertTrue(any("duplicate scenario id" in issue for issue in report_json["schema_errors"]))

    def test_duplicate_prediction_id_is_schema_error(self) -> None:
        code, report_json, _report_text = self.run_evaluator(
            [scenario("duplicate")],
            [prediction("duplicate"), prediction("duplicate")],
        )

        self.assertEqual(code, 1)
        self.assertTrue(any("duplicate prediction id" in issue for issue in report_json["schema_errors"]))

    def test_explanation_missing_is_reported(self) -> None:
        code, report_json, report_text = self.run_evaluator(
            [scenario()],
            [prediction(explanation="   ")],
        )

        self.assertEqual(code, 0)
        self.assertEqual(report_json["metrics"]["Route Explanation Present Rate"], 0.0)
        self.assertIn("missing explanation", report_text)

    def test_invalid_json_line_is_schema_error(self) -> None:
        evaluator = load_evaluator()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            scenarios_path = root / "scenarios.jsonl"
            predictions_path = root / "predictions.jsonl"
            report_path = root / "report.md"
            json_report_path = root / "report.json"
            scenarios_path.write_text('{"id": "ok"}\n{not json}\n', encoding="utf-8")
            write_jsonl(predictions_path, [])

            with redirect_stderr(io.StringIO()):
                code = evaluator.main(
                    [
                        "--scenarios",
                        str(scenarios_path),
                        "--predictions",
                        str(predictions_path),
                        "--report",
                        str(report_path),
                        "--json-report",
                        str(json_report_path),
                    ]
                )

            report_json = json.loads(json_report_path.read_text(encoding="utf-8"))
            self.assertEqual(code, 1)
            self.assertTrue(any("invalid JSON" in issue for issue in report_json["schema_errors"]))


if __name__ == "__main__":
    unittest.main()
