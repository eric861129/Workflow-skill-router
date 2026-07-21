"""Read-only verification helpers for the repository release-governance contract."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any


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
        and isinstance(value.get("branch"), str)
        and isinstance(required_checks, dict)
        and isinstance(required_checks.get("strict"), bool)
        and isinstance(required_checks.get("checks"), list)
        and isinstance(branch_controls, dict)
        and all(isinstance(branch_controls.get(key), bool) for key in ("pull_request", "conversation_resolution", "force_pushes", "deletions"))
        and isinstance(tag_protection, dict)
        and isinstance(tag_protection.get("ref_name_include"), str)
        and isinstance(tag_protection.get("required_rules"), list)
        and isinstance(tag_protection.get("required_bypass_actor"), dict)
    ):
        raise ValueError("remote-governance-contract-invalid")
    if not all(
        isinstance(item, dict) and isinstance(item.get("context"), str) and isinstance(item.get("app_id"), int)
        for item in required_checks["checks"]
    ):
        raise ValueError("remote-governance-contract-invalid")
    return value


def _enabled(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return isinstance(value, dict) and value.get("enabled") is True


def _tag_ruleset(contract: dict[str, object], rulesets: list[dict[str, object]]) -> dict[str, object] | None:
    tag = contract["tag_protection"]
    assert isinstance(tag, dict)
    wanted = tag["ref_name_include"]
    for ruleset in rulesets:
        conditions = ruleset.get("conditions")
        ref_name = conditions.get("ref_name") if isinstance(conditions, dict) else None
        includes = ref_name.get("include") if isinstance(ref_name, dict) else None
        if (
            ruleset.get("target") == "tag"
            and ruleset.get("enforcement") == "active"
            and isinstance(includes, list)
            and wanted in includes
        ):
            return ruleset
    return None


def evaluate_governance(
    contract: dict[str, object],
    branch: dict[str, object],
    protection: dict[str, object],
    rulesets: list[dict[str, object]],
) -> list[str]:
    """Return deterministic public-safe violations for captured GitHub payloads."""
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
            actual_pairs = {
                (item.get("context"), item.get("app_id")) for item in actual_checks if isinstance(item, dict)
            }
            expected_pairs = {(item["context"], item["app_id"]) for item in expected_checks if isinstance(item, dict)}
            checks_present = expected_pairs.issubset(actual_pairs)
        else:
            contexts = actual_status_checks.get("contexts")
            expected_contexts = {item["context"] for item in expected_checks if isinstance(item, dict)}
            checks_present = isinstance(contexts, list) and expected_contexts.issubset(set(contexts))
        if not checks_present:
            violations.append("required-status-check-missing")

    controls = contract["required_branch_controls"]
    assert isinstance(controls, dict)
    if controls["pull_request"] and not isinstance(protection.get("required_pull_request_reviews"), dict):
        violations.append("direct-push-allowed")
    if controls["conversation_resolution"] and not _enabled(protection.get("required_conversation_resolution")):
        violations.append("conversation-resolution-missing")
    if not controls["force_pushes"] and _enabled(protection.get("allow_force_pushes")):
        violations.append("force-push-allowed")
    if not controls["deletions"] and _enabled(protection.get("allow_deletions")):
        violations.append("deletion-allowed")

    ruleset = _tag_ruleset(contract, rulesets)
    if ruleset is None:
        violations.append(TAG_RULESET_MISSING)
        return violations

    tag = contract["tag_protection"]
    assert isinstance(tag, dict)
    actual_rules = ruleset.get("rules")
    actual_rule_types = {item.get("type") for item in actual_rules if isinstance(item, dict)} if isinstance(actual_rules, list) else set()
    if not set(tag["required_rules"]).issubset(actual_rule_types):
        violations.append("v2-tag-rule-missing")
    wanted_actor = tag["required_bypass_actor"]
    assert isinstance(wanted_actor, dict)
    actors = ruleset.get("bypass_actors")
    if not isinstance(actors, list) or not any(
        isinstance(actor, dict) and all(actor.get(key) == value for key, value in wanted_actor.items())
        for actor in actors
    ):
        violations.append("v2-tag-bypass-missing")
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
