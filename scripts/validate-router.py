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
    "README.en.md",
    "README.zh-TW.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    ".github/FUNDING.yml",
    ".github/CODEOWNERS",
    ".github/dependabot.yml",
    ".github/ISSUE_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/general-issue.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/routing-failure.yml",
    ".github/ISSUE_TEMPLATE/example-request.yml",
    "docs/assets/demo-routing-before-after.svg",
    "downloads/README.md",
    "downloads/workflow-skill-router-blank.zip",
    "downloads/workflow-skill-router-template.zip",
    "downloads/workflow-skill-router-template-clean.zip",
    "downloads/workflow-skill-router-template-manifest.md",
    "docs/roadmap.md",
    "scripts/audit-public-readiness.py",
    "site/astro.config.mjs",
    "site/package.json",
    "site/scripts/lighthouse-audit.mjs",
    "site/public/robots.txt",
    "site/public/og/workflow-skill-router.png",
    "site/src/pages/404.astro",
    "site/src/content/docs/index.mdx",
    "site/src/content/docs/zh-tw/index.mdx",
    "site/src/content/docs/reference/validator.md",
    "site/src/content/docs/zh-tw/reference/validator.md",
]

PUBLIC_REQUIRED_DIRS = [
    "starter/workflow-skill-router",
    "examples/template-skill-catalog",
    "sample-skills",
    "recipes",
    "prompts",
]

PUBLIC_FORBIDDEN_PATTERNS = [
    re.compile(r"林口康橋|康橋國際|康橋"),
    re.compile(r"Edit page|編輯頁面", re.IGNORECASE),
    re.compile(r"\uFFFD"),
    re.compile(r"蝜|銝|雿|嚗|摮|頝|餈|瘝|瑼|憭|銴"),
]

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
    "validate-router.py",
}

ROUTE_SKILL_MARKERS = ("Primary:", "Supporting:", "Use SKILL:")
ROUTE_SKILL_PATTERN = re.compile(r"`([A-Za-z0-9][A-Za-z0-9._:/-]{0,100})`")


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


def validate_placeholder_policy(router_dir: Path, issues: list[str]) -> None:
    skill_tree = router_dir / "references" / "skill-tree.md"
    routing_rules = router_dir / "references" / "routing-rules.md"
    if not skill_tree.is_file():
        return

    tree_text = read_text(skill_tree)
    rules_text = read_text(routing_rules) if routing_rules.is_file() else ""
    combined = f"{tree_text}\n{rules_text}"
    placeholder_tokens = [
        "example-",
        "backend-developer",
        "frontend-builder",
        "documentation-writer",
        "github-connector",
        "release-checklist",
    ]
    has_placeholders = any(token in combined for token in placeholder_tokens)
    if not has_placeholders:
        return

    if "PLACEHOLDER ONLY" not in combined:
        issues.append(f"{router_dir}: placeholder skill names must be clearly marked with 'PLACEHOLDER ONLY'")
    if "examples/template-skill-catalog" not in combined:
        issues.append(f"{router_dir}: placeholder starter must link to examples/template-skill-catalog as the concrete template reference")


def validate_example_readme(router_dir: Path, issues: list[str]) -> None:
    parts = {part.lower() for part in router_dir.parts}
    if "examples" in parts and not (router_dir / "README.md").is_file():
        issues.append(f"{router_dir}: example routers must include README.md")


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


def scan_public_text(root: Path, issues: list[str]) -> None:
    for path in iter_public_text_files(root):
        text = read_text(path)
        for pattern in PUBLIC_FORBIDDEN_PATTERNS:
            match = pattern.search(text)
            if match:
                value = match.group(0)
                if value in {"C:\\Users\\<you>\\", "C:\\Users\\<username>\\"}:
                    continue
                issues.append(f"{display_path(path, root)}: public-readiness scan found '{value}'")


def extract_route_skills_from_text(text: str) -> set[str]:
    skills: set[str] = set()
    for line in text.splitlines():
        if not any(marker in line for marker in ROUTE_SKILL_MARKERS):
            continue
        skills.update(match.group(1) for match in ROUTE_SKILL_PATTERN.finditer(line))
    return skills


def extract_route_skills_from_file(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    return extract_route_skills_from_text(read_text(path))


def parse_template_manifest_skills(manifest_path: Path, issues: list[str]) -> set[str]:
    if not manifest_path.is_file():
        issues.append(f"{display_path(manifest_path)}: template manifest is missing")
        return set()

    skills: set[str] = set()
    for line_number, line in enumerate(read_text(manifest_path).splitlines(), start=1):
        match = re.fullmatch(r"- `([^`]+)`", line.strip())
        if not match:
            continue

        folder = match.group(1).strip().strip("/")
        skill_name = folder.split("/")[-1]
        if not skill_name:
            issues.append(f"{manifest_path}:{line_number}: manifest skill folder is empty")
            continue
        skills.add(skill_name)

    if not skills:
        issues.append(f"{display_path(manifest_path)}: template manifest does not list any skill folders")

    return skills


def validate_template_catalog_manifest_parity(root: Path, issues: list[str]) -> None:
    manifest_path = root / "downloads" / "workflow-skill-router-template-manifest.md"
    skill_tree_path = root / "examples" / "template-skill-catalog" / "references" / "skill-tree.md"
    sample_routes_path = root / "examples" / "template-skill-catalog" / "references" / "sample-routes.md"

    manifest_skills = parse_template_manifest_skills(manifest_path, issues)
    if not skill_tree_path.is_file():
        issues.append(f"{display_path(skill_tree_path, root)}: template catalog skill tree is missing")
        return

    catalog_skills = extract_route_skills_from_file(skill_tree_path)
    unknown = sorted(catalog_skills - manifest_skills)
    missing = sorted(manifest_skills - catalog_skills)

    if unknown:
        issues.append(
            f"{display_path(skill_tree_path, root)}: catalog routes use skills not listed in the template manifest: {', '.join(unknown)}"
        )
    if missing:
        issues.append(
            f"{display_path(skill_tree_path, root)}: catalog routes do not cover template manifest skills: {', '.join(missing)}"
        )

    sample_skills = extract_route_skills_from_file(sample_routes_path)
    sample_unknown = sorted(sample_skills - manifest_skills)
    if sample_unknown:
        issues.append(
            f"{display_path(sample_routes_path, root)}: sample routes use skills not listed in the template manifest: {', '.join(sample_unknown)}"
        )

    site_route_paths = [
        root / "site" / "src" / "content" / "docs" / "examples" / "template-skill-catalog.md",
        root / "site" / "src" / "content" / "docs" / "zh-tw" / "examples" / "template-skill-catalog.md",
    ]
    for path in site_route_paths:
        site_skills = extract_route_skills_from_file(path)
        site_unknown = sorted(site_skills - manifest_skills)
        if site_unknown:
            issues.append(
                f"{display_path(path, root)}: site example routes use skills not listed in the template manifest: {', '.join(site_unknown)}"
            )


def validate_required_public_files(root: Path, issues: list[str]) -> None:
    for relative in PUBLIC_REQUIRED_FILES:
        path = root / relative
        if not path.is_file():
            issues.append(f"{relative}: required public-readiness file is missing")
        elif path.suffix == ".zip" and path.stat().st_size == 0:
            issues.append(f"{relative}: download archive is empty")

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
        "docs/assets/demo-routing-before-after.svg",
        "downloads/workflow-skill-router-blank.zip",
        "downloads/workflow-skill-router-template.zip",
        "downloads/workflow-skill-router-template-clean.zip",
        "examples/template-skill-catalog",
        "scripts/validate-router.py",
    ]
    for snippet in required_snippets:
        if snippet not in text:
            issues.append(f"README.md: missing public surface link '{snippet}'")


def validate_single_example_surface(root: Path, issues: list[str]) -> None:
    examples = root / "examples"
    if not examples.is_dir():
        return

    for child in examples.iterdir():
        if not child.is_dir() or child.name == "template-skill-catalog":
            continue
        has_files = any(item.is_file() for item in child.rglob("*"))
        if has_files:
            issues.append(f"examples/{child.name}: public repo should expose the single template-skill-catalog example")


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
    validate_single_example_surface(root, issues)
    validate_site_public_surface(root, issues)
    validate_template_catalog_manifest_parity(root, issues)

    for router in [
        root / "starter" / "workflow-skill-router",
        root / "examples" / "template-skill-catalog",
    ]:
        for issue in validate_router(router):
            issues.append(issue)

    scan_public_text(root, issues)
    return issues


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
    validate_placeholder_policy(router_dir, issues)
    validate_example_readme(router_dir, issues)
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
            "- Backend / API / Contract: Primary: `api-designer`; Supporting: `qa-test-planner`\n",
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

        placeholder = root / "placeholder"
        write_file(
            placeholder / "SKILL.md",
            "---\nname: placeholder-router\ndescription: Invalid router.\n---\n",
            files,
            dirs,
        )
        write_file(
            placeholder / "references" / "skill-tree.md",
            "- Backend / API / Code: Primary: `backend-developer`; Supporting: `test-planning`\n",
            files,
            dirs,
        )
        write_file(placeholder / "references" / "routing-rules.md", "# Routing Rules\n", files, dirs)
        assert any("PLACEHOLDER ONLY" in issue for issue in validate_router(placeholder)), "unmarked placeholders should fail"

        public_root = root / "public-root"
        for relative in PUBLIC_REQUIRED_FILES:
            content = "placeholder\n"
            if relative == "README.md":
                content = "\n".join(
                    [
                        "docs/assets/demo-routing-before-after.svg",
                        "downloads/workflow-skill-router-blank.zip",
                        "downloads/workflow-skill-router-template.zip",
                        "downloads/workflow-skill-router-template-clean.zip",
                        "examples/template-skill-catalog",
                        "scripts/validate-router.py",
                        "",
                    ]
                )
            if relative == "downloads/workflow-skill-router-template-manifest.md":
                content = "\n".join(
                    [
                        "# Workflow Skill Router Template Manifest",
                        "",
                        "Included public-safe skill folders:",
                        "",
                        "- `api-designer`",
                        "- `qa-test-planner`",
                        "",
                    ]
                )
            write_file(public_root / relative, content, files, dirs)

        starter = public_root / "starter" / "workflow-skill-router"
        write_file(
            starter / "SKILL.md",
            "---\nname: workflow-skill-router\ndescription: Valid starter.\n---\n",
            files,
            dirs,
        )
        write_file(
            starter / "references" / "skill-tree.md",
            "PLACEHOLDER ONLY\nexamples/template-skill-catalog\n- Backend / API / Code: Primary: `backend-developer`; Supporting: `test-planning`\n",
            files,
            dirs,
        )
        write_file(
            starter / "references" / "routing-rules.md",
            "PLACEHOLDER ONLY\nexamples/template-skill-catalog\n",
            files,
            dirs,
        )

        example = public_root / "examples" / "template-skill-catalog"
        write_file(
            example / "SKILL.md",
            "---\nname: template-skill-catalog-router\ndescription: Valid example.\n---\n",
            files,
            dirs,
        )
        write_file(
            example / "README.md",
            "# Template Skill Catalog\n",
            files,
            dirs,
        )
        write_file(
            example / "references" / "skill-tree.md",
            "- Backend / API / Contract: Primary: `api-designer`; Supporting: `qa-test-planner`\n",
            files,
            dirs,
        )
        write_file(
            example / "references" / "routing-rules.md",
            "# Routing Rules\n",
            files,
            dirs,
        )
        write_file(
            example / "references" / "sample-routes.md",
            "Use SKILL: `api-designer`, `qa-test-planner`\n",
            files,
            dirs,
        )
        for relative in PUBLIC_REQUIRED_DIRS:
            (public_root / relative).mkdir(parents=True, exist_ok=True)
        assert not validate_public_readiness(public_root), "public-readiness fixture should pass"

        parity_mismatch = root / "parity-mismatch"
        write_file(
            parity_mismatch / "downloads" / "workflow-skill-router-template-manifest.md",
            "\n".join(
                [
                    "# Workflow Skill Router Template Manifest",
                    "",
                    "Included public-safe skill folders:",
                    "",
                    "- `api-designer`",
                    "- `qa-test-planner`",
                    "- `missing-from-catalog`",
                    "",
                ]
            ),
            files,
            dirs,
        )
        write_file(
            parity_mismatch / "examples" / "template-skill-catalog" / "references" / "skill-tree.md",
            "- API / Contract: Primary: `api-designer`; Supporting: `qa-test-planner`\n",
            files,
            dirs,
        )
        parity_issues: list[str] = []
        validate_template_catalog_manifest_parity(parity_mismatch, parity_issues)
        assert any("do not cover template manifest skills" in issue for issue in parity_issues), "manifest/catalog parity mismatch should fail"

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
