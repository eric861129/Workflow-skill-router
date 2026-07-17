#!/usr/bin/env python3
"""Validate a workflow-skill-router package.

The validator is intentionally dependency-free so it can run in a fresh clone.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

TEXT_EXTENSIONS = {".md", ".yaml", ".yml", ".txt"}
PUBLIC_TEXT_EXTENSIONS = TEXT_EXTENSIONS | {
    ".css",
    ".html",
    ".js",
    ".json",
    ".mdx",
    ".mjs",
    ".py",
    ".svg",
    ".toml",
}

PUBLIC_REQUIRED_FILES = [
    "README.md",
    "README.zh-TW.md",
    "CHANGELOG.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "GOVERNANCE.md",
    "MAINTAINERS.md",
    "SUPPORT.md",
    ".github/FUNDING.yml",
    ".github/CODEOWNERS",
    ".github/dependabot.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/routing-failure.yml",
    ".github/ISSUE_TEMPLATE/plugin-runtime-bug.yml",
    ".github/ISSUE_TEMPLATE/evaluation-case.yml",
    "docs/architecture/v2-overview.md",
    "docs/adr/0001-v2-first-public-surface.md",
    "docs/adr/0002-release-assets-outside-git.md",
    "evaluation/v2/README.md",
    "evaluation/v2/cases/behavior-routing.jsonl",
    "evaluation/v2/profiles/beta-smoke.json",
    "packages/router-core/pyproject.toml",
    "plugins/workflow-skill-router/.codex-plugin/plugin.json",
    "plugins/workflow-skill-router/.mcp.json",
    "plugins/workflow-skill-router/package.json",
    "plugins/workflow-skill-router/mcp/server.bundle.mjs",
    "plugins/workflow-skill-router/runtime/workflow_skill_router.pyz",
    "release/version.json",
    "release/public-surface-policy.json",
    "release/legacy-v1-removal-manifest.json",
    "scripts/build-release-artifacts.py",
    "scripts/build-v2-demo-data.py",
    "scripts/audit-public-readiness.py",
    "scripts/check-markdown-links.py",
    "scripts/check-doc-parity.py",
    "scripts/run-v2-benchmark.py",
    "scripts/validate-router.py",
    "starter/v2/workflow-skill-router/SKILL.md",
    "starter/v2/workflow-skill-router/references/routing-protocol.md",
    "starter/v2/workflow-skill-router/references/goal-protocol.md",
    "starter/v2/workflow-skill-router/references/evaluation-boundary.md",
    "site/astro.config.mjs",
    "site/package.json",
    "site/public/robots.txt",
    "site/public/og/workflow-skill-router.png",
    "site/src/pages/404.astro",
    "site/src/content/docs/index.mdx",
    "site/src/content/docs/zh-tw/index.mdx",
    "site/src/content/docs/reference/validator.md",
    "site/src/content/docs/zh-tw/reference/validator.md",
]

PUBLIC_REQUIRED_DIRS = [
    "docs/adr",
    "docs/architecture",
    "evaluation/v2",
    "packages/router-core/src",
    "plugins/workflow-skill-router",
    "release/allowlists",
    "starter/v2/workflow-skill-router",
    "site/src/content/docs",
]

MOJIBAKE_MARKERS = [chr(codepoint) for codepoint in (0x875C, 0x929D, 0x96FF, 0x5697, 0x646E, 0x981D, 0x9908, 0x761D, 0x747C, 0x61AD, 0x92B4)]
PUBLIC_FORBIDDEN_PATTERNS = [
    re.compile("|".join(["Edit " + "page", r"\u7de8\u8f2f\u9801\u9762"]), re.IGNORECASE),
    re.compile(r"\uFFFD"),
    re.compile("|".join(re.escape(marker) for marker in MOJIBAKE_MARKERS)),
]
PUBLIC_FORBIDDEN_MARKERS_ENV = "WORKFLOW_SKILL_ROUTER_PUBLIC_FORBIDDEN_MARKERS"

PUBLIC_SKIP_DIR_NAMES = {
    ".astro",
    ".git",
    ".github-cache",
    ".pagefind",
    ".vercel",
    "dist",
    "node_modules",
    "pagefind",
    "playwright-report",
    "test-results",
}

PUBLIC_SKIP_FILE_NAMES = {
    "site-preview.err.log",
    "site-preview.log",
}

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def display_path(path: Path, base: Path | None = None) -> str:
    if base is None:
        return str(path)
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


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


def should_skip_public_path(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True

    if path.name in PUBLIC_SKIP_FILE_NAMES:
        return True

    for part in relative.parts:
        lowered = part.lower()
        if lowered in PUBLIC_SKIP_DIR_NAMES:
            return True
        if lowered.startswith(".chrome"):
            return True
    return False


def iter_public_text_files(root: Path):
    for path in root.rglob("*"):
        if should_skip_public_path(path, root):
            continue
        if not path.is_file() or path.suffix.lower() not in PUBLIC_TEXT_EXTENSIONS:
            continue
        yield path


def iter_public_forbidden_patterns():
    yield from PUBLIC_FORBIDDEN_PATTERNS

    raw_markers = os.environ.get(PUBLIC_FORBIDDEN_MARKERS_ENV, "")
    for marker in re.split(r"[\r\n;]+", raw_markers):
        marker = marker.strip()
        if marker:
            yield re.compile(re.escape(marker))


def scan_public_text(root: Path, issues: list[str]) -> None:
    for path in iter_public_text_files(root):
        text = read_text(path)
        for pattern in iter_public_forbidden_patterns():
            match = pattern.search(text)
            if match:
                value = match.group(0)
                if value in {"C:\\Users\\<you>\\", "C:\\Users\\<username>\\"}:
                    continue
                issues.append(f"{display_path(path, root)}: public-readiness scan found '{value}'")


def validate_required_public_files(root: Path, issues: list[str]) -> None:
    for relative in PUBLIC_REQUIRED_FILES:
        path = root / relative
        if not path.is_file():
            issues.append(f"{relative}: required public-readiness file is missing")
        elif path.suffix.lower() in {".mp4", ".png", ".webm", ".zip"} and path.stat().st_size == 0:
            issues.append(f"{relative}: required binary asset is empty")

    for relative in PUBLIC_REQUIRED_DIRS:
        path = root / relative
        if not path.is_dir():
            issues.append(f"{relative}: required public-readiness directory is missing")


def validate_readme_public_surface(root: Path, issues: list[str]) -> None:
    readme = root / "README.md"
    if not readme.is_file():
        return

    text = read_text(readme)
    required_snippets = [
        "plugins/workflow-skill-router/runtime/workflow_skill_router.pyz",
        "starter\\v2\\workflow-skill-router",
        "site/src/content/docs/guides/install-plugin.md",
        "site/src/content/docs/guides/install-skill.md",
        "release/version.json",
    ]
    for snippet in required_snippets:
        if snippet not in text:
            issues.append(f"README.md: missing public surface link '{snippet}'")


def validate_v2_skill(skill_root: Path, issues: list[str]) -> None:
    """驗證 V2 instruction fallback，不套用已退休的 V1 route-table 格式。"""
    skill_path = skill_root / "SKILL.md"
    if not skill_path.is_file():
        issues.append(f"{display_path(skill_root)}: missing SKILL.md")
        return
    parse_frontmatter(skill_path, issues)

    required_references = (
        "routing-protocol.md",
        "goal-protocol.md",
        "evaluation-boundary.md",
    )
    for name in required_references:
        path = skill_root / "references" / name
        if not path.is_file():
            issues.append(f"{display_path(path)}: required V2 reference is missing")

    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in skill_root.rglob("*.md")
        if path.is_file()
    )
    for marker in (
        "single",
        "phased",
        "managed-goal",
        "explicit-locked",
        "skill-only-fallback",
        "capability snapshot",
    ):
        if marker not in text:
            issues.append(f"{display_path(skill_root)}: missing V2 routing marker '{marker}'")


def validate_site_public_surface(root: Path, issues: list[str]) -> None:
    site_root = root / "site" / "src" / "content" / "docs"
    old_example_slugs = [
        "common-engineering",
        "company-platform",
        "frontend-debugging",
    ]
    for slug in old_example_slugs:
        if (site_root / "examples" / f"{slug}.md").exists():
            issues.append(f"site examples: stale example page '{slug}' should not be published")
        if (site_root / "zh-tw" / "examples" / f"{slug}.md").exists():
            issues.append(f"site zh-tw examples: stale example page '{slug}' should not be published")


def validate_public_readiness(root: Path) -> list[str]:
    issues: list[str] = []
    if not root.exists():
        return [f"{root}: path does not exist"]
    if not root.is_dir():
        return [f"{root}: path must be a repository directory"]

    validate_required_public_files(root, issues)
    validate_readme_public_surface(root, issues)
    validate_site_public_surface(root, issues)
    validate_v2_skill(root / "starter" / "v2" / "workflow-skill-router", issues)

    scan_public_text(root, issues)
    return issues


def validate_router(router_dir: Path) -> list[str]:
    issues: list[str] = []
    if not router_dir.exists():
        return [f"{router_dir}: path does not exist"]
    if not router_dir.is_dir():
        return [f"{router_dir}: path must be a directory"]

    validate_v2_skill(router_dir, issues)
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
        valid = root / "valid-v2"
        write_file(
            valid / "SKILL.md",
            "---\nname: valid-router\ndescription: Valid V2 router.\n---\n\n"
            "single phased managed-goal explicit-locked skill-only-fallback\n"
            "capability snapshot\n",
            files,
            dirs,
        )
        for name in ("routing-protocol.md", "goal-protocol.md", "evaluation-boundary.md"):
            write_file(valid / "references" / name, f"# {name}\n", files, dirs)
        assert not validate_router(valid), "valid V2 fixture should pass"

        missing_reference = root / "missing-reference"
        write_file(
            missing_reference / "SKILL.md",
            read_text(valid / "SKILL.md"),
            files,
            dirs,
        )
        write_file(missing_reference / "references" / "routing-protocol.md", "# routing\n", files, dirs)
        write_file(missing_reference / "references" / "goal-protocol.md", "# goal\n", files, dirs)
        assert any(
            "evaluation-boundary.md" in issue for issue in validate_router(missing_reference)
        ), "missing V2 reference should fail"

        missing_marker = root / "missing-marker"
        write_file(
            missing_marker / "SKILL.md",
            "---\nname: missing-marker-router\ndescription: Invalid V2 router.\n---\n\n"
            "single phased managed-goal explicit-locked skill-only-fallback\n",
            files,
            dirs,
        )
        for name in ("routing-protocol.md", "goal-protocol.md", "evaluation-boundary.md"):
            write_file(missing_marker / "references" / name, f"# {name}\n", files, dirs)
        assert any(
            "capability snapshot" in issue for issue in validate_router(missing_marker)
        ), "missing V2 marker should fail"

        public_root = root / "public-root"
        for relative in PUBLIC_REQUIRED_FILES:
            content = "placeholder\n"
            if relative == "README.md":
                content = "\n".join(
                    [
                        "plugins/workflow-skill-router/runtime/workflow_skill_router.pyz",
                        r"starter\v2\workflow-skill-router",
                        "site/src/content/docs/guides/install-plugin.md",
                        "site/src/content/docs/guides/install-skill.md",
                        "release/version.json",
                        "",
                    ]
                )
            write_file(public_root / relative, content, files, dirs)

        starter = public_root / "starter" / "v2" / "workflow-skill-router"
        write_file(
            starter / "SKILL.md",
            "\n".join(
                [
                    "---",
                    "name: workflow-skill-router",
                    "description: Valid V2 starter.",
                    "---",
                    "single phased managed-goal explicit-locked skill-only-fallback",
                    "capability snapshot",
                    "",
                ]
            ),
            files,
            dirs,
        )
        for name in (
            "routing-protocol.md",
            "goal-protocol.md",
            "evaluation-boundary.md",
        ):
            write_file(
                starter / "references" / name,
                f"# {name}\n",
                files,
                dirs,
            )
        for relative in PUBLIC_REQUIRED_DIRS:
            (public_root / relative).mkdir(parents=True, exist_ok=True)
        assert not validate_public_readiness(public_root), "public-readiness fixture should pass"

        scanned_paths = {path.relative_to(public_root).as_posix() for path in iter_public_text_files(public_root)}
        assert "scripts/validate-router.py" in scanned_paths, "public-readiness should scan validator source"

        synthetic_marker = "PUBLIC_READINESS_SYNTHETIC_PRIVATE_MARKER"
        previous_markers = os.environ.get(PUBLIC_FORBIDDEN_MARKERS_ENV)
        try:
            os.environ[PUBLIC_FORBIDDEN_MARKERS_ENV] = synthetic_marker
            (public_root / "scripts" / "validate-router.py").write_text(
                f"{synthetic_marker}\n",
                encoding="utf-8",
            )
            marker_issues = validate_public_readiness(public_root)
            assert any(synthetic_marker in issue for issue in marker_issues), "env marker should fail public-readiness"
        finally:
            if previous_markers is None:
                os.environ.pop(PUBLIC_FORBIDDEN_MARKERS_ENV, None)
            else:
                os.environ[PUBLIC_FORBIDDEN_MARKERS_ENV] = previous_markers
            (public_root / "scripts" / "validate-router.py").write_text("placeholder\n", encoding="utf-8")

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
    parser.add_argument("path", nargs="?", help="Path to a router directory, or repository root with --public-readiness")
    parser.add_argument("--public-readiness", action="store_true", help="Audit the public repository surface before publishing")
    parser.add_argument("--self-test", action="store_true", help="Run validator self-tests")
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    target = Path(args.path or ".")

    if args.public_readiness:
        issues = validate_public_readiness(target)
        if issues:
            for issue in issues:
                print(issue)
            return 1

        print("OK: public-readiness audit passed")
        return 0

    if not args.path:
        parser.error("path is required unless --self-test or --public-readiness is used")

    issues = validate_router(target)
    if issues:
        for issue in issues:
            print(issue)
        return 1

    print(f"OK: {target.name} passed validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
