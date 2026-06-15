#!/usr/bin/env python3
"""Scan skill markdown files and build a workflow-skill-router inventory."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


IGNORED_DIR_NAMES = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    "site",
    ".next",
    "coverage",
}

LIST_FIELDS = {"domains", "stages", "triggers", "exclusions", "dependencies", "tags"}
METADATA_FIELDS = {
    "id",
    "skill_id",
    "name",
    "description",
    "summary",
    "domains",
    "stages",
    "triggers",
    "exclusions",
    "dependencies",
    "tags",
    "owner",
    "visibility",
    "version",
}

FIELD_ALIASES = {
    "author": "owner",
    "domain": "domains",
    "related-skills": "dependencies",
    "scope": "stages",
}

IGNORED_FRONTMATTER_FIELDS = {"license", "metadata", "output-format", "role"}

PRIVATE_PATTERNS = [
    ("email address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("localhost URL", re.compile(r"https?://(?:localhost|127\.0\.0\.1|\[?::1\]?)(?:[/:?#][^\s)]*)?", re.IGNORECASE)),
    ("internal domain", re.compile(r"\b(?:[A-Za-z0-9-]+\.)+(?:local|internal|intranet)\b|\bintranet\b", re.IGNORECASE)),
    ("token-like string", re.compile(r"\b(?:sk|pk|ghp|xoxb|xoxp|xoxa)[-_][A-Za-z0-9_-]{10,}\b")),
    ("absolute local path", re.compile(r"(?:[A-Za-z]:\\Users\\[^\\\s]+\\|/Users/[^/\s]+/)")),
]

PRIVATE_IP_PATTERN = re.compile(r"\b(?:10|127|172|192)\.(?:\d{1,3}\.){2}\d{1,3}\b")
SAFE_EMAIL_DOMAINS = {"example.com", "example.org", "example.net"}
CREDENTIAL_ASSIGNMENT_PATTERN = re.compile(
    r"^\s*(?:[-*]\s*)?(?:secret|password|credential|api[_ -]?key|access[_ -]?token)\b\s*(?:=|:)\s*['\"]?[A-Za-z0-9_./+=!@#$%^&*-]{8,}",
    re.IGNORECASE | re.MULTILINE,
)


def slugify(value: str, fallback: str = "skill") -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug or fallback


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_inline_list(value: str) -> list[str]:
    value = value.strip()
    if not value:
        return []
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [strip_quotes(item.strip()) for item in inner.split(",") if item.strip()]
    if "," in value:
        return [strip_quotes(item.strip()) for item in value.split(",") if item.strip()]
    return [strip_quotes(value)]


def canonical_key(key: str) -> str:
    return FIELD_ALIASES.get(key, key)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str, bool, list[str]]:
    if not text.startswith("---"):
        return {}, text, False, []

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, False, []

    close_index: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            close_index = index
            break
    if close_index is None:
        return {}, text, False, ["frontmatter is missing closing ---"]

    metadata: dict[str, Any] = {}
    warnings: list[str] = []
    current_key: str | None = None

    for line_number, line in enumerate(lines[1:close_index], start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        is_nested = line[:1].isspace()
        if current_key and stripped.startswith("- "):
            metadata.setdefault(current_key, [])
            if isinstance(metadata[current_key], list):
                metadata[current_key].append(strip_quotes(stripped[2:].strip()))
            else:
                warnings.append(f"frontmatter line {line_number}: list item used after scalar field '{current_key}'")
            continue
        if ":" not in line:
            warnings.append(f"frontmatter line {line_number}: expected key: value")
            current_key = None
            continue
        key, value = line.split(":", 1)
        raw_key = key.strip()
        key = canonical_key(raw_key)
        value = value.strip()
        if raw_key == "metadata":
            current_key = None
            continue
        if not is_nested:
            current_key = None
        if key not in METADATA_FIELDS and raw_key not in IGNORED_FRONTMATTER_FIELDS:
            continue
        current_key = key
        if key in LIST_FIELDS:
            metadata[key] = parse_inline_list(value) if value else []
        else:
            metadata[key] = strip_quotes(value)

    body = "\n".join(lines[close_index + 1 :])
    return metadata, body, True, warnings


def first_h1(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def first_paragraph(body: str) -> str:
    paragraph: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            if paragraph:
                break
            continue
        if stripped.startswith("#"):
            continue
        paragraph.append(stripped)
    return " ".join(paragraph)


def as_list(metadata: dict[str, Any], key: str) -> list[str]:
    value = metadata.get(key, [])
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return parse_inline_list(value)
    return []


def display_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def is_ignored(path: Path) -> bool:
    return any(part in IGNORED_DIR_NAMES for part in path.parts)


def is_skill_file(path: Path, source_root: Path) -> bool:
    if path.suffix.lower() != ".md":
        return False
    if path.name == "SKILL.md":
        return True
    if path.name.lower() == "readme.md":
        return False
    return path.parent == source_root


def iter_skill_files(source_roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for root in source_roots:
        for path in root.rglob("*.md"):
            if is_ignored(path.relative_to(root)):
                continue
            if not path.is_file() or not is_skill_file(path, root):
                continue
            resolved = path.resolve()
            if resolved not in seen:
                files.append(path)
                seen.add(resolved)
    return sorted(files, key=lambda item: display_path(item).lower())


def private_warnings(text: str) -> list[str]:
    warnings: list[str] = []
    for label, pattern in PRIVATE_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(0)
            if label == "email address" and value.rsplit("@", 1)[-1].lower() in SAFE_EMAIL_DOMAINS:
                continue
            warnings.append(f"{label}: {value}")

    for match in CREDENTIAL_ASSIGNMENT_PATTERN.finditer(text):
        warnings.append(f"credential-like assignment: {match.group(0)}")

    for match in PRIVATE_IP_PATTERN.finditer(text):
        value = match.group(0)
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            continue
        if address.is_private or address.is_loopback:
            warnings.append(f"private IP address: {value}")

    return sorted(set(warnings))


def quality_warnings(skill: dict[str, Any], frontmatter_warnings: list[str]) -> list[str]:
    warnings = list(frontmatter_warnings)
    description = skill["description"].strip()
    if not description:
        warnings.append("description is missing")
    elif len(description) < 30:
        warnings.append("description is short; explain when to use the skill")

    for field in ["triggers", "exclusions", "domains", "stages"]:
        if not skill[field]:
            warnings.append(f"missing {field} metadata")
    if len(skill["tags"]) < 1:
        warnings.append("tags are missing or too sparse")

    return sorted(set(warnings))


def parse_skill(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    metadata, body, has_frontmatter, frontmatter_warnings = parse_frontmatter(text)

    source_name = path.parent.name if path.name == "SKILL.md" else path.stem
    skill_id = slugify(str(metadata.get("skill_id") or metadata.get("id") or source_name))
    name = str(metadata.get("name") or first_h1(body) or source_name).strip()
    description = str(metadata.get("description") or metadata.get("summary") or first_paragraph(body)).strip()

    skill = {
        "skill_id": skill_id,
        "name": name,
        "path": display_path(path),
        "description": description,
        "domains": as_list(metadata, "domains"),
        "stages": as_list(metadata, "stages"),
        "triggers": as_list(metadata, "triggers"),
        "exclusions": as_list(metadata, "exclusions"),
        "dependencies": as_list(metadata, "dependencies"),
        "tags": as_list(metadata, "tags"),
        "has_frontmatter": has_frontmatter,
        "private_warnings": private_warnings(text),
        "quality_warnings": [],
    }
    skill["quality_warnings"] = quality_warnings(skill, frontmatter_warnings)
    return skill


def overlap_terms(skill: dict[str, Any]) -> set[str]:
    terms: set[str] = set()
    for field in ["domains", "stages", "triggers", "tags"]:
        for value in skill[field]:
            normalized = slugify(value)
            if normalized:
                terms.add(normalized)
            for token in normalized.split("-"):
                if len(token) >= 3:
                    terms.add(token)
    return terms


def global_warnings(skills: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    by_id: dict[str, list[str]] = {}
    by_name: dict[str, list[str]] = {}

    for skill in skills:
        by_id.setdefault(skill["skill_id"], []).append(skill["path"])
        by_name.setdefault(skill["name"].strip().lower(), []).append(skill["path"])

    for skill_id, paths in sorted(by_id.items()):
        if len(paths) > 1:
            warnings.append(f"duplicate skill_id '{skill_id}' in {', '.join(paths)}")

    for name, paths in sorted(by_name.items()):
        if name and len(paths) > 1:
            warnings.append(f"duplicate name '{name}' in {', '.join(paths)}")

    term_sets = {skill["skill_id"]: overlap_terms(skill) for skill in skills}
    for index, left in enumerate(skills):
        for right in skills[index + 1 :]:
            left_terms = term_sets[left["skill_id"]]
            right_terms = term_sets[right["skill_id"]]
            if not left_terms or not right_terms:
                continue
            intersection = left_terms & right_terms
            union = left_terms | right_terms
            if len(intersection) >= 3 and len(intersection) / len(union) >= 0.5:
                warnings.append(
                    "overlap heuristic: "
                    f"{left['skill_id']} and {right['skill_id']} share {', '.join(sorted(intersection))}"
                )

    return sorted(set(warnings))


def build_index(source_paths: list[Path], generated_at: str) -> dict[str, Any]:
    skills = [parse_skill(path) for path in iter_skill_files(source_paths)]
    warnings = global_warnings(skills)
    for skill in skills:
        for warning in skill["private_warnings"]:
            warnings.append(f"{skill['skill_id']}: {warning}")
        for warning in skill["quality_warnings"]:
            warnings.append(f"{skill['skill_id']}: {warning}")

    return {
        "generated_at": generated_at,
        "source_paths": [display_path(path) for path in source_paths],
        "skill_count": len(skills),
        "skills": skills,
        "warnings": sorted(set(warnings)),
    }


def markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return lines


def render_markdown(index: dict[str, Any]) -> str:
    lines = [
        "# Skill Index",
        "",
        f"Generated at: `{index['generated_at']}`",
        f"Skill count: `{index['skill_count']}`",
        "",
    ]
    rows = [
        [
            skill["skill_id"],
            skill["name"],
            ", ".join(skill["domains"]) or "-",
            ", ".join(skill["stages"]) or "-",
            skill["path"],
        ]
        for skill in index["skills"]
    ]
    lines.extend(markdown_table(["Skill ID", "Name", "Domains", "Stages", "Path"], rows or [["-", "-", "-", "-", "-"]]))
    lines.append("")
    return "\n".join(lines)


def render_warnings(index: dict[str, Any]) -> str:
    lines = ["# Skill Scan Warnings", ""]
    if not index["warnings"]:
        lines.extend(["No warnings.", ""])
        return "\n".join(lines)

    lines.extend(["## All Warnings", ""])
    for warning in index["warnings"]:
        lines.append(f"- {warning}")
    lines.append("")

    lines.extend(["## Skill Details", ""])
    for skill in index["skills"]:
        warnings = [*skill["private_warnings"], *skill["quality_warnings"]]
        if not warnings:
            continue
        lines.append(f"### {skill['skill_id']}")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")
    return "\n".join(lines)


def render_suggested_tree(index: dict[str, Any]) -> str:
    tree: dict[str, dict[str, list[str]]] = {}
    metadata_gaps: list[str] = []

    for skill in index["skills"]:
        domains = skill["domains"] or ["Uncategorized"]
        stages = skill["stages"] or ["Uncategorized"]
        if "Uncategorized" in domains or "Uncategorized" in stages:
            metadata_gaps.append(skill["skill_id"])
        for domain in domains:
            domain_label = domain.strip().title() if domain != "Uncategorized" else "Uncategorized"
            for stage in stages:
                stage_label = stage.strip().title() if stage != "Uncategorized" else "Uncategorized"
                tree.setdefault(domain_label, {}).setdefault(stage_label, []).append(skill["skill_id"])

    lines = [
        "# Suggested Skill Tree",
        "",
        "This tree is generated from domains and stages metadata. Overlap detection is a deterministic keyword heuristic, not semantic analysis.",
        "",
    ]
    for domain in sorted(tree):
        lines.append(f"## {domain}")
        lines.append("")
        for stage in sorted(tree[domain]):
            lines.append(f"### {stage}")
            for skill_id in sorted(set(tree[domain][stage])):
                lines.append(f"- {skill_id}")
            lines.append("")

    if metadata_gaps:
        lines.extend(["## Metadata Gaps", ""])
        for skill_id in sorted(set(metadata_gaps)):
            lines.append(f"- {skill_id}")
        lines.append("")
    return "\n".join(lines)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def default_generated_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan skill markdown files and generate inventory reports.")
    parser.add_argument("paths", nargs="+", type=Path, help="One or more skill catalog directories to scan.")
    parser.add_argument("--out", type=Path, help="Write a JSON skill index to this path.")
    parser.add_argument("--markdown", type=Path, help="Write a Markdown skill summary to this path.")
    parser.add_argument("--warnings", type=Path, help="Write a Markdown warnings report to this path.")
    parser.add_argument("--suggest-tree", type=Path, help="Write a suggested skill tree Markdown report to this path.")
    parser.add_argument("--fail-on-private", action="store_true", help="Exit non-zero when public-safety warnings are found.")
    parser.add_argument("--fail-on-duplicates", action="store_true", help="Exit non-zero when duplicate skill ids or names are found.")
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        help="Print the index to stdout in the selected format when no output path is supplied.",
    )
    parser.add_argument(
        "--generated-at",
        help="Override generated_at for deterministic examples, e.g. 2026-01-01T00:00:00Z.",
    )
    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    missing = [path for path in args.paths if not path.exists() or not path.is_dir()]
    if missing:
        for path in missing:
            print(f"{path}: scan path must be an existing directory", file=sys.stderr)
        return 1

    index = build_index(args.paths, args.generated_at or default_generated_at())

    if args.out:
        write_text(args.out, json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    if args.markdown:
        write_text(args.markdown, render_markdown(index))
    if args.warnings:
        write_text(args.warnings, render_warnings(index))
    if args.suggest_tree:
        write_text(args.suggest_tree, render_suggested_tree(index))

    if args.format == "json" and not args.out:
        print(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True))
    if args.format == "markdown" and not args.markdown:
        print(render_markdown(index))

    has_private = any(skill["private_warnings"] for skill in index["skills"])
    has_duplicates = any(warning.startswith("duplicate skill_id") or warning.startswith("duplicate name") for warning in index["warnings"])
    if args.fail_on_private and has_private:
        return 1
    if args.fail_on_duplicates and has_duplicates:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
