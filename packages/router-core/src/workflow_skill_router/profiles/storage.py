from __future__ import annotations

from collections.abc import Mapping
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Any

from workflow_skill_router.schemas.artifacts import canonical_json

from .contract import (
    RoutingPreferenceProfile,
    RoutingProfileContractError,
    decode_routing_profile,
)


MAX_PROFILE_BYTES = 256 * 1024
MAX_PERSONAL_PROFILE_FILES = 32
WORKSPACE_PROFILE_PATH = Path(".codex/workflow-skill-router.json")


def default_router_data_dir(
    *,
    platform: str = sys.platform,
    environment: Mapping[str, str] = os.environ,
    home: Path | None = None,
) -> Path:
    """Return the same user-owned state root used by the Plugin runtime."""

    home = home or Path.home()
    override = environment.get("WORKFLOW_SKILL_ROUTER_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if platform == "win32":
        base = Path(environment.get("LOCALAPPDATA", str(home / "AppData/Local")))
        return base / "Codex/workflow-skill-router"
    if platform == "darwin":
        return home / "Library/Application Support/Codex/workflow-skill-router"
    base = Path(environment.get("XDG_STATE_HOME", str(home / ".local/state")))
    return base / "codex/workflow-skill-router"


def _is_reparse_or_symlink(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)


def _read_document(path: Path) -> Mapping[str, Any]:
    if not path.is_file() or _is_reparse_or_symlink(path):
        raise RoutingProfileContractError(f"profile source must be a regular non-link file: {path}")
    if path.stat().st_size > MAX_PROFILE_BYTES:
        raise RoutingProfileContractError(f"profile exceeds {MAX_PROFILE_BYTES} bytes: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RoutingProfileContractError(f"profile is not valid UTF-8 JSON: {path}") from error
    if not isinstance(value, Mapping):
        raise RoutingProfileContractError(f"profile root must be an object: {path}")
    return value


def load_profile_file(path: Path, *, expected_scope: str | None = None) -> RoutingPreferenceProfile:
    return decode_routing_profile(_read_document(path), expected_scope=expected_scope)


class RoutingProfileRepository:
    """Load user-owned personal and workspace profiles without executing their content."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = (data_dir or default_router_data_dir()).expanduser().resolve()
        self.personal_dir = self.data_dir / "profiles/personal"

    def _ensure_personal_directory(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for path in (self.data_dir / "profiles", self.personal_dir):
            if _is_reparse_or_symlink(path):
                raise RoutingProfileContractError(
                    "personal profile directory cannot be a link or reparse point"
                )
            if path.exists() or path.is_symlink():
                if not path.is_dir():
                    raise RoutingProfileContractError(
                        "personal profile directory cannot be a link or reparse point"
                    )
            else:
                path.mkdir()
            if not path.is_dir() or _is_reparse_or_symlink(path):
                raise RoutingProfileContractError(
                    "personal profile directory cannot be a link or reparse point"
                )
        try:
            self.personal_dir.resolve().relative_to(self.data_dir)
        except ValueError as error:
            raise RoutingProfileContractError(
                "personal profile directory escaped the Router data directory"
            ) from error

    def install_personal(self, source: Path) -> Path:
        source_path = Path(os.path.abspath(source.expanduser()))
        document = _read_document(source_path)
        profile = decode_routing_profile(document, expected_scope="personal")
        destination = self.personal_dir / f"{profile.profile_id.split(':', 1)[1]}.json"
        self._ensure_personal_directory()
        existing = tuple(self.personal_dir.glob("*.json"))
        if not destination.exists() and len(existing) >= MAX_PERSONAL_PROFILE_FILES:
            raise RoutingProfileContractError(
                f"personal profile file count exceeds {MAX_PERSONAL_PROFILE_FILES}"
            )
        if destination.exists() and (
            not destination.is_file() or _is_reparse_or_symlink(destination)
        ):
            raise RoutingProfileContractError(
                "personal profile destination must be a regular non-link file"
            )
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{destination.name}.",
                suffix=".tmp",
                dir=self.personal_dir,
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(canonical_json(document) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
            temporary = None
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
        return destination

    def list_personal(self) -> tuple[RoutingPreferenceProfile, ...]:
        if _is_reparse_or_symlink(self.personal_dir):
            raise RoutingProfileContractError(
                "personal profile directory cannot be a link or reparse point"
            )
        if not self.personal_dir.exists():
            return ()
        self._ensure_personal_directory()
        paths = sorted(self.personal_dir.glob("*.json"), key=lambda item: item.name.casefold())
        if len(paths) > MAX_PERSONAL_PROFILE_FILES:
            raise RoutingProfileContractError(
                f"personal profile file count exceeds {MAX_PERSONAL_PROFILE_FILES}"
            )
        profiles = tuple(load_profile_file(path, expected_scope="personal") for path in paths)
        profile_ids = [profile.profile_id for profile in profiles]
        if len(set(profile_ids)) != len(profile_ids):
            raise RoutingProfileContractError("personal profile_id must be unique across files")
        return profiles

    def load_layers(self, *, workspace_root: Path | None) -> tuple[RoutingPreferenceProfile, ...]:
        profiles = list(self.list_personal())
        if workspace_root is None:
            return tuple(profiles)
        root = workspace_root.expanduser().resolve()
        if not root.is_dir():
            raise RoutingProfileContractError("workspace_root must be an existing directory")
        profile_path = root / WORKSPACE_PROFILE_PATH
        if _is_reparse_or_symlink(profile_path):
            raise RoutingProfileContractError("workspace profile cannot be a link or reparse point")
        if not profile_path.exists():
            return tuple(profiles)
        resolved = profile_path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as error:
            raise RoutingProfileContractError("workspace profile escaped workspace_root") from error
        profiles.append(load_profile_file(resolved, expected_scope="workspace"))
        return tuple(profiles)
