from __future__ import annotations

import argparse
import json
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
        from workflow_skill_router.service_models import RouterStatusView
        from workflow_skill_router.tool_dispatch import ToolDispatcher

        class BootstrapControlService:
            def get_router_status(self, query):
                return RouterStatusView(query.goal_binding_id, query.workflow_run_id, 0, None, False)

            def __getattr__(self, name):
                def unavailable(command):
                    del command
                    raise RuntimeError("verified-runtime-initialization-required")
                return unavailable

        serve(sys.stdin, sys.stdout, ToolDispatcher(BootstrapControlService()))
        return 0
    if args.command == "doctor":
        print(json.dumps({
            "runtime_status": "core-ready",
            "conformance_profile": None,
            "fallback_mode": "skill-only-fallback",
            "content_preflight": "unobservable",
            "telemetry_enabled": False,
        }, ensure_ascii=False, sort_keys=True))
        return 0
    print("此命令需要 Plugin/MCP host context；純 CLI 不會自行授予 runtime 權限。")
    return 2


__all__ = ["build_parser", "main"]
