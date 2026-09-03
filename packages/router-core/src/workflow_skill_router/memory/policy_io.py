from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import stat
import sys
from typing import Literal

from .models import MemoryPolicy, MemoryPolicyError, MemoryScope
from .policy import decode_policy_text


MAX_POLICY_BYTES = 64 * 1024
POLICY_FILENAMES = (
    "workflow-memory.json",
    "workflow-memory.yaml",
    "workflow-memory.yml",
)
PolicyLoadStatus = Literal["missing", "valid", "invalid", "ambiguous"]
PolicyFormat = Literal["json", "yaml"]


def default_router_data_dir(
    *,
    platform: str | None = None,
    environment: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Return the external Router data root without creating it."""

    values = os.environ if environment is None else environment
    override = values.get("WORKFLOW_SKILL_ROUTER_DATA_DIR")
    if override:
        return Path(override).expanduser()

    current_platform = sys.platform if platform is None else platform
    user_home = Path.home() if home is None else Path(home)
    if current_platform == "win32":
        local_app_data = values.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else user_home / "AppData" / "Local"
        return base / "Codex" / "workflow-skill-router"
    if current_platform == "darwin":
        return (
            user_home
            / "Library"
            / "Application Support"
            / "Codex"
            / "workflow-skill-router"
        )
    state_home = values.get("XDG_STATE_HOME")
    base = Path(state_home) if state_home else user_home / ".local" / "state"
    return base / "codex" / "workflow-skill-router"


@dataclass(frozen=True, slots=True)
class PolicySource:
    scope: MemoryScope
    format: PolicyFormat
    source_class: str
    policy: MemoryPolicy

    def to_public_dict(self) -> dict[str, object]:
        return {
            "scope": self.scope.value,
            "format": self.format,
            "source_class": self.source_class,
            "policy_id": self.policy.policy_id,
            "mode": self.policy.mode.value,
            "policy_digest": self.policy.policy_digest,
        }


@dataclass(frozen=True, slots=True)
class PolicyLoadResult:
    status: PolicyLoadStatus
    source: PolicySource | None
    reason_codes: tuple[str, ...]

    def to_public_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "source": None if self.source is None else self.source.to_public_dict(),
        }


def _is_link_or_reparse(metadata: os.stat_result) -> bool:
    if stat.S_ISLNK(metadata.st_mode):
        return True
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return bool(attributes & reparse_flag)


def _format_for_path(path: Path) -> PolicyFormat:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    raise MemoryPolicyError("unsupported-policy-format")


def _inspect_fixed_directory(path: Path) -> bool:
    """Return False for a missing directory and reject linked/non-directory boundaries."""

    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as error:
        raise MemoryPolicyError("policy-source-unavailable") from error
    if _is_link_or_reparse(metadata):
        raise MemoryPolicyError("policy-source-link-forbidden")
    if not stat.S_ISDIR(metadata.st_mode):
        raise MemoryPolicyError("policy-source-parent-not-directory")
    return True


def _read_policy_text(path: Path) -> str:
    try:
        before = path.lstat()
    except OSError as error:
        raise MemoryPolicyError("policy-source-unavailable") from error
    if _is_link_or_reparse(before):
        raise MemoryPolicyError("policy-source-link-forbidden")
    if not stat.S_ISREG(before.st_mode):
        raise MemoryPolicyError("policy-source-not-regular")
    if before.st_size > MAX_POLICY_BYTES:
        raise MemoryPolicyError("policy-source-too-large")

    flags = os.O_RDONLY
    flags |= int(getattr(os, "O_BINARY", 0))
    flags |= int(getattr(os, "O_CLOEXEC", 0))
    flags |= int(getattr(os, "O_NOFOLLOW", 0))
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise MemoryPolicyError("policy-source-unavailable") from error
    try:
        after = os.fstat(descriptor)
        if _is_link_or_reparse(after) or not stat.S_ISREG(after.st_mode):
            raise MemoryPolicyError("policy-source-not-regular")
        if after.st_size > MAX_POLICY_BYTES:
            raise MemoryPolicyError("policy-source-too-large")
        if (
            getattr(before, "st_dev", None) != getattr(after, "st_dev", None)
            or getattr(before, "st_ino", None) != getattr(after, "st_ino", None)
        ):
            raise MemoryPolicyError("policy-source-changed-during-read")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            content = stream.read(MAX_POLICY_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(content) > MAX_POLICY_BYTES:
        raise MemoryPolicyError("policy-source-too-large")
    try:
        return content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise MemoryPolicyError("policy-source-invalid-utf8") from error


def _load_policy_file(path: Path, expected_scope: MemoryScope) -> tuple[MemoryPolicy, PolicyFormat]:
    source_format = _format_for_path(path)
    text = _read_policy_text(path)
    policy = decode_policy_text(
        text,
        format=source_format,
        expected_scope=expected_scope,
    )
    return policy, source_format


class MemoryPolicyRepository:
    """Read strict Memory Policies from fixed, non-creating locations."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = default_router_data_dir() if data_dir is None else Path(data_dir)

    def inspect_personal(self) -> PolicyLoadResult:
        return self._inspect(
            root=self.data_dir,
            parent=self.data_dir / "config",
            expected_scope=MemoryScope.PERSONAL,
            source_class="personal-policy",
            missing_code="personal-policy-missing",
        )

    def inspect_workspace(self, workspace_root: Path) -> PolicyLoadResult:
        root = Path(workspace_root)
        return self._inspect(
            root=root,
            parent=root / ".codex",
            expected_scope=MemoryScope.WORKSPACE,
            source_class="workspace-policy",
            missing_code="workspace-policy-missing",
        )

    def validate_explicit_file(
        self,
        path: Path,
        expected_scope: MemoryScope,
    ) -> MemoryPolicy:
        policy, _ = _load_policy_file(Path(path), expected_scope)
        return policy

    def memory_store_exists(self) -> bool:
        path = self.data_dir / "memory" / "workflow-memory.sqlite3"
        try:
            metadata = path.lstat()
        except OSError:
            return False
        return stat.S_ISREG(metadata.st_mode) and not _is_link_or_reparse(metadata)

    @staticmethod
    def _candidate_paths(parent: Path) -> tuple[Path, ...]:
        result: list[Path] = []
        for name in POLICY_FILENAMES:
            candidate = parent / name
            try:
                candidate.lstat()
            except OSError:
                continue
            result.append(candidate)
        return tuple(result)

    def _inspect(
        self,
        *,
        root: Path,
        parent: Path,
        expected_scope: MemoryScope,
        source_class: str,
        missing_code: str,
    ) -> PolicyLoadResult:
        try:
            if not _inspect_fixed_directory(root):
                return PolicyLoadResult("missing", None, (missing_code,))
            if not _inspect_fixed_directory(parent):
                return PolicyLoadResult("missing", None, (missing_code,))
        except MemoryPolicyError as error:
            return PolicyLoadResult("invalid", None, (str(error),))

        candidates = self._candidate_paths(parent)
        if not candidates:
            return PolicyLoadResult("missing", None, (missing_code,))
        if len(candidates) > 1:
            return PolicyLoadResult(
                "ambiguous",
                None,
                ("ambiguous-memory-policy",),
            )
        try:
            policy, source_format = _load_policy_file(candidates[0], expected_scope)
        except MemoryPolicyError as error:
            return PolicyLoadResult("invalid", None, (str(error),))
        return PolicyLoadResult(
            "valid",
            PolicySource(
                scope=expected_scope,
                format=source_format,
                source_class=source_class,
                policy=policy,
            ),
            (),
        )


__all__ = [
    "MAX_POLICY_BYTES",
    "MemoryPolicyRepository",
    "PolicyLoadResult",
    "PolicySource",
    "default_router_data_dir",
]
