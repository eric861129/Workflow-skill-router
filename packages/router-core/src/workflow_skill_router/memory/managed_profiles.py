from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat


_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class ManagedProfilePathError(ValueError):
    """Raised when a managed Profile identity or fixed path is unsafe."""


def _absolute(path: Path) -> Path:
    expanded = Path(path).expanduser()
    return expanded if expanded.is_absolute() else Path.cwd() / expanded


def _is_link_or_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as error:
        raise ManagedProfilePathError("workspace-root-unavailable") from error
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    reparse = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse)


@dataclass(frozen=True, slots=True)
class VerifiedWorkspaceIdentity:
    root: Path
    digest: str

    def __post_init__(self) -> None:
        if not self.root.is_absolute():
            raise ManagedProfilePathError("workspace-root-not-absolute")
        if _DIGEST.fullmatch(self.digest) is None:
            raise ManagedProfilePathError("invalid-workspace-digest")


def verify_workspace_root(workspace_root: Path) -> VerifiedWorkspaceIdentity:
    """Bind a real, non-link Workspace root to a path-free SHA-256 identity."""

    root = _absolute(workspace_root).absolute()
    if _is_link_or_reparse(root):
        raise ManagedProfilePathError("workspace-root-link-forbidden")
    try:
        metadata = root.lstat()
    except FileNotFoundError as error:
        raise ManagedProfilePathError("workspace-root-missing") from error
    except OSError as error:
        raise ManagedProfilePathError("workspace-root-unavailable") from error
    if not stat.S_ISDIR(metadata.st_mode):
        raise ManagedProfilePathError("workspace-root-not-directory")
    try:
        resolved = root.resolve(strict=True)
    except OSError as error:
        raise ManagedProfilePathError("workspace-root-unavailable") from error
    if _is_link_or_reparse(resolved):
        raise ManagedProfilePathError("workspace-root-link-forbidden")
    digest = "sha256:" + hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()
    return VerifiedWorkspaceIdentity(resolved, digest)


def managed_personal_profile_path(data_dir: Path) -> Path:
    return _absolute(data_dir).absolute() / "profiles/managed/personal/adaptive-memory.json"


def managed_workspace_profile_path(data_dir: Path, workspace_digest: str) -> Path:
    if not isinstance(workspace_digest, str) or _DIGEST.fullmatch(workspace_digest) is None:
        raise ManagedProfilePathError("invalid-workspace-digest")
    component = workspace_digest.removeprefix("sha256:")
    return (
        _absolute(data_dir).absolute()
        / "profiles"
        / "managed"
        / "workspace"
        / component
        / "adaptive-memory.json"
    )


__all__ = [
    "ManagedProfilePathError",
    "VerifiedWorkspaceIdentity",
    "managed_personal_profile_path",
    "managed_workspace_profile_path",
    "verify_workspace_root",
]
