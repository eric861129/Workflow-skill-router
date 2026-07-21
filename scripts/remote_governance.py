"""Read-only verification helpers for the repository release-governance contract."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess


MAIN_NOT_PROTECTED = "main-not-protected"
TAG_RULESET_MISSING = "v2-tag-ruleset-missing"
REMOTE_GOVERNANCE_UNAVAILABLE = "remote-governance-unavailable"


class RemoteGovernanceUnavailableError(RuntimeError):
    """Indicates that a read-only GitHub API payload could not be obtained safely."""


def load_contract(path: Path) -> dict[str, object]:
    """Load and validate the versioned desired-state governance contract."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("remote-governance-contract-invalid") from error
    if not isinstance(value, dict):
        raise ValueError("remote-governance-contract-invalid")

    required_checks = value.get("required_status_checks")
    branch_controls = value.get("required_branch_controls")
    tag_protection = value.get("tag_protection")
    if not (
        isinstance(value.get("repository"), str)
        and bool(value["repository"])
        and value.get("branch") == "main"
        and isinstance(required_checks, dict)
        and required_checks.get("strict") is True
        and isinstance(required_checks.get("checks"), list)
        and isinstance(branch_controls, dict)
        and branch_controls == {
            "pull_request": True,
            "conversation_resolution": True,
            "force_pushes": False,
            "deletions": False,
        }
        and isinstance(tag_protection, dict)
        and tag_protection.get("name") == "Immutable V2 release tags"
        and tag_protection.get("target") == "tag"
        and tag_protection.get("enforcement") == "active"
        and tag_protection.get("ref_name_include") == "refs/tags/v2.*"
        and isinstance(tag_protection.get("required_rules"), list)
        and isinstance(tag_protection.get("required_bypass_actor"), dict)
    ):
        raise ValueError("remote-governance-contract-invalid")
    if not all(
        isinstance(item, dict) and isinstance(item.get("context"), str) and bool(item["context"])
        and isinstance(item.get("app_id"), int)
        for item in required_checks["checks"]
    ) or not required_checks["checks"]:
        raise ValueError("remote-governance-contract-invalid")
    if not all(isinstance(rule, str) and bool(rule) for rule in tag_protection["required_rules"]):
        raise ValueError("remote-governance-contract-invalid")
    if tag_protection["required_rules"] != ["creation", "update", "deletion"]:
        raise ValueError("remote-governance-contract-invalid")
    if tag_protection["required_bypass_actor"] != {
        "actor_id": 15368,
        "actor_type": "Integration",
        "bypass_mode": "always",
    }:
        raise ValueError("remote-governance-contract-invalid")
    return value


def _enabled(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return isinstance(value, dict) and value.get("enabled") is True


def _explicitly_disabled(value: object) -> bool:
    """Return true only for GitHub's two documented disabled representations."""
    return value is False or (isinstance(value, dict) and value == {"enabled": False})


def _tag_rulesets(contract: dict[str, object], rulesets: list[dict[str, object]]) -> list[dict[str, object]]:
    tag = contract["tag_protection"]
    assert isinstance(tag, dict)
    wanted = tag["ref_name_include"]
    qualifying: list[dict[str, object]] = []
    for ruleset in rulesets:
        if not isinstance(ruleset, dict):
            raise RemoteGovernanceUnavailableError(REMOTE_GOVERNANCE_UNAVAILABLE)
        conditions = ruleset.get("conditions")
        ref_name = conditions.get("ref_name") if isinstance(conditions, dict) else None
        includes = ref_name.get("include") if isinstance(ref_name, dict) else None
        if (
            ruleset.get("target") == "tag"
            and ruleset.get("enforcement") == "active"
            and isinstance(includes, list)
            and wanted in includes
        ):
            qualifying.append(ruleset)
    return qualifying


def _rule_types(ruleset: dict[str, object]) -> set[str]:
    rules = ruleset.get("rules")
    if not isinstance(rules, list) or not all(
        isinstance(rule, dict) and isinstance(rule.get("type"), str) for rule in rules
    ):
        raise RemoteGovernanceUnavailableError(REMOTE_GOVERNANCE_UNAVAILABLE)
    return {rule["type"] for rule in rules}


def _has_required_bypass(ruleset: dict[str, object], wanted_actor: dict[str, object]) -> bool:
    actors = ruleset.get("bypass_actors")
    if not isinstance(actors, list) or not all(isinstance(actor, dict) for actor in actors):
        raise RemoteGovernanceUnavailableError(REMOTE_GOVERNANCE_UNAVAILABLE)
    return any(all(actor.get(key) == value for key, value in wanted_actor.items()) for actor in actors)


def evaluate_governance(
    contract: dict[str, object],
    branch: dict[str, object],
    protection: dict[str, object],
    rulesets: list[dict[str, object]],
) -> list[str]:
    """Return deterministic public-safe violations for captured GitHub payloads."""
    if not isinstance(branch.get("protected"), bool):
        raise RemoteGovernanceUnavailableError(REMOTE_GOVERNANCE_UNAVAILABLE)
    violations: list[str] = []
    if branch.get("protected") is not True:
        violations.append(MAIN_NOT_PROTECTED)

    required_checks = contract["required_status_checks"]
    assert isinstance(required_checks, dict)
    expected_checks = required_checks["checks"]
    assert isinstance(expected_checks, list)
    actual_status_checks = protection.get("required_status_checks")
    if not isinstance(actual_status_checks, dict) or actual_status_checks.get("strict") is not required_checks["strict"]:
        violations.append("required-status-checks-invalid")
    else:
        actual_checks = actual_status_checks.get("checks")
        if isinstance(actual_checks, list):
            if not all(
                isinstance(item, dict) and isinstance(item.get("context"), str) and isinstance(item.get("app_id"), int)
                for item in actual_checks
            ):
                raise RemoteGovernanceUnavailableError(REMOTE_GOVERNANCE_UNAVAILABLE)
            actual_pairs = {
                (item["context"], item["app_id"]) for item in actual_checks
            }
            expected_pairs = {(item["context"], item["app_id"]) for item in expected_checks if isinstance(item, dict)}
            checks_present = expected_pairs.issubset(actual_pairs)
        else:
            contexts = actual_status_checks.get("contexts")
            expected_contexts = {item["context"] for item in expected_checks if isinstance(item, dict)}
            if not isinstance(contexts, list) or not all(isinstance(context, str) for context in contexts):
                raise RemoteGovernanceUnavailableError(REMOTE_GOVERNANCE_UNAVAILABLE)
            checks_present = expected_contexts.issubset(set(contexts))
        if not checks_present:
            violations.append("required-status-check-missing")

    controls = contract["required_branch_controls"]
    assert isinstance(controls, dict)
    if controls["pull_request"] and not isinstance(protection.get("required_pull_request_reviews"), dict):
        violations.append("direct-push-allowed")
    if controls["conversation_resolution"] and not _enabled(protection.get("required_conversation_resolution")):
        violations.append("conversation-resolution-missing")
    if not controls["force_pushes"] and not _explicitly_disabled(protection.get("allow_force_pushes")):
        violations.append("force-push-allowed")
    if not controls["deletions"] and not _explicitly_disabled(protection.get("allow_deletions")):
        violations.append("deletion-allowed")

    ruleset_candidates = _tag_rulesets(contract, rulesets)
    if not ruleset_candidates:
        violations.append(TAG_RULESET_MISSING)
        return violations

    tag = contract["tag_protection"]
    assert isinstance(tag, dict)
    wanted_actor = tag["required_bypass_actor"]
    assert isinstance(wanted_actor, dict)
    required_rules = set(tag["required_rules"])
    candidates = [
        (required_rules.issubset(_rule_types(ruleset)), _has_required_bypass(ruleset, wanted_actor))
        for ruleset in ruleset_candidates
    ]
    if any(has_rules and has_bypass for has_rules, has_bypass in candidates):
        return violations
    if not any(has_rules for has_rules, _ in candidates):
        violations.append("v2-tag-rule-missing")
    if not any(has_bypass for _, has_bypass in candidates):
        violations.append("v2-tag-bypass-missing")
    if not violations or violations[-1] not in {"v2-tag-rule-missing", "v2-tag-bypass-missing"}:
        violations.append("v2-tag-ruleset-incomplete")
    return violations


def fetch_json(repo: str, endpoint: str) -> object:
    """Fetch one GitHub API JSON response without allowing mutating CLI flags."""
    if not repo or not endpoint.startswith(f"repos/{repo}/"):
        raise RemoteGovernanceUnavailableError(REMOTE_GOVERNANCE_UNAVAILABLE)
    try:
        completed = subprocess.run(
            ["gh", "api", endpoint], capture_output=True, text=True, check=False
        )
        if completed.returncode != 0:
            raise RemoteGovernanceUnavailableError(REMOTE_GOVERNANCE_UNAVAILABLE)
        return json.loads(completed.stdout)
    except (OSError, json.JSONDecodeError) as error:
        raise RemoteGovernanceUnavailableError(REMOTE_GOVERNANCE_UNAVAILABLE) from error
