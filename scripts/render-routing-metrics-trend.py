#!/usr/bin/env python3
"""Validate and render public routing metrics trend data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = [
    "version",
    "date",
    "scenario_count",
    "primary_accuracy",
    "supporting_recall",
    "supporting_precision",
    "forbidden_violation_rate",
    "max_skill_count_violation_rate",
    "over_routing_rate",
]

RATE_FIELDS = [
    "primary_accuracy",
    "supporting_recall",
    "supporting_precision",
    "forbidden_violation_rate",
    "max_skill_count_violation_rate",
    "over_routing_rate",
]


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [], [f"{path}: failed to read metrics history: {exc}"]

    seen_versions: set[str] = set()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        location = f"{path}:{line_number}"
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{location}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(row, dict):
            errors.append(f"{location}: metrics history row must be an object")
            continue

        missing = [field for field in REQUIRED_FIELDS if field not in row]
        if missing:
            errors.append(f"{location}: missing fields: {', '.join(missing)}")
            continue

        version = row["version"]
        if not isinstance(version, str) or not version.strip():
            errors.append(f"{location}: version must be a non-empty string")
        elif version in seen_versions:
            errors.append(f"{location}: duplicate version '{version}'")
        seen_versions.add(str(version))

        if not isinstance(row["date"], str) or not row["date"].strip():
            errors.append(f"{location}: date must be a non-empty string")
        if not isinstance(row["scenario_count"], int) or row["scenario_count"] <= 0:
            errors.append(f"{location}: scenario_count must be a positive integer")

        for field in RATE_FIELDS:
            value = row[field]
            if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
                errors.append(f"{location}: {field} must be a number between 0 and 1")
            else:
                row[field] = round(float(value), 4)

        if "notes" in row and not isinstance(row["notes"], str):
            errors.append(f"{location}: notes must be a string when present")

        rows.append(row)

    rows.sort(key=lambda row: row["date"])
    return rows, errors


def percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Routing Metrics Trends",
        "",
        "This public history tracks the small benchmark used by Workflow Skill Router releases. It is intentionally lightweight: the goal is to show direction, coverage, and violation rates without claiming model-wide performance.",
        "",
        "| Version | Date | Scenarios | Primary accuracy | Supporting recall | Supporting precision | Forbidden violations | Max skill violations | Over-routing |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {version} | {date} | {scenario_count} | {primary_accuracy} | {supporting_recall} | {supporting_precision} | {forbidden_violation_rate} | {max_skill_count_violation_rate} | {over_routing_rate} |".format(
                version=row["version"],
                date=row["date"],
                scenario_count=row["scenario_count"],
                primary_accuracy=percent(row["primary_accuracy"]),
                supporting_recall=percent(row["supporting_recall"]),
                supporting_precision=percent(row["supporting_precision"]),
                forbidden_violation_rate=percent(row["forbidden_violation_rate"]),
                max_skill_count_violation_rate=percent(row["max_skill_count_violation_rate"]),
                over_routing_rate=percent(row["over_routing_rate"]),
            )
        )

    lines.extend(
        [
            "",
            "## How to update",
            "",
            "1. Run `python scripts/evaluate-routing.py` against the release benchmark.",
            "2. Add one row to `evaluation/metrics-history.jsonl`.",
            "3. Run `python scripts/render-routing-metrics-trend.py`.",
            "4. Commit the generated site data and this markdown summary.",
            "",
            "The history keeps the existing evaluator JSON report compatible. Trend fields are duplicated in snake_case so the documentation site can render them without parsing report labels.",
            "",
        ]
    )
    return "\n".join(lines)


def build_site_data(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "metric_fields": RATE_FIELDS,
        "history": rows,
    }


def write_or_check(path: Path, content: str, check: bool, errors: list[str]) -> None:
    if check:
        try:
            existing = path.read_text(encoding="utf-8")
        except OSError:
            errors.append(f"{path}: generated file is missing")
            return
        if existing != content:
            errors.append(f"{path}: generated file is out of date")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", default="evaluation/metrics-history.jsonl", help="Metrics history JSONL path.")
    parser.add_argument("--site-out", default="site/src/data/routing-metrics-history.generated.json")
    parser.add_argument("--markdown-out", default="docs/routing-metrics-trends.md")
    parser.add_argument("--check", action="store_true", help="Fail if generated outputs are out of date.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    rows, errors = load_jsonl(Path(args.history))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    site_content = json.dumps(build_site_data(rows), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    markdown_content = render_markdown(rows)

    check_errors: list[str] = []
    write_or_check(Path(args.site_out), site_content, args.check, check_errors)
    write_or_check(Path(args.markdown_out), markdown_content, args.check, check_errors)
    if check_errors:
        for error in check_errors:
            print(error, file=sys.stderr)
        return 1

    action = "Checked" if args.check else "Rendered"
    print(f"{action} routing metrics trend for {len(rows)} releases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
