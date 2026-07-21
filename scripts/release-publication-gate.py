#!/usr/bin/env python3
"""Fail closed unless trusted release metadata is explicitly publishable."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


PUBLISHABLE_LIFECYCLE = "reviewed-attested-publishable"
REVISION_PATTERN = re.compile(r"[0-9a-f]{40}")
TAG_PATTERN = re.compile(r"v2\.[0-9]+\.[0-9]+(-(alpha|beta|rc)\.[0-9]+)?")


class PublicationGateError(ValueError):
    """指出受信任的 release metadata 尚未符合發布條件。"""


def _required_string(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value:
        raise PublicationGateError(f"Release metadata {key!r} is missing or invalid.")
    return value


def _load_publication_binding(metadata_path: Path) -> tuple[str, str, str]:
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PublicationGateError("Release metadata could not be read.") from error
    if not isinstance(metadata, dict):
        raise PublicationGateError("Release metadata must be a JSON object.")

    lifecycle = _required_string(metadata, "release_lifecycle")
    if lifecycle != PUBLISHABLE_LIFECYCLE:
        raise PublicationGateError(
            f"Release lifecycle {lifecycle!r} is not publishable; expected "
            f"{PUBLISHABLE_LIFECYCLE!r}. A manual confirmation cannot bypass "
            "trusted reviewed and attested release metadata."
        )

    source_revision = _required_string(metadata, "release_source_revision")
    if not REVISION_PATTERN.fullmatch(source_revision):
        raise PublicationGateError("Release metadata source revision is invalid.")

    release_version = _required_string(metadata, "v2_version")
    release_tag = f"v{release_version}"
    if not TAG_PATTERN.fullmatch(release_tag):
        raise PublicationGateError("Release metadata V2 version is invalid.")
    return source_revision, release_version, release_tag


def _verify_trusted_checkout(trusted_revision: str) -> None:
    if not REVISION_PATTERN.fullmatch(trusted_revision):
        raise PublicationGateError("Trusted metadata revision is invalid.")
    try:
        actual_revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
    except subprocess.CalledProcessError as error:
        raise PublicationGateError("Trusted metadata checkout could not be verified.") from error
    if actual_revision != trusted_revision:
        raise PublicationGateError(
            "Release metadata was not read from the trusted dispatch revision."
        )


def _git_show(revision: str, path: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "show", f"{revision}:{path}"],
            text=True,
            encoding="utf-8",
            stderr=subprocess.PIPE,
        )
    except (subprocess.CalledProcessError, UnicodeDecodeError) as error:
        raise PublicationGateError(
            f"Frozen release source is missing or cannot decode {path!r}."
        ) from error


def _verify_allowlist_schema(path: str, allowlist_text: str) -> None:
    try:
        allowlist = json.loads(allowlist_text)
    except json.JSONDecodeError as error:
        raise PublicationGateError(
            f"Frozen release allowlist {path!r} is invalid JSON."
        ) from error
    if not isinstance(allowlist, dict):
        raise PublicationGateError(f"Frozen release allowlist {path!r} is invalid.")

    raw_files = allowlist.get("files")
    if not isinstance(raw_files, list) or not all(
        isinstance(value, str) for value in raw_files
    ):
        raise PublicationGateError(
            f"Frozen release allowlist {path!r} must define string file paths."
        )
    if raw_files != sorted(set(raw_files)):
        raise PublicationGateError(
            f"Frozen release allowlist {path!r} must be sorted and unique."
        )
    for relative_name in raw_files:
        relative_path = PurePosixPath(relative_name)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise PublicationGateError(
                f"Frozen release allowlist {path!r} contains an unsafe file path."
            )


def _verify_frozen_source_contract(
    source_revision: str, release_version: str, release_tag: str
) -> None:
    try:
        subprocess.run(
            ["git", "cat-file", "-e", f"{source_revision}^{{commit}}"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", source_revision, "HEAD"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as error:
        raise PublicationGateError(
            "Declared release source is not a reachable trusted revision."
        ) from error

    try:
        frozen_metadata = json.loads(
            _git_show(source_revision, "release/version.json")
        )
    except json.JSONDecodeError as error:
        raise PublicationGateError("Frozen release metadata is invalid JSON.") from error
    if not isinstance(frozen_metadata, dict) or any(
        frozen_metadata.get(key) != release_version
        for key in ("v2_version", "target_prerelease")
    ):
        raise PublicationGateError(
            "Frozen release metadata does not match trusted release version."
        )

    notes_path = f"release/notes/{release_tag}.md"
    notes = _git_show(source_revision, notes_path)
    if notes != _git_show("HEAD", notes_path):
        raise PublicationGateError(
            "Frozen release notes differ from trusted release contract."
        )
    required_notes = (
        f"# Workflow Skill Router {release_tag}",
        f"workflow-skill-router-plugin-v{release_version}.zip",
        f"workflow-skill-router-skill-v{release_version}.zip",
        "checksums.sha256",
        "maintainer-attestation",
    )
    if any(required not in notes for required in required_notes):
        raise PublicationGateError(
            "Frozen release notes do not match the trusted artifact contract."
        )

    builder_path = "scripts/build-release-artifacts.py"
    builder = _git_show(source_revision, builder_path)
    if builder != _git_show("HEAD", builder_path):
        raise PublicationGateError(
            "Frozen release artifact builder differs from trusted release contract."
        )
    required_builder_contract = (
        'RELEASE / "allowlists" / "plugin-runtime-files.json"',
        'RELEASE / "allowlists" / "skill-package.json"',
        'plugin_name = f"workflow-skill-router-plugin-v{version}.zip"',
        'skill_name = f"workflow-skill-router-skill-v{version}.zip"',
        'output_dir / "checksums.sha256"',
    )
    if any(required not in builder for required in required_builder_contract):
        raise PublicationGateError(
            "Frozen release artifact builder does not match the trusted contract."
        )

    for path in (
        "release/allowlists/plugin-runtime-files.json",
        "release/allowlists/skill-package.json",
    ):
        frozen_allowlist_text = _git_show(source_revision, path)
        if frozen_allowlist_text != _git_show("HEAD", path):
            raise PublicationGateError(
                f"Frozen release allowlist {path!r} differs from trusted release contract."
            )
        _verify_allowlist_schema(path, frozen_allowlist_text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--trusted-revision", required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    arguments = parser.parse_args()

    try:
        _verify_trusted_checkout(arguments.trusted_revision)
        source_revision, release_version, release_tag = _load_publication_binding(
            arguments.metadata
        )
        _verify_frozen_source_contract(
            source_revision, release_version, release_tag
        )
        arguments.github_output.write_text(
            f"source_revision={source_revision}\nrelease_tag={release_tag}\n",
            encoding="utf-8",
            newline="\n",
        )
    except PublicationGateError as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
