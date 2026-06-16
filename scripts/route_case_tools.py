"""Shared helpers for public route case validation and generation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"

REQUIRED_FIELDS = {
    "id",
    "title",
    "domain",
    "task",
    "context",
    "route",
    "omitted_skills",
    "tags",
    "public_safety",
}

REQUIRED_ROUTE_FIELDS = {"path", "primary", "supporting", "reason"}

PUBLIC_SAFETY_CHECKS = {
    "fictionalized",
    "no_private_paths",
    "no_secrets",
    "no_customer_names",
    "no_live_credentials",
}

ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TAG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SKILL_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*(?::[a-z0-9][a-z0-9-]*)?$")

UNSAFE_TEXT_PATTERNS = [
    (re.compile(r"\b[A-Za-z]:[\\/][^\s\"'`]+"), "local filesystem path"),
    (re.compile(r"\\\\[A-Za-z0-9_.-]+\\[^\s\"'`]+"), "UNC path"),
    (re.compile(r"\b10(?:\.\d{1,3}){3}\b"), "private IP address"),
    (re.compile(r"\b192\.168(?:\.\d{1,3}){2}\b"), "private IP address"),
    (re.compile(r"\b172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}\b"), "private IP address"),
    (re.compile(r"\b(?:localhost|127\.0\.0\.1)\b", re.IGNORECASE), "local host reference"),
    (re.compile(r"\b[\w.-]+\.(?:internal|local|corp)\b", re.IGNORECASE), "private domain"),
    (re.compile(r"\b(?:sk|rk)-[A-Za-z0-9_-]{12,}\b"), "API key shaped token"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{12,}\b"), "GitHub token shaped value"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "GitHub fine-grained token shaped value"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key shaped value"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{12,}\b"), "Slack token shaped value"),
]


@dataclass(frozen=True)
class RouteCase:
    source: Path
    data: dict[str, Any]


def read_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"{path}: invalid JSON: {exc.msg}"]
    except OSError as exc:
        return None, [f"{path}: failed to read file: {exc}"]

    if not isinstance(parsed, dict):
        return None, [f"{path}: route case must be a JSON object"]
    return parsed, []


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def as_non_empty_string(value: Any, field: str, source: Path, errors: list[str]) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    errors.append(f"{source}: field '{field}' must be a non-empty string")
    return ""


def as_string_list(value: Any, field: str, source: Path, errors: list[str]) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{source}: field '{field}' must be a list of strings")
        return []

    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{source}: field '{field}[{index}]' must be a non-empty string")
            continue
        normalized = item.strip().lower()
        if normalized in seen:
            errors.append(f"{source}: field '{field}' contains duplicate value '{normalized}'")
        seen.add(normalized)
        result.append(normalized)
    return result


def iter_text_values(value: Any, prefix: str = "$") -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [(prefix, value)]
    if isinstance(value, dict):
        values: list[tuple[str, str]] = []
        for key, item in value.items():
            values.extend(iter_text_values(item, f"{prefix}.{key}"))
        return values
    if isinstance(value, list):
        values = []
        for index, item in enumerate(value):
            values.extend(iter_text_values(item, f"{prefix}[{index}]"))
        return values
    return []


def validate_public_safety_text(case: dict[str, Any], source: Path, errors: list[str]) -> None:
    for location, text in iter_text_values(case):
        for pattern, label in UNSAFE_TEXT_PATTERNS:
            if pattern.search(text):
                errors.append(f"{source}: {location} contains {label}; route cases must be public-safe")


def validate_omitted_skills(
    value: Any,
    selected_skills: set[str],
    source: Path,
    errors: list[str],
) -> list[dict[str, str]]:
    if not isinstance(value, list):
        errors.append(f"{source}: field 'omitted_skills' must be a list")
        return []

    omitted: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        location = f"omitted_skills[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{source}: field '{location}' must be an object")
            continue
        skill = as_non_empty_string(item.get("skill"), f"{location}.skill", source, errors).lower()
        reason = as_non_empty_string(item.get("reason"), f"{location}.reason", source, errors)
        if skill and not SKILL_PATTERN.match(skill):
            errors.append(f"{source}: field '{location}.skill' must be a skill id")
        if skill in selected_skills:
            errors.append(f"{source}: omitted skill '{skill}' is already selected in the route")
        if skill in seen:
            errors.append(f"{source}: omitted skill '{skill}' is duplicated")
        seen.add(skill)
        if skill and reason:
            omitted.append({"skill": skill, "reason": reason})
    return omitted


def validate_case(case: dict[str, Any], source: Path, seen_ids: dict[str, Path]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []

    missing = sorted(REQUIRED_FIELDS - case.keys())
    if missing:
        errors.append(f"{source}: missing required fields: {', '.join(missing)}")

    case_id = as_non_empty_string(case.get("id"), "id", source, errors)
    if case_id:
        if not ID_PATTERN.match(case_id):
            errors.append(f"{source}: field 'id' must be lowercase kebab-case")
        if source.stem != case_id:
            errors.append(f"{source}: filename must match route case id '{case_id}'")
        if case_id in seen_ids:
            errors.append(f"{source}: duplicate route case id '{case_id}' first seen in {seen_ids[case_id]}")
        seen_ids[case_id] = source

    route = case.get("route")
    if not isinstance(route, dict):
        errors.append(f"{source}: field 'route' must be an object")
        route = {}
    else:
        route_missing = sorted(REQUIRED_ROUTE_FIELDS - route.keys())
        if route_missing:
            errors.append(f"{source}: missing route fields: {', '.join(route_missing)}")

    title = as_non_empty_string(case.get("title"), "title", source, errors)
    domain = as_non_empty_string(case.get("domain"), "domain", source, errors).lower()
    task = as_non_empty_string(case.get("task"), "task", source, errors)
    context = as_non_empty_string(case.get("context"), "context", source, errors)
    route_path = as_non_empty_string(route.get("path"), "route.path", source, errors)
    primary = as_non_empty_string(route.get("primary"), "route.primary", source, errors).lower()
    reason = as_non_empty_string(route.get("reason"), "route.reason", source, errors)
    supporting = as_string_list(route.get("supporting"), "route.supporting", source, errors)
    tags = as_string_list(case.get("tags"), "tags", source, errors)

    if domain and not TAG_PATTERN.match(domain):
        errors.append(f"{source}: field 'domain' must be lowercase kebab-case")
    for tag in tags:
        if not TAG_PATTERN.match(tag):
            errors.append(f"{source}: tag '{tag}' must be lowercase kebab-case")
    if primary and not SKILL_PATTERN.match(primary):
        errors.append(f"{source}: field 'route.primary' must be a skill id")
    for skill in supporting:
        if not SKILL_PATTERN.match(skill):
            errors.append(f"{source}: supporting skill '{skill}' must be a skill id")
    if primary in supporting:
        errors.append(f"{source}: route.primary must not be repeated in route.supporting")
    if primary and len([primary, *supporting]) > 4:
        errors.append(f"{source}: route may select at most 4 skills")

    selected_skills = {primary, *supporting} - {""}
    omitted_skills = validate_omitted_skills(case.get("omitted_skills"), selected_skills, source, errors)

    public_safety = case.get("public_safety")
    if not isinstance(public_safety, dict):
        errors.append(f"{source}: field 'public_safety' must be an object")
        public_safety = {}
    for check in sorted(PUBLIC_SAFETY_CHECKS):
        if public_safety.get(check) is not True:
            errors.append(f"{source}: public_safety.{check} must be true")
    review_notes = public_safety.get("review_notes", "")
    if review_notes is not None and not isinstance(review_notes, str):
        errors.append(f"{source}: public_safety.review_notes must be a string when present")

    validate_public_safety_text(case, source, errors)

    if errors:
        return None, errors

    normalized = {
        "id": case_id,
        "title": title,
        "domain": domain,
        "task": task,
        "context": context,
        "route": {
            "path": route_path,
            "primary": primary,
            "supporting": supporting,
            "reason": reason,
        },
        "omitted_skills": omitted_skills,
        "tags": tags,
        "public_safety": {
            check: True for check in sorted(PUBLIC_SAFETY_CHECKS)
        }
        | {"review_notes": review_notes.strip() if isinstance(review_notes, str) else ""},
    }
    return normalized, []


def load_route_cases(route_cases_dir: Path) -> tuple[list[RouteCase], list[str]]:
    errors: list[str] = []
    cases: list[RouteCase] = []
    seen_ids: dict[str, Path] = {}

    if not route_cases_dir.exists():
        return [], [f"{route_cases_dir}: route cases directory does not exist"]

    json_paths = sorted(route_cases_dir.glob("*.json"))
    if not json_paths:
        return [], [f"{route_cases_dir}: no route case JSON files found"]

    for path in json_paths:
        raw, read_errors = read_json(path)
        if read_errors:
            errors.extend(read_errors)
            continue
        assert raw is not None
        normalized, case_errors = validate_case(raw, path, seen_ids)
        errors.extend(case_errors)
        if normalized is not None:
            cases.append(RouteCase(source=path, data=normalized))

    cases.sort(key=lambda route_case: route_case.data["id"])
    return cases, errors


def build_gallery_data(cases: list[RouteCase]) -> dict[str, Any]:
    case_records = []
    for route_case in cases:
        record = dict(route_case.data)
        record["source_path"] = route_case.source.as_posix()
        record["selected_skill_count"] = 1 + len(record["route"]["supporting"])
        case_records.append(record)

    domains = sorted({case.data["domain"] for case in cases})
    tags = sorted({tag for case in cases for tag in case.data["tags"]})
    return {
        "schema_version": SCHEMA_VERSION,
        "case_count": len(cases),
        "domains": domains,
        "tags": tags,
        "cases": case_records,
    }


def build_evaluation_scenarios(cases: list[RouteCase]) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    for route_case in cases:
        data = route_case.data
        route = data["route"]
        scenarios.append(
            {
                "id": f"route-case-{data['id']}",
                "task": data["task"],
                "context": data["context"],
                "expected": {
                    "primary": route["primary"],
                    "supporting": route["supporting"],
                },
                "forbidden": [item["skill"] for item in data["omitted_skills"]],
                "max_skills": 4,
                "tags": sorted({data["domain"], *data["tags"], "route-case"}),
                "notes": route["reason"],
            }
        )
    return scenarios
