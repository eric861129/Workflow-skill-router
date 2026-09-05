from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from workflow_skill_router.memory.models import MemoryPolicyError, MemoryScope
from workflow_skill_router.memory.observations import MatcherSeed, RouteObservationError
from workflow_skill_router.memory.analytics import HistorySummaryQuery, PurgeMemoryCommand
from workflow_skill_router.memory.feedback import RecordRouteFeedbackCommand, RouteFeedbackError
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

    feedback = commands.add_parser(
        "feedback",
        help="Record typed feedback for one remembered Workflow route",
    )
    feedback_commands = feedback.add_subparsers(
        dest="memory_feedback_command", required=True
    )
    feedback_record = feedback_commands.add_parser(
        "record", help="Record one typed route feedback event"
    )
    feedback_record.add_argument("--database", type=Path, required=True)
    feedback_record.add_argument("--data-dir", type=Path)
    feedback_record.add_argument("--workspace", type=Path)
    feedback_record.add_argument("--workflow-run", required=True)
    feedback_record.add_argument("--observation-id", required=True)
    feedback_record.add_argument("--session-id", required=True)
    feedback_record.add_argument("--actor", required=True)
    feedback_record.add_argument("--runtime-policy-snapshot-id", required=True)
    feedback_record.add_argument(
        "--type",
        choices=(
            "accepted", "corrected", "rejected", "support-rejected",
            "capability-unavailable", "gate-failed", "completed",
            "abandoned", "no-memory",
        ),
        required=True,
    )
    feedback_record.add_argument("--reason")
    feedback_record.add_argument("--correction-dimension", action="append", default=[])
    feedback_record.add_argument("--original-route-digest")
    feedback_record.add_argument("--corrected-route-digest")
    feedback_record.add_argument("--free-text")
    feedback_record.add_argument("--idempotency-key", required=True)
    feedback_record.add_argument("--correlation-id", required=True)

    history = commands.add_parser(
        "history",
        help="Summarize, export, or purge local Workflow Memory history",
    )
    history_commands = history.add_subparsers(
        dest="memory_history_command", required=True
    )

    def add_history_context(command: argparse.ArgumentParser) -> None:
        command.add_argument("--database", type=Path, required=True)
        command.add_argument("--data-dir", type=Path)
        command.add_argument("--session-id", required=True)
        command.add_argument("--actor", required=True)
        command.add_argument("--runtime-policy-snapshot-id", required=True)
        command.add_argument("--workspace-digest")
        command.add_argument("--route-signature-digest")

    history_summary = history_commands.add_parser(
        "summary", help="Compute deterministic local history metrics"
    )
    add_history_context(history_summary)

    history_export = history_commands.add_parser(
        "export", help="Write a canonical redacted history export"
    )
    add_history_context(history_export)
    history_export.add_argument("--output", type=Path, required=True)
    history_export.add_argument("--include-observations", action="store_true")

    history_purge = history_commands.add_parser(
        "purge", help="Purge history using an exact summary digest"
    )
    add_history_context(history_purge)
    history_purge.add_argument(
        "--scope",
        choices=(
            "history-only", "analytics-only", "candidates-only",
            "revisions-only", "managed-profiles-only", "all-memory-data",
        ),
        required=True,
    )
    history_purge.add_argument("--expected-summary-digest", required=True)
    history_purge.add_argument("--include-managed-profiles", action="store_true")
    history_purge.add_argument("--idempotency-key", required=True)
    history_purge.add_argument("--correlation-id", required=True)

    candidates = commands.add_parser(
        "candidates",
        help="Rebuild, list, inspect, or reject deterministic Workflow candidates",
    )
    candidate_commands = candidates.add_subparsers(dest="memory_candidate_command", required=True)
    candidate_rebuild = candidate_commands.add_parser("rebuild")
    candidate_rebuild.add_argument("--database", type=Path, required=True)
    candidate_rebuild.add_argument("--data-dir", type=Path)
    candidate_rebuild.add_argument("--workspace", type=Path)
    candidate_rebuild.add_argument("--scope", choices=("personal", "workspace"), default="personal")
    candidate_list = candidate_commands.add_parser("list")
    candidate_list.add_argument("--database", type=Path, required=True)
    candidate_list.add_argument("--data-dir", type=Path)
    candidate_list.add_argument("--workspace", type=Path)
    candidate_list.add_argument("--status")
    candidate_show = candidate_commands.add_parser("show")
    candidate_show.add_argument("candidate_id")
    candidate_show.add_argument("--database", type=Path, required=True)
    candidate_show.add_argument("--data-dir", type=Path)
    candidate_show.add_argument("--workspace", type=Path)
    candidate_reject = candidate_commands.add_parser("reject")
    candidate_reject.add_argument("candidate_id")
    candidate_reject.add_argument("--database", type=Path, required=True)
    candidate_reject.add_argument("--data-dir", type=Path)
    candidate_reject.add_argument("--workspace", type=Path)
    candidate_reject.add_argument("--reason", required=True)
    candidate_promote = candidate_commands.add_parser(
        "promote-eligible",
        help=(
            "Run one explicit local Automatic-mode promotion pass; "
            "this command does not start a background scheduler"
        ),
    )
    candidate_promote.add_argument("--database", type=Path, required=True)
    candidate_promote.add_argument("--data-dir", type=Path)
    candidate_promote.add_argument("--workspace", type=Path)
    candidate_promote.add_argument(
        "--scope", choices=("personal", "workspace"), default="personal"
    )
    candidate_promote.add_argument("--actor", required=True)
    candidate_promote.add_argument("--session-id", required=True)
    candidate_promote.add_argument("--idempotency-key", required=True)
    candidate_promote.add_argument("--correlation-id", required=True)
    candidate_promote.add_argument("--now")

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

        if args.memory_command == "feedback" and args.memory_feedback_command == "record":
            service = WorkflowMemoryService(args.database, data_dir=args.data_dir)
            result = service.record_route_feedback(RecordRouteFeedbackCommand(
                context=MemoryRequestContext(
                    args.session_id, args.actor, args.runtime_policy_snapshot_id
                ),
                workflow_run_id=args.workflow_run,
                workspace_root=args.workspace,
                observation_id=args.observation_id,
                feedback_type=args.type,
                reason_code=args.reason,
                correction_dimensions=tuple(args.correction_dimension),
                original_route_digest=args.original_route_digest,
                corrected_route_digest=args.corrected_route_digest,
                free_text=args.free_text,
                idempotency_key=args.idempotency_key,
                correlation_id=args.correlation_id,
            ))
            _print(result.to_dict())
            return 0 if result.status in {"recorded", "not-recorded", "memory-disabled"} else 2

        if args.memory_command == "history":
            service = WorkflowMemoryService(args.database, data_dir=args.data_dir)
            context = MemoryRequestContext(
                args.session_id, args.actor, args.runtime_policy_snapshot_id
            )
            query = HistorySummaryQuery(
                context=context,
                workspace_identity_digest=args.workspace_digest,
                route_signature_digest=args.route_signature_digest,
            )
            if args.memory_history_command == "summary":
                _print(service.history_summary(query).to_dict())
                return 0
            if args.memory_history_command == "export":
                exported = service.export_history(
                    query, include_observations=args.include_observations
                )
                output = Path(args.output).expanduser()
                if not output.is_absolute():
                    output = (Path.cwd() / output).absolute()
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(exported, encoding="utf-8")
                import hashlib
                _print({
                    "status": "exported",
                    "export_digest": "sha256:" + hashlib.sha256(exported.encode("utf-8")).hexdigest(),
                    "bytes_written": len(exported.encode("utf-8")),
                })
                return 0
            if args.memory_history_command == "purge":
                result = service.purge_memory(PurgeMemoryCommand(
                    context=context,
                    scope=args.scope,
                    expected_summary_digest=args.expected_summary_digest,
                    include_managed_profiles=args.include_managed_profiles,
                    idempotency_key=args.idempotency_key,
                    correlation_id=args.correlation_id,
                ))
                _print(result.to_dict())
                return 0 if result.status in {"purged", "scope-not-available"} else 2

        if args.memory_command == "candidates":
            service = WorkflowMemoryService(args.database, data_dir=args.data_dir)
            if args.memory_candidate_command == "rebuild":
                items = service.rebuild_candidates(
                    MemoryScope(args.scope), workspace_root=args.workspace
                )
                _print({"status": "rebuilt", "candidates": [item.to_dict() for item in items]})
                return 0
            if args.memory_candidate_command == "list":
                items = service.list_workflow_candidates(
                    workspace_root=args.workspace, status=args.status
                )
                _print({"status": "ready", "candidates": [item.to_dict() for item in items]})
                return 0
            if args.memory_candidate_command == "promote-eligible":
                result = service.promote_eligible_candidates(
                    MemoryScope(args.scope),
                    workspace_root=args.workspace,
                    actor_id=args.actor,
                    session_id=args.session_id,
                    idempotency_key=args.idempotency_key,
                    correlation_id=args.correlation_id,
                    now=args.now,
                )
                _print(result.to_dict())
                return 0 if result.status in {
                    "completed", "memory-disabled", "not-automatic"
                } else 2
            repository, effective = service._effective_policy(args.workspace)
            if not repository.memory_store_exists():
                raise MemoryStoreError("memory-store-unavailable")
            from workflow_skill_router.memory.store import MemoryStore
            store = MemoryStore.open_if_enabled(args.data_dir or repository.data_dir, effective) if effective.capture_enabled else MemoryStore.open_existing(args.data_dir or repository.data_dir)
            if store is None:
                raise MemoryStoreError("memory-store-unavailable")
            with store:
                if args.memory_candidate_command == "show":
                    item = store.load_workflow_candidate(args.candidate_id)
                    if item is None:
                        raise MemoryStoreError("workflow-candidate-not-found")
                    _print(item.to_dict())
                    return 0
            if args.memory_candidate_command == "reject":
                item = service.reject_workflow_candidate(
                    args.candidate_id, workspace_root=args.workspace, reason_code=args.reason
                )
                _print(item.to_dict())
                return 0

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
    except (MemoryPolicyError, RouteObservationError, RouteFeedbackError, MemoryStoreError, MemoryCommandConflict, ValueError) as error:
        _print(
            {"status": "invalid", "error": str(error)},
            output=sys.stderr,
        )
        return 2


__all__ = ["configure_memory_parser", "run_memory_cli"]
