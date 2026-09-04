from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping

from workflow_skill_router.profiles.contract import (
    RoutingPreferenceProfile,
    decode_routing_profile,
)
from workflow_skill_router.schemas.artifacts import canonical_json

from .candidates import WorkflowCandidate


class ProfileDiffError(ValueError):
    """Raised when a Candidate cannot be compiled to a safe Routing Profile."""


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def profile_document(profile: RoutingPreferenceProfile | None) -> dict[str, object] | None:
    if profile is None:
        return None
    return {
        "schema_id": "workflow-skill-router/routing-profile",
        "schema_version": "1.0.0",
        "artifact_kind": "routing-profile",
        "profile_id": profile.profile_id,
        "scope": profile.scope,
        "enabled": profile.enabled,
        "rules": [
            {
                "rule_id": rule.rule_id,
                "priority": rule.priority,
                "match": {
                    "objective_keywords": list(rule.match.objective_keywords),
                    "domains": list(rule.match.domains),
                    "tags": list(rule.match.tags),
                    "work_modes": list(rule.match.work_modes),
                },
                "route": {
                    "work_mode": rule.route.work_mode,
                    "skill_tree": [phase.to_dict() for phase in rule.route.skill_tree],
                },
            }
            for rule in profile.rules
        ],
    }


def _candidate_rule(candidate: WorkflowCandidate) -> dict[str, object]:
    tree: list[dict[str, object]] = []
    for phase in candidate.phases:
        if phase.primary_skill_id is None or len(phase.exit_gate_ids) != 1:
            raise ProfileDiffError("candidate-phase-not-profile-compatible")
        tree.append({
            "phase_id": phase.phase_id,
            "primary_skill_id": phase.primary_skill_id,
            "support_skill_ids": list(phase.support_skill_ids),
            "exit_gate": phase.exit_gate_ids[0],
        })
    rule_id = "memory-" + candidate.pattern_id.split(":", 1)[-1][:24]
    return {
        "rule_id": rule_id,
        "priority": 100,
        "match": {
            "objective_keywords": list(candidate.matcher_seed.objective_keywords),
            "domains": list(candidate.matcher_seed.domains),
            "tags": list(candidate.matcher_seed.tags),
            "work_modes": [candidate.work_mode],
        },
        "route": {"work_mode": candidate.work_mode, "skill_tree": tree},
    }


def build_profile_document(
    candidate: WorkflowCandidate,
    current_profile: RoutingPreferenceProfile | None,
) -> dict[str, object]:
    if not isinstance(candidate, WorkflowCandidate):
        raise TypeError("candidate must be WorkflowCandidate")
    scope = candidate.scope.value
    expected_scope = "personal" if candidate.target_profile_class in {"managed-personal", "user-personal"} else "workspace"
    if scope != expected_scope:
        raise ProfileDiffError("candidate-target-scope-mismatch")
    rule = _candidate_rule(candidate)
    if current_profile is None:
        document: dict[str, object] = {
            "schema_id": "workflow-skill-router/routing-profile",
            "schema_version": "1.0.0",
            "artifact_kind": "routing-profile",
            "profile_id": f"{scope}:adaptive-memory",
            "scope": scope,
            "enabled": True,
            "rules": [rule],
        }
    else:
        if current_profile.scope != scope:
            raise ProfileDiffError("current-profile-scope-mismatch")
        document = profile_document(current_profile) or {}
        rules = [item for item in list(document["rules"]) if item["rule_id"] != rule["rule_id"]]
        rules.append(rule)
        rules.sort(key=lambda item: str(item["rule_id"]))
        document["rules"] = rules
    decoded = decode_routing_profile(document, expected_scope=scope)
    return profile_document(decoded) or {}


@dataclass(frozen=True, slots=True)
class SemanticDiffEntry:
    change_type: str
    rule_id: str | None
    phase_id: str | None
    field: str | None
    before: object
    after: object

    def to_dict(self) -> dict[str, object]:
        return {
            "change_type": self.change_type,
            "rule_id": self.rule_id,
            "phase_id": self.phase_id,
            "field": self.field,
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True, slots=True)
class SemanticProfileDiff:
    entries: tuple[SemanticDiffEntry, ...]
    json_patch: tuple[dict[str, object], ...]
    semantic_diff_digest: str
    json_patch_digest: str

    def to_dict(self) -> dict[str, object]:
        return {
            "entries": [item.to_dict() for item in self.entries],
            "json_patch": [dict(item) for item in self.json_patch],
            "semantic_diff_digest": self.semantic_diff_digest,
            "json_patch_digest": self.json_patch_digest,
        }


def _rules(document: Mapping[str, object] | None) -> dict[str, Mapping[str, object]]:
    if document is None:
        return {}
    return {str(item["rule_id"]): item for item in document["rules"]}  # type: ignore[index]


def _phase_map(rule: Mapping[str, object]) -> tuple[list[str], dict[str, Mapping[str, object]]]:
    route = rule["route"]  # type: ignore[index]
    tree = route["skill_tree"]  # type: ignore[index]
    order = [str(item["phase_id"]) for item in tree]
    return order, {str(item["phase_id"]): item for item in tree}


def diff_profiles(
    before: RoutingPreferenceProfile | Mapping[str, object] | None,
    after: RoutingPreferenceProfile | Mapping[str, object],
) -> SemanticProfileDiff:
    before_doc = profile_document(before) if isinstance(before, RoutingPreferenceProfile) else (dict(before) if before is not None else None)
    after_doc = profile_document(after) if isinstance(after, RoutingPreferenceProfile) else dict(after)
    decoded_after = decode_routing_profile(after_doc)
    after_doc = profile_document(decoded_after) or {}
    if before_doc is not None:
        before_doc = profile_document(decode_routing_profile(before_doc))
    entries: list[SemanticDiffEntry] = []
    old_rules, new_rules = _rules(before_doc), _rules(after_doc)
    for rule_id in sorted(set(old_rules) | set(new_rules)):
        old, new = old_rules.get(rule_id), new_rules.get(rule_id)
        if old is None:
            entries.append(SemanticDiffEntry("rule-added", rule_id, None, None, None, new))
            continue
        if new is None:
            entries.append(SemanticDiffEntry("rule-removed", rule_id, None, None, old, None))
            continue
        for field in ("priority", "match"):
            if old[field] != new[field]:
                entries.append(SemanticDiffEntry("rule-changed", rule_id, None, field, old[field], new[field]))
        old_route, new_route = old["route"], new["route"]
        if old_route["work_mode"] != new_route["work_mode"]:  # type: ignore[index]
            entries.append(SemanticDiffEntry("rule-changed", rule_id, None, "work_mode", old_route["work_mode"], new_route["work_mode"]))  # type: ignore[index]
        old_order, old_phases = _phase_map(old)
        new_order, new_phases = _phase_map(new)
        if old_order != new_order:
            entries.append(SemanticDiffEntry("phase-order-changed", rule_id, None, "phase_order", old_order, new_order))
        for phase_id in sorted(set(old_phases) | set(new_phases)):
            op, np = old_phases.get(phase_id), new_phases.get(phase_id)
            if op is None:
                entries.append(SemanticDiffEntry("phase-added", rule_id, phase_id, None, None, np))
                continue
            if np is None:
                entries.append(SemanticDiffEntry("phase-removed", rule_id, phase_id, None, op, None))
                continue
            for field in ("primary_skill_id", "support_skill_ids", "exit_gate"):
                if op[field] != np[field]:
                    entries.append(SemanticDiffEntry("phase-changed", rule_id, phase_id, field, op[field], np[field]))
    patch: list[dict[str, object]] = []
    if before_doc is None:
        patch.append({"op": "add", "path": "/", "value": after_doc})
    elif canonical_json(before_doc) != canonical_json(after_doc):
        patch.append({"op": "replace", "path": "/rules", "value": after_doc["rules"]})
    semantic_doc = [item.to_dict() for item in entries]
    return SemanticProfileDiff(tuple(entries), tuple(patch), _digest(semantic_doc), _digest(patch))


__all__ = [
    "ProfileDiffError", "SemanticDiffEntry", "SemanticProfileDiff",
    "build_profile_document", "diff_profiles", "profile_document",
]
