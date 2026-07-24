#!/usr/bin/env python3
"""Verify the generated Plugin repository's GitHub governance without mutations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Sequence


PAGE_SIZE = 100
GOVERNANCE_UNAVAILABLE = "plugin-distribution-governance-unavailable"


class GovernanceUnavailableError(RuntimeError):
    """Indicates that GitHub governance could not be read or parsed safely."""


def load_contract(path: Path) -> dict[str, object]:
    """Load the fail-closed desired-state contract for the generated target."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(GOVERNANCE_UNAVAILABLE) from error
    if not isinstance(value, dict):
        raise ValueError(GOVERNANCE_UNAVAILABLE)

    scanner = value.get("scanner")
    branch_ruleset = value.get("branch_ruleset")
    tag_ruleset = value.get("tag_ruleset")
    bypass = value.get("release_app_bypass")
    if not (
        value.get("schema_version") == "1.0"
        and value.get("repository")
        == "eric861129/workflow-skill-router-plugin"
        and value.get("visibility") == "public"
        and value.get("default_branch") == "main"
        and scanner
        == {
            "workflow": "HOL Plugin Scanner",
            "required_check": {
                "context": "scan",
                "integration_id": 15368,
                "strict": True,
            },
        }
        and branch_ruleset
        == {
            "name": "Protected generated main",
            "target": "branch",
            "enforcement": "active",
            "ref_name_include": "refs/heads/main",
            "required_rules": ["deletion", "non_fast_forward"],
        }
        and tag_ruleset
        == {
            "name": "Immutable Plugin release tags",
            "target": "tag",
            "enforcement": "active",
            "ref_name_include": "refs/tags/v*",
            "required_rules": ["creation", "update", "deletion"],
        }
        and bypass
        == {
            "actor_id": 4361147,
            "actor_type": "Integration",
            "bypass_mode": "always",
        }
    ):
        raise ValueError(GOVERNANCE_UNAVAILABLE)
    return value


def fetch_json(repo: str, endpoint: str) -> object:
    """Fetch one repository-scoped GitHub API response with an explicit GET."""
    if not repo or not (
        endpoint == f"repos/{repo}"
        or endpoint.startswith(f"repos/{repo}/")
    ):
        raise GovernanceUnavailableError(GOVERNANCE_UNAVAILABLE)
    try:
        completed = subprocess.run(
            ["gh", "api", "--method", "GET", endpoint],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise GovernanceUnavailableError(GOVERNANCE_UNAVAILABLE)
        return json.loads(completed.stdout)
    except (OSError, json.JSONDecodeError) as error:
        raise GovernanceUnavailableError(GOVERNANCE_UNAVAILABLE) from error


def _ruleset_summaries(repo: str, target: str) -> list[dict[str, object]]:
    """Fetch every summary page for one GitHub ruleset target."""
    summaries: list[dict[str, object]] = []
    page = 1
    while True:
        response = fetch_json(
            repo,
            (
                f"repos/{repo}/rulesets?targets={target}"
                f"&per_page={PAGE_SIZE}&page={page}"
            ),
        )
        if not isinstance(response, list) or not all(
            isinstance(item, dict) for item in response
        ):
            raise GovernanceUnavailableError(GOVERNANCE_UNAVAILABLE)
        summaries.extend(response)
        if len(response) < PAGE_SIZE:
            return summaries
        page += 1


def _eligible_ruleset_ids(
    desired: dict[str, object],
    summaries: list[dict[str, object]],
) -> list[int]:
    """Select active named rulesets whose complete details must be checked."""
    result: list[int] = []
    for summary in summaries:
        ruleset_id = summary.get("id")
        if (
            not isinstance(ruleset_id, int)
            or isinstance(ruleset_id, bool)
            or ruleset_id <= 0
            or not isinstance(summary.get("name"), str)
            or not isinstance(summary.get("enforcement"), str)
        ):
            raise GovernanceUnavailableError(GOVERNANCE_UNAVAILABLE)
        if (
            summary["name"] == desired["name"]
            and summary["enforcement"] == desired["enforcement"]
        ):
            result.append(ruleset_id)
    return result


def _ruleset_details(
    repo: str,
    desired: dict[str, object],
    summaries: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Fetch full details only for active rulesets eligible by contract."""
    details: list[dict[str, object]] = []
    for ruleset_id in _eligible_ruleset_ids(desired, summaries):
        response = fetch_json(repo, f"repos/{repo}/rulesets/{ruleset_id}")
        if not isinstance(response, dict):
            raise GovernanceUnavailableError(GOVERNANCE_UNAVAILABLE)
        details.append(response)
    return details


def _ref_conditions(
    ruleset: dict[str, object],
) -> tuple[list[str], list[str]]:
    conditions = ruleset.get("conditions")
    ref_name = conditions.get("ref_name") if isinstance(conditions, dict) else None
    includes = ref_name.get("include") if isinstance(ref_name, dict) else None
    excludes = ref_name.get("exclude") if isinstance(ref_name, dict) else None
    if (
        not isinstance(includes, list)
        or not all(isinstance(item, str) for item in includes)
        or not isinstance(excludes, list)
        or not all(isinstance(item, str) for item in excludes)
    ):
        raise GovernanceUnavailableError(GOVERNANCE_UNAVAILABLE)
    return includes, excludes


def _rule_entries(ruleset: dict[str, object]) -> list[dict[str, object]]:
    rules = ruleset.get("rules")
    if not isinstance(rules, list) or not all(
        isinstance(rule, dict) and isinstance(rule.get("type"), str)
        for rule in rules
    ):
        raise GovernanceUnavailableError(GOVERNANCE_UNAVAILABLE)
    return rules


def _matching_rulesets(
    desired: dict[str, object],
    rulesets: list[dict[str, object]],
) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for ruleset in rulesets:
        if not all(
            isinstance(ruleset.get(field), str)
            for field in ("name", "target", "enforcement")
        ):
            raise GovernanceUnavailableError(GOVERNANCE_UNAVAILABLE)
        includes, excludes = _ref_conditions(ruleset)
        target_ref = desired["ref_name_include"]
        if (
            ruleset["name"] == desired["name"]
            and ruleset["target"] == desired["target"]
            and ruleset["enforcement"] == desired["enforcement"]
            and target_ref in includes
            and not excludes
        ):
            matches.append(ruleset)
    return matches


def _has_required_rules(
    ruleset: dict[str, object],
    desired: dict[str, object],
) -> bool:
    actual = {rule["type"] for rule in _rule_entries(ruleset)}
    required = desired.get("required_rules")
    if not isinstance(required, list) or not all(
        isinstance(item, str) for item in required
    ):
        raise GovernanceUnavailableError(GOVERNANCE_UNAVAILABLE)
    return set(required).issubset(actual)


def _has_scanner(
    ruleset: dict[str, object],
    scanner: dict[str, object],
) -> bool:
    required_check = scanner.get("required_check")
    if not isinstance(required_check, dict):
        raise GovernanceUnavailableError(GOVERNANCE_UNAVAILABLE)
    for rule in _rule_entries(ruleset):
        if rule["type"] != "required_status_checks":
            continue
        parameters = rule.get("parameters")
        checks = (
            parameters.get("required_status_checks")
            if isinstance(parameters, dict)
            else None
        )
        if not isinstance(checks, list) or not all(
            isinstance(check, dict) for check in checks
        ):
            raise GovernanceUnavailableError(GOVERNANCE_UNAVAILABLE)
        if (
            parameters.get("strict_required_status_checks_policy")
            is required_check["strict"]
            and {
                (check.get("context"), check.get("integration_id"))
                for check in checks
            }
            >= {
                (
                    required_check["context"],
                    required_check["integration_id"],
                )
            }
        ):
            return True
    return False


def _has_release_app_bypass(
    ruleset: dict[str, object],
    expected: dict[str, object],
) -> bool:
    bypass_actors = ruleset.get("bypass_actors")
    if not isinstance(bypass_actors, list) or not all(
        isinstance(actor, dict) for actor in bypass_actors
    ):
        raise GovernanceUnavailableError(GOVERNANCE_UNAVAILABLE)
    return bypass_actors == [expected]


def evaluate_governance(
    contract: dict[str, object],
    repository: dict[str, object],
    branch: dict[str, object],
    branch_rulesets: list[dict[str, object]],
    tag_rulesets: list[dict[str, object]],
) -> list[str]:
    """Return deterministic violations for captured target-repository payloads."""
    if (
        not isinstance(repository.get("private"), bool)
        or not isinstance(repository.get("visibility"), str)
        or not isinstance(repository.get("default_branch"), str)
        or not isinstance(branch.get("protected"), bool)
    ):
        raise GovernanceUnavailableError(GOVERNANCE_UNAVAILABLE)

    violations: list[str] = []
    if (
        repository["private"] is not False
        or repository["visibility"] != contract["visibility"]
    ):
        violations.append("repository-not-public")
    if repository["default_branch"] != contract["default_branch"]:
        violations.append("default-branch-mismatch")
    if branch["protected"] is not True:
        violations.append("target-branch-not-protected")

    desired_branch = contract["branch_ruleset"]
    desired_tag = contract["tag_ruleset"]
    scanner = contract["scanner"]
    bypass = contract["release_app_bypass"]
    if not all(
        isinstance(item, dict)
        for item in (desired_branch, desired_tag, scanner, bypass)
    ):
        raise GovernanceUnavailableError(GOVERNANCE_UNAVAILABLE)

    matching_branches = _matching_rulesets(desired_branch, branch_rulesets)
    branch_rule_candidates = [
        ruleset
        for ruleset in matching_branches
        if _has_required_rules(ruleset, desired_branch)
    ]
    if not branch_rule_candidates:
        violations.append("target-branch-rules-missing")
    branch_scanner_candidates = [
        ruleset
        for ruleset in branch_rule_candidates or matching_branches
        if _has_scanner(ruleset, scanner)
    ]
    if not branch_scanner_candidates:
        violations.append("scanner-requirement-missing")
    if not any(
        _has_release_app_bypass(ruleset, bypass)
        for ruleset in (
            branch_scanner_candidates
            or branch_rule_candidates
            or matching_branches
        )
    ):
        violations.append("release-app-bypass-missing")

    matching_tags = _matching_rulesets(desired_tag, tag_rulesets)
    tag_rule_candidates = [
        ruleset
        for ruleset in matching_tags
        if _has_required_rules(ruleset, desired_tag)
    ]
    if not tag_rule_candidates:
        violations.append("tag-protection-missing")
    if not any(
        _has_release_app_bypass(ruleset, bypass)
        for ruleset in tag_rule_candidates or matching_tags
    ) and "release-app-bypass-missing" not in violations:
        violations.append("release-app-bypass-missing")
    return violations


def main(argv: Sequence[str] | None = None) -> int:
    """Run the read-only target-governance verification."""
    parser = argparse.ArgumentParser(
        description="Verify generated Plugin repository governance using GET only."
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path(".github/plugin-distribution-governance.json"),
    )
    parser.add_argument("--repo", metavar="OWNER/REPO")
    args = parser.parse_args(argv)
    try:
        contract = load_contract(args.contract)
        repo = contract["repository"]
        if not isinstance(repo, str) or (args.repo and args.repo != repo):
            raise ValueError(GOVERNANCE_UNAVAILABLE)
        repository = fetch_json(repo, f"repos/{repo}")
        branch_name = contract["default_branch"]
        branch = fetch_json(repo, f"repos/{repo}/branches/{branch_name}")
        desired_branch = contract["branch_ruleset"]
        desired_tag = contract["tag_ruleset"]
        if not all(
            isinstance(value, dict)
            for value in (
                repository,
                branch,
                desired_branch,
                desired_tag,
            )
        ):
            raise GovernanceUnavailableError(GOVERNANCE_UNAVAILABLE)

        branch_summaries = _ruleset_summaries(repo, "branch")
        branch_rulesets = _ruleset_details(
            repo,
            desired_branch,
            branch_summaries,
        )
        tag_summaries = _ruleset_summaries(repo, "tag")
        tag_rulesets = _ruleset_details(repo, desired_tag, tag_summaries)
        violations = evaluate_governance(
            contract,
            repository,
            branch,
            branch_rulesets,
            tag_rulesets,
        )
    except (AttributeError, KeyError, TypeError, ValueError, RuntimeError):
        print(GOVERNANCE_UNAVAILABLE)
        return 1
    if violations:
        print("\n".join(violations))
        return 1
    print("PASS: generated Plugin repository governance matches contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
