from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from workflow_skill_router.memory.models import MemoryPolicyError, MemoryScope
from workflow_skill_router.memory.observations import MatcherSeed, RouteObservationError
from workflow_skill_router.memory.service import (
    MemoryCommandConflict,
    RememberWorkflowCommand,
    WorkflowMemoryService,
)
from workflow_skill_router.memory.store import MemoryStoreError
from workflow_skill_router.memory.workflow_reader import MemoryRequestContext
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

    remember = commands.add_parser(
        "remember",
        help="Record one eligible completed Workflow using structured matcher evidence",
    )
    remember.add_argument("--database", type=Path, required=True)
    remember.add_argument("--data-dir", type=Path)
    remember.add_argument("--workspace", type=Path)
    remember.add_argument("--workflow-run", required=True)
    remember.add_argument("--session-id", required=True)
    remember.add_argument("--actor", required=True)
    remember.add_argument("--runtime-policy-snapshot-id", required=True)
    remember.add_argument("--keyword", action="append", default=[])
    remember.add_argument("--domain", action="append", default=[])
    remember.add_argument("--tag", action="append", default=[])
    remember.add_argument(
        "--matcher-source",
        choices=("trusted-routing-context", "existing-profile", "user-explicit"),
    )
    remember.add_argument(
        "--target",
        choices=("managed-personal", "managed-workspace-local", "user-personal", "workspace-file"),
        required=True,
    )
    remember.add_argument("--risk", choices=("r0", "r1", "r2", "r3"), required=True)
    remember.add_argument(
        "--side-effect",
        choices=("none", "known-success", "known-failure", "unknown"),
        required=True,
    )
    remember.add_argument(
        "--one-shot",
        choices=("none", "remember-once", "no-memory"),
        default="none",
    )
    remember.add_argument("--idempotency-key", required=True)
    remember.add_argument("--correlation-id", required=True)

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

        if args.memory_command == "remember":
            matcher_present = bool(args.keyword or args.domain or args.tag or args.matcher_source)
            if matcher_present and args.matcher_source is None:
                raise RouteObservationError("matcher-source-required")
            matcher = None if not matcher_present else MatcherSeed(
                tuple(args.keyword),
                tuple(args.domain),
                tuple(args.tag),
                args.matcher_source,
            )
            service = WorkflowMemoryService(args.database, data_dir=args.data_dir)
            result = service.remember_workflow(RememberWorkflowCommand(
                context=MemoryRequestContext(
                    args.session_id, args.actor, args.runtime_policy_snapshot_id
                ),
                workflow_run_id=args.workflow_run,
                workspace_root=args.workspace,
                matcher_seed=matcher,
                target_profile_class=args.target,
                risk_class=args.risk,
                side_effect_outcome=args.side_effect,
                one_shot=args.one_shot,
                idempotency_key=args.idempotency_key,
                correlation_id=args.correlation_id,
            ))
            _print(result.to_dict())
            return 0 if result.status in {"recorded", "not-recorded", "memory-disabled"} else 2

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
    except (MemoryPolicyError, RouteObservationError, MemoryStoreError, MemoryCommandConflict, ValueError) as error:
        _print(
            {"status": "invalid", "error": str(error)},
            output=sys.stderr,
        )
        return 2


__all__ = ["configure_memory_parser", "run_memory_cli"]
