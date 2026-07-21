from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import re
from typing import Any

from workflow_skill_router.schemas.artifacts import canonical_json


SCHEMA_ID = "workflow-skill-router/routing-profile"
SCHEMA_VERSION = "1.0.0"
ARTIFACT_KIND = "routing-profile"
MAX_RULES = 64
MAX_PHASES = 32
MAX_SUPPORT_SKILLS = 3

_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_PROFILE_ID = re.compile(r"^(personal|workspace):[a-z0-9][a-z0-9._-]{0,63}$")
_SKILL_ID = re.compile(r"^skill:[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_WORK_MODES = frozenset({"single", "phased", "managed-goal"})


def is_canonical_skill_id(value: object) -> bool:
    """判斷識別碼是否符合 Routing Profile 的 canonical Skill ID 契約。"""

    return isinstance(value, str) and _SKILL_ID.fullmatch(value) is not None


class RoutingProfileContractError(ValueError):
    """Raised when a routing profile is ambiguous or outside the safe contract."""


@dataclass(frozen=True, slots=True)
class ProfileMatch:
    objective_keywords: tuple[str, ...]
    domains: tuple[str, ...]
    tags: tuple[str, ...]
    work_modes: tuple[str, ...]

    @property
    def specificity(self) -> int:
        return sum(bool(value) for value in (
            self.objective_keywords,
            self.domains,
            self.tags,
            self.work_modes,
        ))


@dataclass(frozen=True, slots=True)
class SkillTreePhase:
    phase_id: str
    primary_skill_id: str
    support_skill_ids: tuple[str, ...]
    exit_gate: str

    def to_dict(self) -> dict[str, object]:
        return {
            "phase_id": self.phase_id,
            "primary_skill_id": self.primary_skill_id,
            "support_skill_ids": list(self.support_skill_ids),
            "exit_gate": self.exit_gate,
        }


@dataclass(frozen=True, slots=True)
class ProfileRoute:
    work_mode: str
    skill_tree: tuple[SkillTreePhase, ...]


@dataclass(frozen=True, slots=True)
class RoutingProfileRule:
    rule_id: str
    priority: int
    match: ProfileMatch
    route: ProfileRoute


@dataclass(frozen=True, slots=True)
class RoutingPreferenceProfile:
    profile_id: str
    scope: str
    enabled: bool
    rules: tuple[RoutingProfileRule, ...]
    profile_digest: str


def _object(value: object, *, path: str, fields: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RoutingProfileContractError(f"{path} must be an object")
    actual = {str(key) for key in value}
    if actual != fields:
        missing = sorted(fields - actual)
        unknown = sorted(actual - fields)
        raise RoutingProfileContractError(
            f"{path} fields mismatch: missing={missing}, unknown={unknown}"
        )
    return value


def _identifier(value: object, *, path: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise RoutingProfileContractError(f"{path} must be a lowercase identifier")
    return value


def _string_list(
    value: object,
    *,
    path: str,
    pattern: re.Pattern[str] | None = _IDENTIFIER,
    item_predicate: Callable[[object], bool] | None = None,
    maximum: int = 32,
) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > maximum:
        raise RoutingProfileContractError(f"{path} must be an array with at most {maximum} items")
    result: list[str] = []
    for index, item in enumerate(value):
        if item_predicate is not None:
            if not item_predicate(item) or not isinstance(item, str):
                raise RoutingProfileContractError(
                    f"{path}[{index}] has an invalid identifier"
                )
            result.append(item)
            continue
        if not isinstance(item, str) or not item or len(item) > 128:
            raise RoutingProfileContractError(f"{path}[{index}] must be a non-empty string")
        if pattern is not None and pattern.fullmatch(item) is None:
            raise RoutingProfileContractError(f"{path}[{index}] has an invalid identifier")
        result.append(item)
    if len(set(result)) != len(result):
        raise RoutingProfileContractError(f"{path} must not contain duplicates")
    return tuple(result)


def _decode_match(value: object, *, path: str) -> ProfileMatch:
    document = _object(
        value,
        path=path,
        fields={"objective_keywords", "domains", "tags", "work_modes"},
    )
    keywords = _string_list(
        document["objective_keywords"],
        path=f"{path}.objective_keywords",
        pattern=None,
    )
    domains = _string_list(document["domains"], path=f"{path}.domains")
    tags = _string_list(document["tags"], path=f"{path}.tags")
    work_modes = _string_list(
        document["work_modes"],
        path=f"{path}.work_modes",
        pattern=None,
    )
    if any(mode not in _WORK_MODES for mode in work_modes):
        raise RoutingProfileContractError(f"{path}.work_modes contains an unsupported mode")
    return ProfileMatch(keywords, domains, tags, work_modes)


def _decode_phase(value: object, *, path: str) -> SkillTreePhase:
    document = _object(
        value,
        path=path,
        fields={"phase_id", "primary_skill_id", "support_skill_ids", "exit_gate"},
    )
    phase_id = _identifier(document["phase_id"], path=f"{path}.phase_id")
    primary = document["primary_skill_id"]
    if not is_canonical_skill_id(primary):
        raise RoutingProfileContractError(f"{path}.primary_skill_id must be canonical skill:<id>")
    support = _string_list(
        document["support_skill_ids"],
        path=f"{path}.support_skill_ids",
        pattern=None,
        item_predicate=is_canonical_skill_id,
        maximum=MAX_SUPPORT_SKILLS,
    )
    if primary in support:
        raise RoutingProfileContractError(f"{path} primary skill cannot also be support")
    exit_gate = _identifier(document["exit_gate"], path=f"{path}.exit_gate")
    return SkillTreePhase(phase_id, primary, support, exit_gate)


def _decode_route(value: object, *, path: str) -> ProfileRoute:
    document = _object(value, path=path, fields={"work_mode", "skill_tree"})
    work_mode = document["work_mode"]
    if not isinstance(work_mode, str) or work_mode not in _WORK_MODES:
        raise RoutingProfileContractError(f"{path}.work_mode is unsupported")
    raw_tree = document["skill_tree"]
    if not isinstance(raw_tree, list) or not raw_tree or len(raw_tree) > MAX_PHASES:
        raise RoutingProfileContractError(
            f"{path}.skill_tree must contain between 1 and {MAX_PHASES} phases"
        )
    tree = tuple(
        _decode_phase(item, path=f"{path}.skill_tree[{index}]")
        for index, item in enumerate(raw_tree)
    )
    phase_ids = [phase.phase_id for phase in tree]
    if len(set(phase_ids)) != len(phase_ids):
        raise RoutingProfileContractError(f"{path}.skill_tree phase_id must be unique")
    if work_mode == "single" and len(tree) != 1:
        raise RoutingProfileContractError("single routes must contain exactly one phase")
    return ProfileRoute(work_mode, tree)


def _decode_rule(value: object, *, path: str) -> RoutingProfileRule:
    document = _object(
        value,
        path=path,
        fields={"rule_id", "priority", "match", "route"},
    )
    rule_id = _identifier(document["rule_id"], path=f"{path}.rule_id")
    priority = document["priority"]
    if isinstance(priority, bool) or not isinstance(priority, int) or not -1000 <= priority <= 1000:
        raise RoutingProfileContractError(f"{path}.priority must be an integer from -1000 to 1000")
    return RoutingProfileRule(
        rule_id,
        priority,
        _decode_match(document["match"], path=f"{path}.match"),
        _decode_route(document["route"], path=f"{path}.route"),
    )


def decode_routing_profile(
    value: object,
    *,
    expected_scope: str | None = None,
) -> RoutingPreferenceProfile:
    document = _object(
        value,
        path="profile",
        fields={
            "schema_id",
            "schema_version",
            "artifact_kind",
            "profile_id",
            "scope",
            "enabled",
            "rules",
        },
    )
    if document["schema_id"] != SCHEMA_ID:
        raise RoutingProfileContractError("profile schema_id is unsupported")
    if document["schema_version"] != SCHEMA_VERSION:
        raise RoutingProfileContractError("profile schema_version is unsupported")
    if document["artifact_kind"] != ARTIFACT_KIND:
        raise RoutingProfileContractError("profile artifact_kind is unsupported")
    profile_id = document["profile_id"]
    if not isinstance(profile_id, str) or _PROFILE_ID.fullmatch(profile_id) is None:
        raise RoutingProfileContractError("profile_id must start with personal: or workspace:")
    scope = document["scope"]
    if scope not in {"personal", "workspace"}:
        raise RoutingProfileContractError("profile scope is unsupported")
    if profile_id.split(":", 1)[0] != scope:
        raise RoutingProfileContractError("profile_id and scope must agree")
    if expected_scope is not None and scope != expected_scope:
        raise RoutingProfileContractError(
            f"profile scope {scope!r} does not match source scope {expected_scope!r}"
        )
    enabled = document["enabled"]
    if not isinstance(enabled, bool):
        raise RoutingProfileContractError("profile.enabled must be boolean")
    raw_rules = document["rules"]
    if not isinstance(raw_rules, list) or not raw_rules or len(raw_rules) > MAX_RULES:
        raise RoutingProfileContractError(
            f"profile.rules must contain between 1 and {MAX_RULES} rules"
        )
    rules = tuple(
        _decode_rule(item, path=f"profile.rules[{index}]")
        for index, item in enumerate(raw_rules)
    )
    rule_ids = [rule.rule_id for rule in rules]
    if len(set(rule_ids)) != len(rule_ids):
        raise RoutingProfileContractError("profile rule_id must be unique")
    digest = "sha256:" + hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()
    return RoutingPreferenceProfile(profile_id, scope, enabled, rules, digest)
