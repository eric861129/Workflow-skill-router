from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="workflow-skill-router", description="Workflow Skill Router V2")
    sub = parser.add_subparsers(dest="command")
    serve = sub.add_parser("serve-jsonl", help="啟動長存 JSONL bridge")
    serve.add_argument("--database", required=True)
    doctor = sub.add_parser("doctor", help="檢查 Python、runtime 與 Plugin 能力")
    doctor.add_argument("--database")
    sub.add_parser("status", help="讀取 Router/Goal 狀態")
    sub.add_parser("plan", help="建立 Single、Phased 或 Managed Goal 計畫")
    sub.add_parser("validate-route", help="驗證 JIT route 與 single-use activation")
    evaluation = sub.add_parser("evaluation", help="真實模型評測與 artifact 管理")
    evaluation_sub = evaluation.add_subparsers(dest="evaluation_command")
    for name in ("run", "import", "compare", "export", "publish", "export-status"):
        evaluation_sub.add_parser(name)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(); return 0
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
    print("此命令需要 Plugin/MCP host context；純 CLI 不會自行授予 runtime 權限。")
    return 2


__all__ = ["build_parser", "main"]
