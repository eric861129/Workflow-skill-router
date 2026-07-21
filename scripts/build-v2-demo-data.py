from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/router-core/src"))
from workflow_skill_router.demo_export import build_demo_artifact


def _validate_public_evaluation(evaluation: object) -> dict[str, object]:
    if not isinstance(evaluation, dict):
        raise ValueError("public evaluation must be an object")
    if evaluation.get("schema_id") != "workflow-skill-router/public-evaluation-status":
        raise ValueError("public evaluation schema mismatch")
    if evaluation.get("schema_version") != "2.0.0-alpha.1":
        raise ValueError("public evaluation version mismatch")
    if evaluation.get("status") not in {"manual-required", "review-required"}:
        raise ValueError("public evaluation status is not publishable")
    if evaluation.get("publication_gate") != "review-required":
        raise ValueError("public evaluation must retain the review gate")
    if evaluation.get("evidence_class") not in {"behavior", "contract"}:
        raise ValueError("public evaluation evidence class mismatch")
    limitations=evaluation.get("limitations")
    if not isinstance(limitations,list) or not limitations or not all(isinstance(item,str) for item in limitations):
        raise ValueError("public evaluation limitations are required")
    forbidden={"score","trusted","reviewer_id","raw_traces","transcripts","attempts"}
    if forbidden.intersection(evaluation):
        raise ValueError("public evaluation contains non-public evidence")
    return evaluation


def _pending_public_evaluation() -> dict[str, object]:
    """回傳可重現且不冒充真實模型結果的公開評測狀態。"""
    return {
        "schema_id": "workflow-skill-router/public-evaluation-status",
        "schema_version": "2.0.0-alpha.1",
        "status": "manual-required",
        "publication_gate": "review-required",
        "evidence_class": "behavior",
        "provenance": (
            "No verified fresh-task adapter was available during deterministic "
            "site generation."
        ),
        "limitations": [
            "No public score is emitted without a trusted human review attestation.",
            "Tier 0 Contract fixtures are not real model evaluation.",
        ],
    }


def _validate_routing_evidence(output: dict[str, object]) -> None:
    """驗證公開 Demo 只呈現規劃證據，不把規劃誤稱為實際啟用或權限。"""

    allowed_sources = {
        "native-goal-binding",
        "caller-work-mode-hint",
        "deterministic-analyzer",
        "profile-route",
        "builtin-fallback",
        "legacy-replay",
    }
    authority_keys = {"native_goal_mutation", "deployment", "production"}
    for preset in output["presets"]:
        evidence = preset.get("routing_evidence")
        if not isinstance(evidence, dict):
            raise ValueError("demo routing evidence is required")
        classification = evidence.get("classification")
        if (
            not isinstance(classification, dict)
            or classification.get("source") not in allowed_sources
        ):
            raise ValueError("demo classification source is invalid")
        authority = evidence.get("authority")
        if (
            not isinstance(authority, dict)
            or set(authority) != authority_keys
            or any(value is not False for value in authority.values())
        ):
            raise ValueError("demo must not claim Goal or deployment authority")
        profile_match = evidence.get("profile_match")
        if not isinstance(profile_match, dict) or set(profile_match) != {
            "status", "source", "profile_ids", "matched_rule_id",
        }:
            raise ValueError("demo profile match evidence is required")
        if profile_match["status"] == "applied":
            if (
                profile_match["source"]
                not in {"personal-profile", "workspace-profile"}
                or not profile_match["profile_ids"]
                or not isinstance(profile_match["matched_rule_id"], str)
            ):
                raise ValueError("demo profile match source is invalid")
        elif profile_match["status"] == "not-applied" and (
            profile_match["source"] is not None
            or profile_match["profile_ids"] != []
            or profile_match["matched_rule_id"] is not None
        ):
            raise ValueError("demo non-profile route is mislabeled as a profile match")
        elif profile_match["status"] not in {"applied", "not-applied"}:
            raise ValueError("demo profile match status is invalid")
        for branch in preset.get("branches", []):
            branch_evidence = branch.get("routing_evidence")
            if not isinstance(branch_evidence, dict):
                raise ValueError("demo branch routing evidence is required")
            expected_skills = [
                branch["route"]["primary_selection"],
                *branch["route"]["support_selections"],
            ]
            if branch_evidence.get("planned_skill_ids") != expected_skills:
                raise ValueError("demo branch planned Skills do not match its route")
            if branch_evidence.get("actual_activation") != "unverified":
                raise ValueError("demo must not claim actual Skill activation")


def build_demo_data(root: Path) -> dict[str, object]:
    source = json.loads((root / "demo/v2-scenarios/inputs.json").read_text("utf-8"))
    forbidden = {"request_decision","route","active_selections","policy_result","events"}
    if any(forbidden.intersection(item) for item in source["presets"]): raise ValueError("demo input contains policy output")
    evaluation = _validate_public_evaluation(_pending_public_evaluation())
    output = build_demo_artifact(source, evaluation)
    _validate_routing_evidence(output)
    encoded = json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if re.search(r"[A-Za-z]:\\Users\\|/Users/|/home/|sk-[A-Za-z0-9]", encoded): raise ValueError("demo output is not public safe")
    return output


def main() -> int:
    parser=argparse.ArgumentParser();parser.add_argument("--check",action="store_true");args=parser.parse_args()
    target=ROOT / "site/src/data/router-demo-v2.generated.json"
    data=(json.dumps(build_demo_data(ROOT),ensure_ascii=False,sort_keys=True,separators=(",", ":"))+"\n").encode()
    if args.check: return 0 if target.is_file() and target.read_bytes()==data else 1
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);return 0


if __name__=="__main__":raise SystemExit(main())
