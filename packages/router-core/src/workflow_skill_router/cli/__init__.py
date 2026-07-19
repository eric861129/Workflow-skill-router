from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .evaluation import configure_evaluation_parser, run_evaluation_cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="workflow-skill-router",
        description="Workflow Skill Router V2",
    )
    subparsers = parser.add_subparsers(dest="command")
    serve = subparsers.add_parser("serve-jsonl", help="Serve the JSONL runtime bridge")
    serve.add_argument("--database", required=True)
    doctor = subparsers.add_parser("doctor", help="Inspect Python and plugin runtime readiness")
    doctor.add_argument("--database")
    subparsers.add_parser("status", help="Inspect Router and Goal status")
    subparsers.add_parser("plan", help="Plan Single, Phased, or Managed Goal work")
    subparsers.add_parser("validate-route", help="Validate a JIT route and activation")
    evaluation = subparsers.add_parser("evaluation", help="Run or inspect evaluation artifacts")
    configure_evaluation_parser(evaluation)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "serve-jsonl":
        from workflow_skill_router.bridge import serve
        from workflow_skill_router.local_control import LocalControlPlaneService
        from workflow_skill_router.tool_dispatch import ToolDispatcher

        service = LocalControlPlaneService(Path(args.database))
        serve(sys.stdin, sys.stdout, ToolDispatcher(service))
        return 0
    if args.command == "doctor":
        from workflow_skill_router.runtime_readiness import readiness_document

        print(json.dumps({
            "runtime_status": "core-ready",
            "runtime_profile": "bundled-local-r0",
            "conformance_profile": None,
            "fallback_mode": "skill-only-fallback",
            "content_preflight": "unobservable",
            "telemetry_enabled": False,
            "tools": readiness_document(),
        }, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "evaluation":
        return run_evaluation_cli(args)
    print("This command requires Plugin/MCP host context; use the bundled runtime tools.")
    return 2


__all__ = ["build_parser", "main"]
