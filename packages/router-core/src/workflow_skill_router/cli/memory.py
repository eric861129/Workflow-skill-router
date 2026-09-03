from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from workflow_skill_router.memory.models import MemoryPolicyError, MemoryScope
from workflow_skill_router.memory.policy_io import (
    MemoryPolicyRepository,
    PolicyLoadResult,
)
from workflow_skill_router.memory.policy_resolver import (
    EffectiveMemoryPolicy,
    resolution_steps,
    resolve_effective_policy,
)


def configure_memory_parser(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="memory_command", required=True)

    status = commands.add_parser(
        "status",
        help="Show the effective default-off Workflow Memory policy",
    )
    status.add_argument("--data-dir", type=Path)
    status.add_argument("--workspace", type=Path)

    policy = commands.add_parser(
        "policy",
        help="Validate or explain Workflow Memory policy resolution",
    )
    policy_commands = policy.add_subparsers(dest="memory_policy_command", required=True)

    validate = policy_commands.add_parser(
        "validate",
        help="Validate one explicit JSON or restricted YAML policy file",
    )
    validate.add_argument("path", type=Path)
    validate.add_argument(
        "--scope",
        choices=(MemoryScope.PERSONAL.value, MemoryScope.WORKSPACE.value),
        required=True,
    )
    validate.add_argument("--data-dir", type=Path)

    explain = policy_commands.add_parser(
        "explain",
        help="Explain Personal ceiling and Workspace restriction resolution",
    )
    explain.add_argument("--data-dir", type=Path)
    explain.add_argument("--workspace", type=Path)


def _print(value: object, *, output=sys.stdout) -> None:
    reconfigure = getattr(output, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")
    print(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        file=output,
    )


def _workspace_public(result: PolicyLoadResult | None) -> dict[str, object]:
    if result is None:
        return {
            "status": "not-requested",
            "reason_codes": [],
            "source": None,
        }
    return result.to_public_dict()


def _resolve_from_args(
    args: argparse.Namespace,
) -> tuple[
    MemoryPolicyRepository,
    PolicyLoadResult,
    PolicyLoadResult | None,
    EffectiveMemoryPolicy,
]:
    repository = MemoryPolicyRepository(getattr(args, "data_dir", None))
    personal = repository.inspect_personal()
    workspace_root = getattr(args, "workspace", None)
    workspace = (
        None
        if workspace_root is None
        else repository.inspect_workspace(workspace_root)
    )
    effective = resolve_effective_policy(
        personal=personal,
        workspace=workspace,
    )
    return repository, personal, workspace, effective


def run_memory_cli(args: argparse.Namespace) -> int:
    try:
        if args.memory_command == "status":
            repository, _, _, effective = _resolve_from_args(args)
            _print({
                "status": "ready",
                **effective.to_public_dict(),
                "memory_store_exists": repository.memory_store_exists(),
            })
            return 0

        if args.memory_command == "policy" and args.memory_policy_command == "validate":
            repository = MemoryPolicyRepository(args.data_dir)
            policy = repository.validate_explicit_file(
                args.path,
                MemoryScope(args.scope),
            )
            _print({
                "status": "valid",
                "policy_id": policy.policy_id,
                "scope": policy.scope.value,
                "mode": policy.mode.value,
                "policy_digest": policy.policy_digest,
            })
            return 0

        if args.memory_command == "policy" and args.memory_policy_command == "explain":
            repository, personal, workspace, effective = _resolve_from_args(args)
            _print({
                "status": "ready",
                "personal_policy": personal.to_public_dict(),
                "workspace_policy": _workspace_public(workspace),
                "effective_policy": {
                    **effective.to_public_dict(),
                    "memory_store_exists": repository.memory_store_exists(),
                },
                "resolution_steps": list(
                    resolution_steps(personal, workspace, effective)
                ),
            })
            return 0
        raise RuntimeError("unsupported-memory-command")
    except MemoryPolicyError as error:
        _print(
            {"status": "invalid", "error": str(error)},
            output=sys.stderr,
        )
        return 2


__all__ = ["configure_memory_parser", "run_memory_cli"]
