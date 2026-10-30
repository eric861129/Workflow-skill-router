"""Host profiles 由執行環境設定，不接受模型輸入，也不授與任何權限。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path


HOST_ENVIRONMENT_VARIABLE = "WORKFLOW_SKILL_ROUTER_HOST"
WORKSPACE_PROFILE_FILENAME = "workflow-skill-router.json"


class HostProfileError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class HostProfile:
    """單一 Host 的固定 workspace 設定位置；第一個目錄是 Host 原生位置。"""

    host_id: str
    display_name: str
    workspace_config_dirs: tuple[str, ...]


CODEX = HostProfile("codex", "Codex", (".codex",))
# Claude Code 優先讀 .claude/，沒有時沿用 .codex/，讓兩個 Host 可共用同一份 workspace 設定。
CLAUDE_CODE = HostProfile("claude-code", "Claude Code", (".claude", ".codex"))
HOST_PROFILES = {profile.host_id: profile for profile in (CODEX, CLAUDE_CODE)}


def current_host(environment: Mapping[str, str] | None = None) -> HostProfile:
    """未設定時維持 Codex；未知值 fail closed，避免默默套用錯誤路徑。"""

    values = os.environ if environment is None else environment
    raw = values.get(HOST_ENVIRONMENT_VARIABLE, "").strip()
    if not raw:
        return CODEX
    try:
        return HOST_PROFILES[raw]
    except KeyError:
        raise HostProfileError(
            f"unsupported {HOST_ENVIRONMENT_VARIABLE}: {raw!r}; "
            f"expected one of {', '.join(sorted(HOST_PROFILES))}"
        ) from None


def workspace_config_candidates(
    workspace_root: Path,
    filename: str,
    host: HostProfile | None = None,
) -> tuple[Path, ...]:
    profile = current_host() if host is None else host
    return tuple(Path(workspace_root) / name / filename for name in profile.workspace_config_dirs)


def workspace_profile_path(workspace_root: Path, host: HostProfile | None = None) -> Path:
    """回傳第一個存在的固定位置；全部不存在時回傳 Host 原生位置。

    以 lstat 判斷存在，連結也算存在，讓呼叫端既有的 link／reparse 檢查照常 fail closed。
    """

    candidates = workspace_config_candidates(workspace_root, WORKSPACE_PROFILE_FILENAME, host)
    for candidate in candidates:
        try:
            candidate.lstat()
        except OSError:
            continue
        return candidate
    return candidates[0]
