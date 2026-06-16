#!/usr/bin/env python3
"""Smoke-test release download assets without mutating tracked files."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import zipfile
from pathlib import Path


ASSETS = {
    "blank": "workflow-skill-router-blank.zip",
    "template_clean": "workflow-skill-router-template-clean.zip",
    "template_full": "workflow-skill-router-template.zip",
    "manifest": "workflow-skill-router-template-manifest.md",
}

MANIFEST_PHRASES = [
    "workflow-skill-router-blank.zip",
    "workflow-skill-router-template-clean.zip",
    "workflow-skill-router-template.zip",
    "Excluded private skill folders:",
    "Sanitized text files:",
]


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def require_non_empty_file(path: Path) -> None:
    if not path.is_file():
        fail(f"Missing required asset: {path}")
    if path.stat().st_size <= 0:
        fail(f"Required asset is empty: {path}")


def ensure_clean_target(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        fail(f"Work directory already contains extracted files: {path}")
    path.mkdir(parents=True, exist_ok=True)


def safe_extract(zip_path: Path, target: Path) -> None:
    ensure_clean_target(target)

    with zipfile.ZipFile(zip_path) as archive:
        bad_member = archive.testzip()
        if bad_member:
            fail(f"Corrupt zip member in {zip_path.name}: {bad_member}")

        target_root = target.resolve()
        for member in archive.infolist():
            destination = (target / member.filename).resolve()
            if destination != target_root and target_root not in destination.parents:
                fail(f"Unsafe zip path in {zip_path.name}: {member.filename}")

        archive.extractall(target)


def require_path(path: Path) -> None:
    if not path.exists():
        fail(f"Expected extracted path is missing: {path}")


def validate_blank_router(repo_root: Path, extracted_root: Path) -> None:
    router = extracted_root / "workflow-skill-router"
    require_path(router / "SKILL.md")
    require_path(router / "references" / "skill-tree.md")
    require_path(router / "references" / "routing-rules.md")

    subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "validate-router.py"), str(router)],
        cwd=repo_root,
        check=True,
    )


def validate_template(root: Path, package_dir_name: str) -> None:
    router = root / package_dir_name / "skills" / "workflow-skill-router"
    require_path(router / "SKILL.md")
    require_path(router / "references" / "skill-tree.md")
    require_path(router / "references" / "routing-rules.md")


def validate_manifest(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for phrase in MANIFEST_PHRASES:
        if phrase not in text:
            fail(f"Manifest does not mention required phrase: {phrase}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test Workflow Skill Router release assets.")
    parser.add_argument(
        "--downloads-dir",
        type=Path,
        default=Path("downloads"),
        help="Directory containing release assets.",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        required=True,
        help="Directory where a per-run extraction folder will be created. Existing files are never deleted.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    downloads_dir = args.downloads_dir.resolve()
    work_dir = args.work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    run_dir = work_dir / f"run-{os.getpid()}"
    ensure_clean_target(run_dir)

    paths = {name: downloads_dir / filename for name, filename in ASSETS.items()}
    for path in paths.values():
        require_non_empty_file(path)

    validate_manifest(paths["manifest"])

    blank_root = run_dir / "blank"
    template_clean_root = run_dir / "template-clean"
    template_full_root = run_dir / "template-full"

    safe_extract(paths["blank"], blank_root)
    safe_extract(paths["template_clean"], template_clean_root)
    safe_extract(paths["template_full"], template_full_root)

    validate_blank_router(repo_root, blank_root)
    validate_template(template_clean_root, "workflow-skill-router-template-clean")
    validate_template(template_full_root, "workflow-skill-router-template")

    print(f"OK: release assets smoke test passed ({run_dir})")


if __name__ == "__main__":
    main()
