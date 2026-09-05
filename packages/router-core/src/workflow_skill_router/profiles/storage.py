from __future__ import annotations

from collections.abc import Mapping
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any

from workflow_skill_router.schemas.artifacts import canonical_json

from .atomic_io import (
    ProfileIOError,
    atomic_write_canonical_json,
    current_json_digest,
    secure_read_json,
)
from .contract import (
    RoutingPreferenceProfile,
    RoutingProfileContractError,
    decode_routing_profile,
)
from .layers import LayeredRoutingProfile, LoadedProfileLayers, ProfileSourceClass


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
    """Load user-owned and Router-managed Profiles without executing content."""

    def __init__(self, data_dir: Path | None = None) -> None:
        candidate = Path(data_dir or default_router_data_dir()).expanduser()
        lexical_data_dir = Path(os.path.abspath(candidate))
        if _is_reparse_or_symlink(lexical_data_dir):
            raise RoutingProfileContractError(
                "Router data directory cannot be a link or reparse point"
            )
        self.data_dir = lexical_data_dir.resolve()
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
        try:
            expected_digest = current_json_digest(destination, self.data_dir)
            atomic_write_canonical_json(
                destination,
                self.data_dir,
                document,
                expected_digest=expected_digest,
                max_bytes=MAX_PROFILE_BYTES,
            )
        except ProfileIOError as error:
            raise RoutingProfileContractError(str(error)) from error
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

    def _load_managed(
        self,
        path: Path,
        *,
        expected_scope: str,
        expected_profile_id: str,
    ) -> tuple[RoutingPreferenceProfile | None, bool]:
        try:
            document = secure_read_json(path, self.data_dir, MAX_PROFILE_BYTES)
            if document is None:
                return None, False
            profile = decode_routing_profile(document, expected_scope=expected_scope)
            if profile.profile_id != expected_profile_id:
                return None, True
            return profile, False
        except (ProfileIOError, RoutingProfileContractError, OSError, ValueError):
            return None, True

    def load_ranked_layers(self, *, workspace_root: Path | None) -> LoadedProfileLayers:
        from workflow_skill_router.memory.managed_profiles import (
            ManagedProfilePathError,
            managed_personal_profile_path,
            managed_workspace_profile_path,
            verify_workspace_root,
        )

        user_personal = self.list_personal()
        managed_personal_path = managed_personal_profile_path(self.data_dir)
        managed_personal, managed_personal_invalid = self._load_managed(
            managed_personal_path,
            expected_scope="personal",
            expected_profile_id="personal:adaptive-memory",
        )
        warnings: list[str] = []
        if managed_personal_invalid:
            warnings.append("managed-profile-invalid")

        workspace_identity = None
        user_workspace = None
        managed_workspace = None
        if workspace_root is not None:
            try:
                workspace_identity = verify_workspace_root(workspace_root)
            except ManagedProfilePathError as error:
                raise RoutingProfileContractError(str(error)) from error
            profile_path = workspace_identity.root / WORKSPACE_PROFILE_PATH
            if _is_reparse_or_symlink(profile_path):
                raise RoutingProfileContractError(
                    "workspace profile cannot be a link or reparse point"
                )
            if profile_path.exists():
                resolved = profile_path.resolve()
                try:
                    resolved.relative_to(workspace_identity.root)
                except ValueError as error:
                    raise RoutingProfileContractError(
                        "workspace profile escaped workspace_root"
                    ) from error
                user_workspace = load_profile_file(
                    resolved, expected_scope="workspace"
                )
            managed_workspace_path = managed_workspace_profile_path(
                self.data_dir, workspace_identity.digest
            )
            managed_workspace, managed_workspace_invalid = self._load_managed(
                managed_workspace_path,
                expected_scope="workspace",
                expected_profile_id="workspace:adaptive-memory",
            )
            if managed_workspace_invalid:
                warnings.append("managed-profile-invalid")

        layers: list[LayeredRoutingProfile] = []
        if user_workspace is not None:
            layers.append(LayeredRoutingProfile(
                user_workspace, ProfileSourceClass.USER_WORKSPACE,
                user_workspace.profile_digest, workspace_identity.digest,
            ))
        if managed_workspace is not None:
            layers.append(LayeredRoutingProfile(
                managed_workspace, ProfileSourceClass.MANAGED_WORKSPACE,
                managed_workspace.profile_digest, workspace_identity.digest,
            ))
        layers.extend(
            LayeredRoutingProfile(
                profile, ProfileSourceClass.USER_PERSONAL,
                profile.profile_digest, None,
            )
            for profile in user_personal
        )
        if managed_personal is not None:
            layers.append(LayeredRoutingProfile(
                managed_personal, ProfileSourceClass.MANAGED_PERSONAL,
                managed_personal.profile_digest, None,
            ))
        return LoadedProfileLayers(
            tuple(sorted(layers, key=lambda item: item.rank)),
            tuple(dict.fromkeys(warnings)),
            None if workspace_identity is None else workspace_identity.digest,
        )

    def load_layers(self, *, workspace_root: Path | None) -> tuple[RoutingPreferenceProfile, ...]:
        # Legacy public API intentionally remains user-owned-only. Managed layers
        # are loaded only through load_ranked_layers so existing callers do not
        # silently change ownership semantics.
        profiles = list(self.list_personal())
        if workspace_root is None:
            return tuple(profiles)
        from workflow_skill_router.memory.managed_profiles import (
            ManagedProfilePathError,
            verify_workspace_root,
        )
        try:
            identity = verify_workspace_root(workspace_root)
        except ManagedProfilePathError as error:
            raise RoutingProfileContractError(str(error)) from error
        profile_path = identity.root / WORKSPACE_PROFILE_PATH
        if _is_reparse_or_symlink(profile_path):
            raise RoutingProfileContractError("workspace profile cannot be a link or reparse point")
        if not profile_path.exists():
            return tuple(profiles)
        resolved = profile_path.resolve()
        try:
            resolved.relative_to(identity.root)
        except ValueError as error:
            raise RoutingProfileContractError("workspace profile escaped workspace_root") from error
        profiles.append(load_profile_file(resolved, expected_scope="workspace"))
        return tuple(profiles)
