"""Portable path validation for release package allowlists."""

from __future__ import annotations

import re
from pathlib import PurePosixPath, PureWindowsPath


WINDOWS_FORBIDDEN_CHARACTERS = frozenset('<>"\\|?*')
WINDOWS_RESERVED_DEVICE_PATTERN = re.compile(
    r"^(?:aux|con|nul|prn|conin\$|conout\$|(?:com|lpt)[0-9\u00b9\u00b2\u00b3])$"
)


def _is_safe_win32_component(component: str) -> bool:
    if component.endswith((".", " ")):
        return False
    if any(
        character in WINDOWS_FORBIDDEN_CHARACTERS or ord(character) < 32
        for character in component
    ):
        return False
    # Win32 reserves device names even when the component adds an extension.
    base_name = component.split(".", maxsplit=1)[0].casefold()
    return WINDOWS_RESERVED_DEVICE_PATTERN.fullmatch(base_name) is None


def parse_safe_relative_posix_path(value: str) -> PurePosixPath:
    """Return a canonical archive-relative path or reject cross-platform escapes."""

    components = value.split("/")
    if (
        not value
        or "\\" in value
        or ":" in value
        or any(part in ("", ".", "..") for part in components)
        or any(not _is_safe_win32_component(part) for part in components)
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
