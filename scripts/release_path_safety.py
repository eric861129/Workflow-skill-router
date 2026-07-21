"""Portable path validation for release package allowlists."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath


def parse_safe_relative_posix_path(value: str) -> PurePosixPath:
    """Return a canonical archive-relative path or reject cross-platform escapes."""

    if (
        not value
        or "\\" in value
        or ":" in value
        or any(part in ("", ".", "..") for part in value.split("/"))
    ):
        raise ValueError(f"unsafe allowlist path: {value!r}")

    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or windows_path.root
    ):
        raise ValueError(f"unsafe allowlist path: {value!r}")
    return posix_path
