#!/usr/bin/env python3
"""Validate a workflow-skill-router package.

The validator is intentionally dependency-free so it can run in a fresh clone.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path


PRIVATE_PATTERNS = [
    re.compile(r"[A-Z]:\\(?:Project|Projects|Work|Client|Company)\\", re.IGNORECASE),
    re.compile(r"[A-Z]:/(?:Project|Projects|Work|Client|Company)/", re.IGNORECASE),
    re.compile(r"D:\\Project\\", re.IGNORECASE),
    re.compile(r"D:/Project/", re.IGNORECASE),
    re.compile(r"C:\\Users\\[^\\]+\\", re.IGNORECASE),
    re.compile(r"\b(?:internal|private|proprietary)[-_](?:project|repo|system|client)\b", re.IGNORECASE),
    re.compile(r"\b(?:real|production|customer)[-_ ](?:hostname|tenant|token|secret)\b", re.IGNORECASE),
    re.compile(r"\bdeploy-(?:dev|staging|prod)\b", re.IGNORECASE),
    re.compile(r"\b(?:api|access|auth|deploy)[-_ ]?(?:key|token|secret)\b", re.IGNORECASE),
]

TEXT_EXTENSIONS = {".md", ".yaml", ".yml", ".txt"}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_frontmatter(skill_path: Path, issues: list[str]) -> dict[str, str]:
    text = read_text(skill_path)
    if not text.startswith("---\n"):
        issues.append(f"{skill_path}: SKILL.md must start with YAML frontmatter")
        return {}

    end = text.find("\n---\n", 4)
    if end == -1:
        issues.append(f"{skill_path}: SKILL.md frontmatter must close with ---")
        return {}

    raw = text[4:end].strip()
    data: dict[str, str] = {}
    for line_number, line in enumerate(raw.splitlines(), start=2):
        if not line.strip():
            continue
        if ":" not in line:
            issues.append(f"{skill_path}:{line_number}: invalid frontmatter line")
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")

    required = {"name", "description"}
    missing = required - data.keys()
    for key in sorted(missing):
        issues.append(f"{skill_path}: missing required frontmatter key '{key}'")

    extra = set(data.keys()) - required
    for key in sorted(extra):
        issues.append(f"{skill_path}: unsupported frontmatter key '{key}'")

    name = data.get("name", "")
    if name and not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", name):
        issues.append(f"{skill_path}: name must be hyphen-case and under 64 characters")

    if not data.get("description", "").strip():
        issues.append(f"{skill_path}: description must not be empty")

    return data


def validate_references(router_dir: Path, issues: list[str]) -> tuple[Path, Path]:
    references = router_dir / "references"
    skill_tree = references / "skill-tree.md"
    routing_rules = references / "routing-rules.md"

    if not references.is_dir():
        issues.append(f"{router_dir}: missing references/ directory")
    if not skill_tree.is_file():
        issues.append(f"{router_dir}: missing references/skill-tree.md")
    if not routing_rules.is_file():
        issues.append(f"{router_dir}: missing references/routing-rules.md")

    return skill_tree, routing_rules


def validate_routes(skill_tree: Path, issues: list[str]) -> None:
    if not skill_tree.is_file():
        return

    for line_number, line in enumerate(read_text(skill_tree).splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue

        looks_like_route = "Primary:" in stripped or "Supporting:" in stripped or re.search(r":\s*`[^`]+`", stripped)
        if not looks_like_route:
            continue

        if "Primary:" not in stripped:
            issues.append(f"{skill_tree}:{line_number}: route must include 'Primary:'")
            continue

        primary_part = stripped.split("Primary:", 1)[1].split("Supporting:", 1)[0]
        primary_skills = re.findall(r"`([^`]+)`", primary_part)
        all_skills = re.findall(r"`([^`]+)`", stripped)

        if len(primary_skills) != 1:
            issues.append(f"{skill_tree}:{line_number}: route must have exactly one Primary skill")
        if not all_skills:
            issues.append(f"{skill_tree}:{line_number}: route must include at least one skill")
        if len(all_skills) > 4:
            issues.append(f"{skill_tree}:{line_number}: route selects {len(all_skills)} skills; maximum is 4")


def validate_example_readme(router_dir: Path, issues: list[str]) -> None:
    parts = {part.lower() for part in router_dir.parts}
    if "examples" in parts and not (router_dir / "README.md").is_file():
        issues.append(f"{router_dir}: example routers must include README.md")


def scan_privacy(router_dir: Path, issues: list[str]) -> None:
    for path in router_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        text = read_text(path)
        for pattern in PRIVATE_PATTERNS:
            match = pattern.search(text)
            if match:
                issues.append(f"{path}: possible private identifier '{match.group(0)}'")


def validate_router(router_dir: Path) -> list[str]:
    issues: list[str] = []
    if not router_dir.exists():
        return [f"{router_dir}: path does not exist"]
    if not router_dir.is_dir():
        return [f"{router_dir}: path must be a directory"]

    skill_path = router_dir / "SKILL.md"
    if not skill_path.is_file():
        issues.append(f"{router_dir}: missing SKILL.md")
    else:
        parse_frontmatter(skill_path, issues)

    skill_tree, _routing_rules = validate_references(router_dir, issues)
    validate_routes(skill_tree, issues)
    validate_example_readme(router_dir, issues)
    scan_privacy(router_dir, issues)
    return issues


def write_file(path: Path, text: str, files: list[Path], dirs: list[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    root = dirs[0]
    current = path.parent
    while True:
        if current not in dirs:
            dirs.append(current)
        if current == root:
            break
        current = current.parent
    path.write_text(text, encoding="utf-8")
    files.append(path)


def run_self_test() -> int:
    root = Path(tempfile.mkdtemp(prefix="workflow-router-validator-"))
    files: list[Path] = []
    dirs: list[Path] = [root]

    try:
        valid = root / "valid"
        write_file(
            valid / "SKILL.md",
            "---\nname: valid-router\ndescription: Valid router.\n---\n\n# Valid\n",
            files,
            dirs,
        )
        write_file(
            valid / "references" / "skill-tree.md",
            "- Backend / API / Contract: Primary: `api-designer`; Supporting: `backend-developer`, `test-planning`\n",
            files,
            dirs,
        )
        write_file(valid / "references" / "routing-rules.md", "# Routing Rules\n", files, dirs)
        assert not validate_router(valid), "valid fixture should pass"

        too_many = root / "too-many"
        write_file(
            too_many / "SKILL.md",
            "---\nname: too-many-router\ndescription: Invalid router.\n---\n",
            files,
            dirs,
        )
        write_file(
            too_many / "references" / "skill-tree.md",
            "- Backend / API / Contract: Primary: `a`; Supporting: `b`, `c`, `d`, `e`\n",
            files,
            dirs,
        )
        write_file(too_many / "references" / "routing-rules.md", "# Routing Rules\n", files, dirs)
        assert any("maximum is 4" in issue for issue in validate_router(too_many)), "too many skills should fail"

        missing_primary = root / "missing-primary"
        write_file(
            missing_primary / "SKILL.md",
            "---\nname: missing-primary-router\ndescription: Invalid router.\n---\n",
            files,
            dirs,
        )
        write_file(
            missing_primary / "references" / "skill-tree.md",
            "- Backend / API / Contract: `api-designer`, `backend-developer`\n",
            files,
            dirs,
        )
        write_file(missing_primary / "references" / "routing-rules.md", "# Routing Rules\n", files, dirs)
        assert any("Primary" in issue for issue in validate_router(missing_primary)), "missing Primary should fail"

        missing_rules = root / "missing-rules"
        write_file(
            missing_rules / "SKILL.md",
            "---\nname: missing-rules-router\ndescription: Invalid router.\n---\n",
            files,
            dirs,
        )
        write_file(
            missing_rules / "references" / "skill-tree.md",
            "- Backend / API / Contract: Primary: `api-designer`\n",
            files,
            dirs,
        )
        assert any("routing-rules" in issue for issue in validate_router(missing_rules)), "missing routing rules should fail"

        private = root / "private"
        write_file(
            private / "SKILL.md",
            "---\nname: private-router\ndescription: Invalid router.\n---\n",
            files,
            dirs,
        )
        write_file(
            private / "references" / "skill-tree.md",
            "- Backend / API / Contract: Primary: `api-designer`\n\nPrivate path: D:\\Project\\Example\n",
            files,
            dirs,
        )
        write_file(private / "references" / "routing-rules.md", "# Routing Rules\n", files, dirs)
        assert any("private identifier" in issue for issue in validate_router(private)), "private path should fail"

        print("OK: validator self-test passed")
        return 0
    finally:
        for path in reversed(files):
            if path.exists():
                path.unlink()
        for directory in sorted(set(dirs), key=lambda item: len(item.parts), reverse=True):
            if directory.exists():
                try:
                    directory.rmdir()
                except OSError:
                    pass


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate a workflow-skill-router package.")
    parser.add_argument("router_dir", nargs="?", help="Path to a router directory")
    parser.add_argument("--self-test", action="store_true", help="Run validator self-tests")
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    if not args.router_dir:
        parser.error("router_dir is required unless --self-test is used")

    router_dir = Path(args.router_dir)
    issues = validate_router(router_dir)
    if issues:
        for issue in issues:
            print(issue)
        return 1

    print(f"OK: {router_dir.name} passed validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
