#!/usr/bin/env python3
"""Evaluate workflow-skill-router predictions against scenario expectations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


METRIC_NAMES = [
    "Scenario Count",
    "Prediction Count",
    "Primary Accuracy",
    "Supporting Recall",
    "Supporting Precision",
    "Exact Route Match Rate",
    "Forbidden Skill Violation Rate",
    "Max Skill Count Violation Rate",
    "Over-routing Rate",
    "Average Selected Skill Count",
    "Route Explanation Present Rate",
    "Missing Prediction Count",
    "Unknown Prediction Count",
]


def normalize_skill(value: Any) -> str:
    return str(value).strip().lower()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def as_string(value: Any, field: str, errors: list[str], location: str, *, required: bool = True) -> str:
    if isinstance(value, str):
        return value
    if value is None and not required:
        return ""
    errors.append(f"{location}: field '{field}' must be a string")
    return ""


def as_bool(value: Any, field: str, errors: list[str], location: str) -> bool:
    if isinstance(value, bool):
        return value
    errors.append(f"{location}: field '{field}' must be a boolean")
    return False


def as_int(value: Any, field: str, errors: list[str], location: str) -> int:
    if isinstance(value, int) and value > 0:
        return value
    errors.append(f"{location}: field '{field}' must be a positive integer")
    return 4


def as_string_list(value: Any, field: str, errors: list[str], location: str) -> list[str]:
    if value is None:
        errors.append(f"{location}: field '{field}' must be a list")
        return []
    if not isinstance(value, list):
        errors.append(f"{location}: field '{field}' must be a list")
        return []

    result: list[str] = []
    for index, item in enumerate(value):
        if isinstance(item, str):
            result.append(item)
        else:
            errors.append(f"{location}: field '{field}[{index}]' must be a string")
    return result


def load_jsonl(path: Path, label: str) -> tuple[list[tuple[int, dict[str, Any]]], list[str]]:
    records: list[tuple[int, dict[str, Any]]] = []
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [], [f"{path}: failed to read {label}: {exc}"]

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{line_number}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(parsed, dict):
            errors.append(f"{path}:{line_number}: {label} record must be a JSON object")
            continue
        records.append((line_number, parsed))
    return records, errors


def validate_scenarios(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    raw_records, errors = load_jsonl(path, "scenario")
    scenarios: list[dict[str, Any]] = []
    seen: dict[str, int] = {}

    for line_number, row in raw_records:
        location = f"{path}:{line_number}"
        scenario_id = as_string(row.get("id"), "id", errors, location).strip()
        if not scenario_id:
            errors.append(f"{location}: field 'id' must not be empty")
            continue
        if scenario_id in seen:
            errors.append(f"{location}: duplicate scenario id '{scenario_id}' first seen on line {seen[scenario_id]}")
            continue
        seen[scenario_id] = line_number

        expected = row.get("expected")
        if not isinstance(expected, dict):
            errors.append(f"{location}: field 'expected' must be an object")
            continue

        primary = normalize_skill(as_string(expected.get("primary"), "expected.primary", errors, location))
        if not primary:
            errors.append(f"{location}: field 'expected.primary' must not be empty")
        scenario = {
            "id": scenario_id,
            "task": as_string(row.get("task"), "task", errors, location),
            "context": as_string(row.get("context"), "context", errors, location, required=False),
            "expected": {
                "primary": primary,
                "supporting": [normalize_skill(item) for item in as_string_list(expected.get("supporting"), "expected.supporting", errors, location)],
            },
            "forbidden": [normalize_skill(item) for item in as_string_list(row.get("forbidden", []), "forbidden", errors, location)],
            "max_skills": as_int(row.get("max_skills", 4), "max_skills", errors, location),
            "tags": as_string_list(row.get("tags", []), "tags", errors, location),
            "notes": as_string(row.get("notes", ""), "notes", errors, location, required=False),
        }
        scenarios.append(scenario)

    return scenarios, errors


def validate_predictions(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    raw_records, errors = load_jsonl(path, "prediction")
    predictions: list[dict[str, Any]] = []
    seen: dict[str, int] = {}

    for line_number, row in raw_records:
        location = f"{path}:{line_number}"
        prediction_id = as_string(row.get("id"), "id", errors, location).strip()
        if not prediction_id:
            errors.append(f"{location}: field 'id' must not be empty")
            continue
        if prediction_id in seen:
            errors.append(f"{location}: duplicate prediction id '{prediction_id}' first seen on line {seen[prediction_id]}")
            continue
        seen[prediction_id] = line_number

        selected = row.get("selected")
        if not isinstance(selected, dict):
            errors.append(f"{location}: field 'selected' must be an object")
            continue

        primary = normalize_skill(as_string(selected.get("primary"), "selected.primary", errors, location))
        if not primary:
            errors.append(f"{location}: field 'selected.primary' must not be empty")
        prediction = {
            "id": prediction_id,
            "selected": {
                "primary": primary,
                "supporting": [normalize_skill(item) for item in as_string_list(selected.get("supporting"), "selected.supporting", errors, location)],
            },
            "explanation": as_string(row.get("explanation"), "explanation", errors, location),
            "stage_split": as_bool(row.get("stage_split"), "stage_split", errors, location),
        }
        predictions.append(prediction)

    return predictions, errors


def ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def format_metric_value(value: Any) -> str:
    if isinstance(value, float):
        if value == int(value):
            return f"{value:.1f}"
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def summarize_set(values: list[str] | set[str]) -> str:
    if not values:
        return "-"
    return ", ".join(sorted(values))


def evaluate(scenarios: list[dict[str, Any]], predictions: list[dict[str, Any]], schema_errors: list[str]) -> dict[str, Any]:
    scenario_by_id = {scenario["id"]: scenario for scenario in scenarios}
    prediction_by_id = {prediction["id"]: prediction for prediction in predictions}

    missing_ids = sorted(scenario_by_id.keys() - prediction_by_id.keys())
    unknown_ids = sorted(prediction_by_id.keys() - scenario_by_id.keys())

    per_scenario: list[dict[str, Any]] = []
    failed_scenarios: list[dict[str, str]] = []
    forbidden_violations: list[dict[str, Any]] = []
    max_skill_violations: list[dict[str, Any]] = []

    primary_matches = 0
    recall_sum = 0.0
    precision_sum = 0.0
    exact_matches = 0
    forbidden_count = 0
    max_count = 0
    over_routing_count = 0
    selected_count_sum = 0
    explanation_count = 0

    for scenario in scenarios:
        scenario_id = scenario["id"]
        prediction = prediction_by_id.get(scenario_id)
        if prediction is None:
            failed_scenarios.append(
                {
                    "id": scenario_id,
                    "issue": "missing prediction",
                    "expected": route_label(scenario["expected"]["primary"], scenario["expected"]["supporting"]),
                    "actual": "-",
                }
            )
            per_scenario.append(
                {
                    "id": scenario_id,
                    "primary": "missing",
                    "supporting_recall": 0.0,
                    "forbidden": "-",
                    "max_skills": f"missing / {scenario['max_skills']}",
                    "pass": False,
                    "issues": ["missing prediction"],
                }
            )
            continue

        expected_primary = scenario["expected"]["primary"]
        expected_supporting = set(scenario["expected"]["supporting"])
        selected_primary = prediction["selected"]["primary"]
        selected_supporting = set(prediction["selected"]["supporting"])
        selected_skills = {selected_primary, *selected_supporting} if selected_primary else set(selected_supporting)
        selected_count = (1 if selected_primary else 0) + len(selected_supporting)
        expected_count = (1 if expected_primary else 0) + len(expected_supporting)

        primary_match = selected_primary == expected_primary
        supporting_hits = expected_supporting & selected_supporting
        supporting_recall = ratio(len(supporting_hits), len(expected_supporting)) if expected_supporting else 1.0
        supporting_precision = ratio(len(supporting_hits), len(selected_supporting)) if selected_supporting else 1.0
        exact_match = primary_match and selected_supporting == expected_supporting
        forbidden_hit = sorted(selected_skills & set(scenario["forbidden"]))
        max_violation = selected_count > scenario["max_skills"]
        over_routing = selected_count > expected_count or max_violation
        explanation_present = bool(prediction["explanation"].strip())

        primary_matches += 1 if primary_match else 0
        recall_sum += supporting_recall
        precision_sum += supporting_precision
        exact_matches += 1 if exact_match else 0
        forbidden_count += 1 if forbidden_hit else 0
        max_count += 1 if max_violation else 0
        over_routing_count += 1 if over_routing else 0
        selected_count_sum += selected_count
        explanation_count += 1 if explanation_present else 0

        issues: list[str] = []
        if not primary_match:
            issues.append("primary mismatch")
        if supporting_recall < 1.0:
            issues.append("supporting skill missing")
        if forbidden_hit:
            issues.append("forbidden skill selected")
            forbidden_violations.append({"id": scenario_id, "forbidden_skills_hit": forbidden_hit})
        if max_violation:
            issues.append("max skills exceeded")
            max_skill_violations.append(
                {"id": scenario_id, "max_skills": scenario["max_skills"], "actual_count": selected_count}
            )
        if over_routing and "max skills exceeded" not in issues:
            issues.append("over-routing")
        if not explanation_present:
            issues.append("missing explanation")

        if issues:
            failed_scenarios.append(
                {
                    "id": scenario_id,
                    "issue": "; ".join(issues),
                    "expected": route_label(expected_primary, expected_supporting),
                    "actual": route_label(selected_primary, selected_supporting),
                }
            )

        per_scenario.append(
            {
                "id": scenario_id,
                "primary": "pass" if primary_match else "fail",
                "supporting_recall": supporting_recall,
                "forbidden": summarize_set(forbidden_hit),
                "max_skills": f"{selected_count} / {scenario['max_skills']}",
                "pass": not issues,
                "issues": issues,
            }
        )

    for prediction_id in unknown_ids:
        failed_scenarios.append(
            {
                "id": prediction_id,
                "issue": "unknown prediction",
                "expected": "-",
                "actual": route_label(
                    prediction_by_id[prediction_id]["selected"]["primary"],
                    prediction_by_id[prediction_id]["selected"]["supporting"],
                ),
            }
        )

    scenario_count = len(scenarios)
    prediction_count = len(predictions)
    metrics = {
        "Scenario Count": scenario_count,
        "Prediction Count": prediction_count,
        "Primary Accuracy": ratio(primary_matches, scenario_count),
        "Supporting Recall": ratio(recall_sum, scenario_count),
        "Supporting Precision": ratio(precision_sum, scenario_count),
        "Exact Route Match Rate": ratio(exact_matches, scenario_count),
        "Forbidden Skill Violation Rate": ratio(forbidden_count, scenario_count),
        "Max Skill Count Violation Rate": ratio(max_count, scenario_count),
        "Over-routing Rate": ratio(over_routing_count, scenario_count),
        "Average Selected Skill Count": ratio(selected_count_sum, scenario_count),
        "Route Explanation Present Rate": ratio(explanation_count, scenario_count),
        "Missing Prediction Count": len(missing_ids),
        "Unknown Prediction Count": len(unknown_ids),
    }

    return {
        "metrics": metrics,
        "schema_errors": schema_errors,
        "missing_predictions": missing_ids,
        "unknown_predictions": unknown_ids,
        "failed_scenarios": failed_scenarios,
        "forbidden_skill_violations": forbidden_violations,
        "max_skill_count_violations": max_skill_violations,
        "per_scenario": per_scenario,
    }


def route_label(primary: str, supporting: list[str] | set[str]) -> str:
    supporting_label = summarize_set(supporting)
    return f"primary={primary}; supporting={supporting_label}"


def markdown_table(headers: list[str], rows: list[list[Any]], right_align: set[int] | None = None) -> list[str]:
    right_align = right_align or set()
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---:" if index in right_align else "---" for index, _ in enumerate(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return lines


def render_report(result: dict[str, Any]) -> str:
    lines: list[str] = ["# Routing Evaluation Report", ""]

    lines.extend(["## Summary", ""])
    lines.extend(
        markdown_table(
            ["Metric", "Value"],
            [[name, format_metric_value(result["metrics"][name])] for name in METRIC_NAMES],
            right_align={1},
        )
    )
    lines.append("")

    if result["schema_errors"]:
        lines.extend(["## Schema Errors", ""])
        for issue in result["schema_errors"]:
            lines.append(f"- {issue}")
        lines.append("")

    lines.extend(["## Failed Scenarios", ""])
    failed_rows = [
        [item["id"], item["issue"], item["expected"], item["actual"]]
        for item in result["failed_scenarios"]
    ]
    lines.extend(markdown_table(["ID", "Issue", "Expected", "Actual"], failed_rows or [["-", "-", "-", "-"]]))
    lines.append("")

    lines.extend(["## Forbidden Skill Violations", ""])
    forbidden_rows = [
        [item["id"], summarize_set(item["forbidden_skills_hit"])]
        for item in result["forbidden_skill_violations"]
    ]
    lines.extend(markdown_table(["ID", "Forbidden Skills Hit"], forbidden_rows or [["-", "-"]]))
    lines.append("")

    lines.extend(["## Max Skill Count Violations", ""])
    max_rows = [
        [item["id"], item["max_skills"], item["actual_count"]]
        for item in result["max_skill_count_violations"]
    ]
    lines.extend(markdown_table(["ID", "Max Skills", "Actual Count"], max_rows or [["-", "-", "-"]], right_align={1, 2}))
    lines.append("")

    lines.extend(["## Per-scenario Results", ""])
    scenario_rows = [
        [
            item["id"],
            item["primary"],
            format_metric_value(item["supporting_recall"]),
            item["forbidden"],
            item["max_skills"],
            "yes" if item["pass"] else "no",
        ]
        for item in result["per_scenario"]
    ]
    lines.extend(
        markdown_table(
            ["ID", "Primary", "Supporting Recall", "Forbidden", "Max Skills", "Pass"],
            scenario_rows or [["-", "-", "-", "-", "-", "-"]],
            right_align={2},
        )
    )
    lines.append("")
    return "\n".join(lines)


def should_fail(result: dict[str, Any], *, fail_on_violations: bool, strict: bool) -> bool:
    if result["schema_errors"]:
        return True

    metrics = result["metrics"]
    if fail_on_violations and (
        metrics["Forbidden Skill Violation Rate"] > 0
        or metrics["Max Skill Count Violation Rate"] > 0
        or metrics["Missing Prediction Count"] > 0
        or metrics["Unknown Prediction Count"] > 0
    ):
        return True

    if strict:
        for item in result["per_scenario"]:
            issues = set(item["issues"])
            if "primary mismatch" in issues or "supporting skill missing" in issues:
                return True

    return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate routed skill predictions against JSONL scenarios.")
    parser.add_argument("--scenarios", required=True, type=Path, help="Path to scenarios JSONL.")
    parser.add_argument("--predictions", required=True, type=Path, help="Path to predictions JSONL.")
    parser.add_argument("--report", required=True, type=Path, help="Path for the Markdown report.")
    parser.add_argument("--json-report", type=Path, help="Optional path for a machine-readable JSON report.")
    parser.add_argument(
        "--fail-on-violations",
        action="store_true",
        help="Exit non-zero for forbidden skills, max skill violations, missing predictions, or unknown predictions.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when primary skills mismatch or expected supporting skills are missing.",
    )
    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    scenarios, scenario_errors = validate_scenarios(args.scenarios)
    predictions, prediction_errors = validate_predictions(args.predictions)
    result = evaluate(scenarios, predictions, [*scenario_errors, *prediction_errors])

    write_text(args.report, render_report(result))
    if args.json_report:
        write_text(args.json_report, json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    if result["schema_errors"]:
        for issue in result["schema_errors"]:
            print(issue, file=sys.stderr)

    return 1 if should_fail(result, fail_on_violations=args.fail_on_violations, strict=args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
