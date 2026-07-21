from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from workflow_skill_router.profiles.contract import RoutingProfileContractError
from workflow_skill_router.profiles.resolver import (
    RoutingMatchContext,
    RoutingProfileResolutionError,
    explain_profile_route,
    lint_profile,
    resolve_profile_route,
)
from workflow_skill_router.profiles.storage import (
    RoutingProfileRepository,
    load_profile_file,
)


def configure_profile_parser(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="profile_command", required=True)

    validate = commands.add_parser("validate", help="Validate one routing profile JSON file")
    validate.add_argument("path", type=Path)

    lint = commands.add_parser("lint", help="Lint one deterministic routing profile")
    lint.add_argument("path", type=Path)
    lint.add_argument("--current-phase")

    install = commands.add_parser("install", help="Install a personal profile into user state")
    install.add_argument("path", type=Path)
    install.add_argument("--data-dir", type=Path)

    list_profiles = commands.add_parser("list", help="List installed personal profiles")
    list_profiles.add_argument("--data-dir", type=Path)

    preview = commands.add_parser("preview", help="Preview the deterministic active profile route")
    preview.add_argument("--objective", required=True)
    preview.add_argument(
        "--work-mode",
        choices=("single", "phased", "managed-goal"),
        default="single",
    )
    preview.add_argument("--domain", action="append", default=[])
    preview.add_argument("--tag", action="append", default=[])
    preview.add_argument("--current-phase")
    preview.add_argument("--workspace-root", type=Path)
    preview.add_argument("--data-dir", type=Path)
    preview.add_argument("--explain", action="store_true")


def _print(value: object, *, output=sys.stdout) -> None:
    reconfigure = getattr(output, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")
    print(json.dumps(value, ensure_ascii=False, sort_keys=True), file=output)


def _contract_lint_issue(error: RoutingProfileContractError) -> dict[str, str]:
    message = str(error)
    if "primary skill cannot also be support" in message:
        code = "same-primary-support-skill"
    elif "rule_id must be unique" in message:
        code = "duplicate-rule"
    else:
        code = "profile-contract-error"
    return {
        "severity": "error",
        "code": code,
        "message": message,
    }


def run_profile_cli(args: argparse.Namespace) -> int:
    try:
        if args.profile_command == "validate":
            profile = load_profile_file(args.path)
            _print({
                "status": "valid",
                "profile_id": profile.profile_id,
                "scope": profile.scope,
                "profile_digest": profile.profile_digest,
                "rule_count": len(profile.rules),
            })
            return 0

        if args.profile_command == "lint":
            try:
                profile = load_profile_file(args.path)
            except RoutingProfileContractError as error:
                _print({
                    "status": "invalid",
                    "error_count": 1,
                    "advisory_count": 0,
                    "issues": [_contract_lint_issue(error)],
                })
                return 2
            issues = lint_profile(
                profile,
                current_phase_id=args.current_phase,
            )
            error_count = sum(issue.severity == "error" for issue in issues)
            advisory_count = sum(issue.severity == "advisory" for issue in issues)
            _print({
                "status": "invalid" if error_count else "valid",
                "profile_id": profile.profile_id,
                "profile_digest": profile.profile_digest,
                "error_count": error_count,
                "advisory_count": advisory_count,
                "issues": [issue.to_dict() for issue in issues],
            })
            return 2 if error_count else 0

        repository = RoutingProfileRepository(args.data_dir)
        if args.profile_command == "install":
            installed = repository.install_personal(args.path)
            profile = load_profile_file(installed, expected_scope="personal")
            _print({
                "status": "installed",
                "profile_id": profile.profile_id,
                "profile_digest": profile.profile_digest,
                "installed_path": str(installed),
            })
            return 0
        if args.profile_command == "list":
            profiles = repository.list_personal()
            _print({
                "status": "ready",
                "profile_ids": [profile.profile_id for profile in profiles],
                "profiles": [
                    {
                        "profile_id": profile.profile_id,
                        "enabled": profile.enabled,
                        "profile_digest": profile.profile_digest,
                        "rule_count": len(profile.rules),
                    }
                    for profile in profiles
                ],
            })
            return 0
        if args.profile_command == "preview":
            profiles = repository.load_layers(workspace_root=args.workspace_root)
            context = RoutingMatchContext(
                domains=tuple(args.domain),
                tags=tuple(args.tag),
                current_phase_id=args.current_phase,
                lock_work_mode=True,
            )
            traces = (
                explain_profile_route(
                    profiles,
                    objective=args.objective,
                    default_work_mode=args.work_mode,
                    context=context,
                )
                if args.explain
                else ()
            )
            route = resolve_profile_route(
                profiles,
                objective=args.objective,
                default_work_mode=args.work_mode,
                context=context,
            )
            if route is None:
                payload = {
                    "status": "no-profile-match",
                    "route_source": "builtin-default",
                    "work_mode": args.work_mode,
                    "activation_status": "not-planned",
                }
                if args.explain:
                    payload["rule_traces"] = [trace.to_dict() for trace in traces]
                _print(payload)
                return 0
            payload = {
                "status": "matched",
                "route_source": route.route_source,
                "profile_id": route.profile_id,
                "profile_digest": route.profile_digest,
                "matched_rule_id": route.matched_rule_id,
                "work_mode": route.work_mode,
                "current_phase": route.current_phase.to_dict(),
                "current_skill_ids": list(route.current_skill_ids),
                "skill_tree": [phase.to_dict() for phase in route.skill_tree],
                "activation_status": route.activation_status,
            }
            if args.explain:
                payload["rule_traces"] = [trace.to_dict() for trace in traces]
            _print(payload)
            return 0
        raise RuntimeError("unsupported-profile-command")
    except (RoutingProfileContractError, RoutingProfileResolutionError) as error:
        _print({"status": "invalid", "error": str(error)}, output=sys.stderr)
        return 2
