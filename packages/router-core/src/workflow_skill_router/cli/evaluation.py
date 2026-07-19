from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from workflow_skill_router.evaluation.adapter_registry import AdapterRegistry


EVALUATION_COMMANDS = ("run", "import", "compare", "export", "publish", "export-status")
EVIDENCE_CLASSES = ("reference-driver", "fresh-model-execution")


def configure_evaluation_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="evaluation_command")
    run = subparsers.add_parser("run", help="Prepare a sealed evaluation run")
    run.add_argument("--profile", required=True, choices=("contract", "behavior", "outcome"))
    run.add_argument("--evidence-class", required=True, choices=EVIDENCE_CLASSES)
    run.add_argument("--adapter", required=True, choices=("subprocess",))
    run.add_argument("--adapter-executable", required=True)
    run.add_argument("--adapter-arg", action="append", default=[])
    run.add_argument("--timeout-seconds", type=int, default=120)
    run.add_argument("--maximum-output-bytes", type=int, default=1_048_576)
    run.add_argument("--repeats", type=int, default=3)
    run.add_argument("--confirm-live-run", action="store_true")
    for name in EVALUATION_COMMANDS[1:]:
        subparsers.add_parser(name)


def run_evaluation_cli(args: argparse.Namespace) -> int:
    if args.evaluation_command != "run":
        print("This evaluation command requires a configured host runtime.", file=sys.stderr)
        return 2
    executable = Path(args.adapter_executable)
    if not executable.is_absolute():
        print("--adapter-executable must be an absolute path.", file=sys.stderr)
        return 2
    if args.repeats < 1 or args.repeats > 20:
        print("--repeats must be between 1 and 20.", file=sys.stderr)
        return 2
    if args.profile in ("behavior", "outcome") and args.repeats < 3:
        print("Behavior and outcome profiles require at least 3 repeats.", file=sys.stderr)
        return 2
    live_run = args.evidence_class == "fresh-model-execution"
    if live_run and args.profile in ("behavior", "outcome") and not args.confirm_live_run:
        print("Behavior and outcome live runs require --confirm-live-run.", file=sys.stderr)
        return 2

    command = (args.adapter_executable, *args.adapter_arg)
    AdapterRegistry.from_subprocess_command(
        command,
        timeout_seconds=args.timeout_seconds,
        maximum_output_bytes=args.maximum_output_bytes,
    )
    manifest = {
        "adapter": args.adapter,
        "adapter_command": list(command),
        "dry_run": True,
        "evidence_class": args.evidence_class,
        "evidence_class_locked": args.evidence_class == "reference-driver",
        "live_run": live_run,
        "live_run_confirmed": bool(args.confirm_live_run),
        "maximum_output_bytes": args.maximum_output_bytes,
        "profile": args.profile,
        "repeats": args.repeats,
        "timeout_seconds": args.timeout_seconds,
    }
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0
