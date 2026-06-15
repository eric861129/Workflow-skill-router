#!/usr/bin/env python3
"""Create downloadable Workflow Skill Router starter packages.

The generated archives are intentionally public-safe:

- blank: a ready-to-install `workflow-skill-router/` starter skill
- template: the blank starter plus common engineering routes and sample skills

No external dependencies are required.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS_DIR = REPO_ROOT / "downloads"

BLANK_ZIP = DOWNLOADS_DIR / "workflow-skill-router-blank.zip"
TEMPLATE_ZIP = DOWNLOADS_DIR / "workflow-skill-router-template.zip"

PUBLIC_SAFE_SOURCES = [
    REPO_ROOT / "starter" / "workflow-skill-router",
    REPO_ROOT / "examples" / "common-engineering-routing",
    REPO_ROOT / "sample-skills",
]

FORBIDDEN_PRIVATE_MARKERS = [
    "KCISLK",
    "Kcislk",
    "康橋",
    "林口",
    "D:\\Project",
    "C:\\Users\\erichuang",
    "ApiCenter",
    "deploy-dev",
    "deploy-prod",
    "school-system",
    "student",
    "parent",
    "teacher",
    "school",
]

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


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SKIP_FILE_NAMES:
            continue
        if any(path.name.startswith(prefix) for prefix in SKIP_FILE_PREFIXES):
            continue
        if path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        yield path


def scan_public_safe(paths: list[Path]) -> list[str]:
    issues: list[str] = []

    for root in paths:
        if not root.exists():
            issues.append(f"Missing source: {root.relative_to(REPO_ROOT)}")
            continue

        for path in iter_files(root):
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            for marker in FORBIDDEN_PRIVATE_MARKERS:
                if marker in text:
                    rel = path.relative_to(REPO_ROOT)
                    issues.append(f"Private marker {marker!r} found in {rel}")

    return issues


def add_tree(zip_file: zipfile.ZipFile, source: Path, archive_root: str) -> None:
    for path in iter_files(source):
        rel = path.relative_to(source).as_posix()
        zip_file.write(path, f"{archive_root}/{rel}")


def add_text(zip_file: zipfile.ZipFile, archive_path: str, text: str) -> None:
    zip_file.writestr(archive_path, text.strip() + "\n")


def build_blank_zip() -> None:
    source = REPO_ROOT / "starter" / "workflow-skill-router"
    with zipfile.ZipFile(BLANK_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        add_tree(zip_file, source, "workflow-skill-router")


def build_template_zip() -> None:
    with zipfile.ZipFile(TEMPLATE_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        add_text(
            zip_file,
            "workflow-skill-router-template/README.md",
            """
# Workflow Skill Router Template Package

This package contains public-safe, copyable skill routing material:

- `starter/workflow-skill-router/`: a blank router skill you can install first.
- `examples/common-engineering-routing/`: realistic route examples with concrete skill names.
- `sample-skills/`: complete sample `SKILL.md` folders that pair with the common routes.

Install the blank router into your agent's skill directory, then use the common engineering example and sample skills as references while filling your own `references/skill-tree.md`.

For Codex on Windows, the install target is usually:

```text
C:\\Users\\<you>\\.codex\\skills\\workflow-skill-router
```
""",
        )
        add_tree(
            zip_file,
            REPO_ROOT / "starter" / "workflow-skill-router",
            "workflow-skill-router-template/starter/workflow-skill-router",
        )
        add_tree(
            zip_file,
            REPO_ROOT / "examples" / "common-engineering-routing",
            "workflow-skill-router-template/examples/common-engineering-routing",
        )
        add_tree(
            zip_file,
            REPO_ROOT / "sample-skills",
            "workflow-skill-router-template/sample-skills",
        )


def main() -> int:
    issues = scan_public_safe(PUBLIC_SAFE_SOURCES)
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1

    DOWNLOADS_DIR.mkdir(exist_ok=True)
    build_blank_zip()
    build_template_zip()

    print(f"Wrote {BLANK_ZIP.relative_to(REPO_ROOT)}")
    print(f"Wrote {TEMPLATE_ZIP.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
