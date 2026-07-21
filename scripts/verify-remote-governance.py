#!/usr/bin/env python3
"""Read-only CLI for verifying GitHub release-governance configuration."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys
from typing import Sequence


def _load_governance_module():
    module_path = Path(__file__).with_name("remote_governance.py")
    spec = importlib.util.spec_from_file_location("remote_governance", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("remote-governance-unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify remote release governance without mutations.")
    parser.add_argument("--repo", required=True, metavar="OWNER/REPO")
    parser.add_argument("--contract", type=Path, default=Path(".github/branch-protection.json"))
    args = parser.parse_args(argv)
    try:
        governance = _load_governance_module()
        contract = governance.load_contract(args.contract)
        branch_name = contract["branch"]
        branch = governance.fetch_json(args.repo, f"repos/{args.repo}/branches/{branch_name}")
        protection = governance.fetch_json(args.repo, f"repos/{args.repo}/branches/{branch_name}/protection")
        ruleset_summaries = governance.fetch_json(args.repo, f"repos/{args.repo}/rulesets")
        if not isinstance(branch, dict) or not isinstance(protection, dict) or not isinstance(ruleset_summaries, list):
            raise governance.RemoteGovernanceUnavailableError(governance.REMOTE_GOVERNANCE_UNAVAILABLE)
        ruleset_ids = governance.eligible_tag_ruleset_ids(contract, ruleset_summaries)
        rulesets = []
        for ruleset_id in ruleset_ids:
            ruleset = governance.fetch_json(args.repo, f"repos/{args.repo}/rulesets/{ruleset_id}")
            if not isinstance(ruleset, dict):
                raise governance.RemoteGovernanceUnavailableError(governance.REMOTE_GOVERNANCE_UNAVAILABLE)
            rulesets.append(ruleset)
        violations = governance.evaluate_governance(contract, branch, protection, rulesets)
    except (AttributeError, KeyError, TypeError, ValueError, RuntimeError):
        print("remote-governance-unavailable")
        return 1
    if violations:
        print("\n".join(violations))
        return 1
    print("PASS: remote release governance matches contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
