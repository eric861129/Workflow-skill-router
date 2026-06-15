#!/usr/bin/env python3
"""Audit the public repository surface before publishing.

This is a small CLI wrapper around the public-readiness checks implemented in
validate-router.py. Keeping this command separate makes the release gate easier
to discover while preserving the original validator command.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_validator_module() -> ModuleType:
    validator_path = Path(__file__).with_name("validate-router.py")
    spec = importlib.util.spec_from_file_location("workflow_router_validator", validator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load validator module from {validator_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Audit Workflow Skill Router public-readiness before publishing."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Repository root to audit. Defaults to the current working directory.",
    )
    args = parser.parse_args(argv)

    validator = load_validator_module()
    issues = validator.validate_public_readiness(Path(args.path))
    if issues:
        for issue in issues:
            print(issue)
        return 1

    print("OK: public-readiness audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
