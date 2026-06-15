#!/usr/bin/env python3
"""Create downloadable Workflow Skill Router packages.

Outputs:

- blank: a ready-to-install `workflow-skill-router/` starter skill
- template: a public-safe skills pack generated from a local Codex skills root

The template package is intended for maintainers who want to publish a sanitized
copy of their real local skill catalog. Private skill names, private prefixes,
and private text markers are supplied at packaging time instead of being written
into this public repository.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS_DIR = REPO_ROOT / "downloads"

BLANK_ZIP = DOWNLOADS_DIR / "workflow-skill-router-blank.zip"
TEMPLATE_ZIP = DOWNLOADS_DIR / "workflow-skill-router-template.zip"
TEMPLATE_MANIFEST = DOWNLOADS_DIR / "workflow-skill-router-template-manifest.md"

DEFAULT_PRIVATE_MARKERS: list[str] = []

SKIP_DIRS = {
    ".git",
    ".github",
    ".astro",
    "node_modules",
    "dist",
    "__pycache__",
}

SKIP_FILE_NAMES = {
    "CREATION-LOG.md",
}

SKIP_FILE_PREFIXES = (
    "test-",
)

TEXT_SUFFIXES = {
    "",
    ".cjs",
    ".css",
    ".csv",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".sh",
    ".svg",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


@dataclass(frozen=True)
class SkillSource:
    source: Path
    archive_name: str
    kind: str


@dataclass
class PackageReport:
    included: list[str]
    excluded_count: int
    sanitized_files: list[str]
    source_root: Path


def split_values(raw_values: list[str] | None, env_name: str) -> list[str]:
    values: list[str] = []
    raw_env = os.environ.get(env_name, "")
    for chunk in raw_env.replace(",", ";").split(";"):
        if chunk.strip():
            values.append(chunk.strip())
    for raw in raw_values or []:
        for chunk in raw.replace(",", ";").split(";"):
            if chunk.strip():
                values.append(chunk.strip())
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skills-root",
        type=Path,
        default=os.environ.get("WORKFLOW_SKILL_ROUTER_SKILLS_ROOT"),
        help="Local Codex skills root to package into the public-safe template.",
    )
    parser.add_argument(
        "--exclude-name",
        action="append",
        default=[],
        help="Skill folder name to exclude from the public template package.",
    )
    parser.add_argument(
        "--exclude-prefix",
        action="append",
        default=[],
        help="Skill folder prefix to exclude from the public template package.",
    )
    parser.add_argument(
        "--private-marker",
        action="append",
        default=[],
        help="Text marker that should be removed from public package contents.",
    )
    parser.add_argument(
        "--allow-no-private-filters",
        action="store_true",
        help="Allow template packaging without exclude-name, exclude-prefix, or private-marker filters.",
    )
    return parser.parse_args()


def should_skip_file(path: Path) -> bool:
    if path.is_dir():
        return True
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    if path.name in SKIP_FILE_NAMES:
        return True
    if any(path.name.startswith(prefix) for prefix in SKIP_FILE_PREFIXES):
        return True
    if path.suffix.lower() in {".pyc", ".pyo"}:
        return True
    return False


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not should_skip_file(path):
            yield path


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES


def contains_marker(text: str, markers: list[str]) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in markers)


def sanitize_lines(text: str, markers: list[str]) -> tuple[str, bool]:
    changed = False
    output: list[str] = []

    for line in text.splitlines():
        if contains_marker(line, markers):
            changed = True
            continue
        output.append(line.rstrip())

    sanitized = "\n".join(output).rstrip() + "\n"
    return sanitized, changed


def parse_frontmatter(text: str) -> tuple[list[str], str]:
    if not text.startswith("---\n"):
        return [], text

    end = text.find("\n---", 4)
    if end == -1:
        return [], text

    frontmatter = text[4:end].strip().splitlines()
    body_start = text.find("\n", end + 4)
    body = text[body_start + 1 :] if body_start != -1 else ""
    return frontmatter, body


def value_after_colon(line: str) -> str:
    return line.split(":", 1)[1].strip().strip("\"'")


def sanitize_skill_markdown(text: str, fallback_name: str, markers: list[str]) -> tuple[str, bool]:
    frontmatter, body = parse_frontmatter(text)
    name = fallback_name
    description = f"Public-safe template copy of the {fallback_name} skill."

    for line in frontmatter:
        if line.startswith("name:") and not contains_marker(line, markers):
            name = value_after_colon(line) or fallback_name
        if line.startswith("description:") and not contains_marker(line, markers):
            description = value_after_colon(line) or description

    sanitized_body, body_changed = sanitize_lines(body, markers)
    sanitized = f"---\nname: {name}\ndescription: {description}\n---\n\n{sanitized_body}"
    return sanitized, body_changed or sanitized != text


def read_text(path: Path) -> str | None:
    if not is_text_file(path):
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            return None


def archive_text(zip_file: zipfile.ZipFile, archive_path: str, text: str) -> None:
    zip_file.writestr(archive_path, text)


def archive_file(zip_file: zipfile.ZipFile, source: Path, archive_path: str) -> None:
    zip_file.write(source, archive_path)


def add_tree(
    zip_file: zipfile.ZipFile,
    source: Path,
    archive_root: str,
    markers: list[str],
    sanitized_files: list[str],
) -> None:
    for path in iter_files(source):
        rel = path.relative_to(source).as_posix()
        archive_path = f"{archive_root}/{rel}"

        text = read_text(path)
        if text is None:
            archive_file(zip_file, path, archive_path)
            continue

        if path.name == "SKILL.md":
            sanitized, changed = sanitize_skill_markdown(text, source.name, markers)
        else:
            sanitized, changed = sanitize_lines(text, markers)

        if changed:
            sanitized_files.append(archive_path)
        archive_text(zip_file, archive_path, sanitized)


def add_text(zip_file: zipfile.ZipFile, archive_path: str, text: str) -> None:
    zip_file.writestr(archive_path, text.strip() + "\n")


def is_excluded_skill(name: str, exclude_names: set[str], exclude_prefixes: list[str]) -> bool:
    if name in exclude_names:
        return True
    return any(name.startswith(prefix) for prefix in exclude_prefixes)


def collect_skill_sources(
    skills_root: Path,
    exclude_names: set[str],
    exclude_prefixes: list[str],
) -> tuple[list[SkillSource], int]:
    sources: list[SkillSource] = []
    excluded_count = 0

    for path in sorted(skills_root.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_dir():
            continue

        if path.name.startswith(".") and path.name != ".system":
            continue

        if path.name == ".system":
            for system_skill in sorted(path.iterdir(), key=lambda item: item.name.lower()):
                if not system_skill.is_dir():
                    continue
                if is_excluded_skill(system_skill.name, exclude_names, exclude_prefixes):
                    excluded_count += 1
                    continue
                sources.append(SkillSource(system_skill, f".system/{system_skill.name}", "system"))
            continue

        if path.name == "workflow-skill-router":
            sources.append(SkillSource(path, "workflow-skill-router", "router"))
            continue

        if is_excluded_skill(path.name, exclude_names, exclude_prefixes):
            excluded_count += 1
            continue

        sources.append(SkillSource(path, path.name, "local"))

    return sources, excluded_count


def validate_zip_private_markers(zip_path: Path, markers: list[str]) -> list[str]:
    issues: list[str] = []
    with zipfile.ZipFile(zip_path) as zip_file:
        for info in zip_file.infolist():
            if info.is_dir():
                continue
            suffix = Path(info.filename).suffix.lower()
            if suffix and suffix not in TEXT_SUFFIXES:
                continue
            try:
                text = zip_file.read(info).decode("utf-8")
            except UnicodeDecodeError:
                continue
            for marker in markers:
                if marker and marker.lower() in text.lower():
                    issues.append(f"Private marker found in archive: {info.filename}")
                    break
    return issues


def build_blank_zip() -> None:
    source = REPO_ROOT / "starter" / "workflow-skill-router"
    with zipfile.ZipFile(BLANK_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for path in iter_files(source):
            rel = path.relative_to(source).as_posix()
            zip_file.write(path, f"workflow-skill-router/{rel}")


def template_readme() -> str:
    return """
# Workflow Skill Router Template Package

This package is a public-safe skills pack generated from the maintainer's real
local Codex skill catalog.

## What is inside

- `skills/`: installable public-safe skill folders.
- `skills/workflow-skill-router/`: a sanitized copy of the maintainer's actual router.
- `MANIFEST.md`: included skill folders and sanitization notes.

Private organization-specific skills are excluded. Private lines inside otherwise
public skills are omitted during packaging.

## Install

Extract the contents of `skills/` into your Codex skills directory.

For Codex on Windows, the install target is usually:

```text
C:\\Users\\<you>\\.codex\\skills
```
"""


def manifest_text(report: PackageReport) -> str:
    included = "\n".join(f"- `{name}`" for name in report.included)

    return f"""
# Workflow Skill Router Template Manifest

Source root: local maintainer Codex skills directory

Included public-safe skill folders:

{included}

Excluded private skill folders: {report.excluded_count}

Sanitized text files: {len(report.sanitized_files)}

Notes:

- Excluded private skill folder names are intentionally not listed in this public manifest.
- Text lines matching private markers are omitted from the package.
- Binary assets are copied only from included public-safe skill folders.
"""


def build_template_zip(
    skills_root: Path,
    exclude_names: set[str],
    exclude_prefixes: list[str],
    private_markers: list[str],
) -> PackageReport:
    if not skills_root.exists():
        raise FileNotFoundError(f"Skills root does not exist: {skills_root}")

    sources, excluded_count = collect_skill_sources(skills_root, exclude_names, exclude_prefixes)
    sanitized_files: list[str] = []
    included_names = [source.archive_name for source in sources]

    with zipfile.ZipFile(TEMPLATE_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        add_text(zip_file, "workflow-skill-router-template/README.md", template_readme())
        for source in sources:
            add_tree(
                zip_file,
                source.source,
                f"workflow-skill-router-template/skills/{source.archive_name}",
                private_markers,
                sanitized_files,
            )

        report = PackageReport(
            included=included_names,
            excluded_count=excluded_count,
            sanitized_files=sanitized_files,
            source_root=skills_root,
        )
        add_text(zip_file, "workflow-skill-router-template/MANIFEST.md", manifest_text(report))

    TEMPLATE_MANIFEST.write_text(manifest_text(report), encoding="utf-8")
    return report


def main() -> int:
    args = parse_args()
    exclude_names = set(split_values(args.exclude_name, "WORKFLOW_SKILL_ROUTER_EXCLUDE_NAMES"))
    exclude_prefixes = split_values(args.exclude_prefix, "WORKFLOW_SKILL_ROUTER_EXCLUDE_PREFIXES")
    private_markers = DEFAULT_PRIVATE_MARKERS + split_values(
        args.private_marker,
        "WORKFLOW_SKILL_ROUTER_PRIVATE_MARKERS",
    )

    if args.skills_root is None:
        print(
            "Missing --skills-root. Refusing to package a template from an implicit local skills directory.",
            file=sys.stderr,
        )
        print(
            "Pass --skills-root plus private filters, or use --allow-no-private-filters only after auditing the source.",
            file=sys.stderr,
        )
        return 1

    if not args.allow_no_private_filters and not (exclude_names or exclude_prefixes or private_markers):
        print(
            "Missing private filters. Add --exclude-name, --exclude-prefix, or --private-marker.",
            file=sys.stderr,
        )
        print(
            "If the source truly has no private content, rerun with --allow-no-private-filters.",
            file=sys.stderr,
        )
        return 1

    DOWNLOADS_DIR.mkdir(exist_ok=True)
    build_blank_zip()

    try:
        report = build_template_zip(
            args.skills_root,
            exclude_names=exclude_names,
            exclude_prefixes=exclude_prefixes,
            private_markers=private_markers,
        )
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    issues = validate_zip_private_markers(TEMPLATE_ZIP, private_markers)
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1

    print(f"Wrote {BLANK_ZIP.relative_to(REPO_ROOT)}")
    print(f"Wrote {TEMPLATE_ZIP.relative_to(REPO_ROOT)}")
    print(f"Wrote {TEMPLATE_MANIFEST.relative_to(REPO_ROOT)}")
    print(f"Included public-safe skill folders: {len(report.included)}")
    print(f"Excluded private skill folders: {report.excluded_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
