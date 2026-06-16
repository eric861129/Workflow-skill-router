#!/usr/bin/env python3
"""Validate public route case submissions."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from route_case_tools import load_route_cases


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "route_cases_dir",
        nargs="?",
        default="route-cases",
        help="Directory containing route case JSON files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    cases, errors = load_route_cases(Path(args.route_cases_dir))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"Validated {len(cases)} public route cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
