#!/usr/bin/env python3
"""Generate site gallery data and evaluator scenarios from public route cases."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from route_case_tools import build_evaluation_scenarios, build_gallery_data, json_dumps, load_route_cases


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route-cases-dir", default="route-cases", help="Directory containing route case JSON files.")
    parser.add_argument(
        "--gallery-out",
        default="site/src/data/route-cases.generated.json",
        help="Generated gallery JSON output path.",
    )
    parser.add_argument(
        "--scenarios-out",
        default="evaluation/route-cases.generated.jsonl",
        help="Generated evaluator scenarios JSONL output path.",
    )
    parser.add_argument("--check", action="store_true", help="Fail if generated outputs are out of date.")
    return parser.parse_args(argv)


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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    cases, errors = load_route_cases(Path(args.route_cases_dir))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    gallery_content = json_dumps(build_gallery_data(cases))
    scenarios = build_evaluation_scenarios(cases)
    scenarios_content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in scenarios)

    check_errors: list[str] = []
    write_or_check(Path(args.gallery_out), gallery_content, args.check, check_errors)
    write_or_check(Path(args.scenarios_out), scenarios_content, args.check, check_errors)

    if check_errors:
        for error in check_errors:
            print(error, file=sys.stderr)
        return 1

    action = "Checked" if args.check else "Generated"
    print(f"{action} gallery data for {len(cases)} route cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
