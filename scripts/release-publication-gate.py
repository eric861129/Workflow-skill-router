#!/usr/bin/env python3
"""Fail closed unless trusted release metadata is explicitly publishable."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
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


def _load_publication_binding(metadata_path: Path) -> tuple[str, str]:
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

    release_tag = f"v{_required_string(metadata, 'v2_version')}"
    if not TAG_PATTERN.fullmatch(release_tag):
        raise PublicationGateError("Release metadata V2 version is invalid.")
    return source_revision, release_tag


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--trusted-revision", required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    arguments = parser.parse_args()

    try:
        _verify_trusted_checkout(arguments.trusted_revision)
        source_revision, release_tag = _load_publication_binding(arguments.metadata)
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
