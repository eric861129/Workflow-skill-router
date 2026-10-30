"""從 canonical 來源同步 Claude Code Plugin 的衍生檔案；--check 只比對、不寫入。

Claude Code 安裝時只複製 Plugin 目錄本身，因此 MCP bundle、Python runtime 與
Skill 參考資料必須逐位元組放進 Plugin 目錄。Host 專屬檔案由人工維護，不在此產生。
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
CODEX_PLUGIN = ROOT / "plugins" / "workflow-skill-router"
STARTER = ROOT / "starter" / "v2" / "workflow-skill-router"
TARGET = ROOT / "plugins" / "claude-code" / "workflow-skill-router"

HOST_FILES = (
    ".claude-plugin/plugin.json",
    ".mcp.json",
    "README.md",
    "assets/icon.png",
    "skills/workflow-skill-router/SKILL.md",
)
SKILL_SUPPORT_FILES = (
    "assets/memory-policy.automatic.example.yaml",
    "assets/memory-policy.disabled.example.yaml",
    "assets/memory-policy.reviewed.example.yaml",
    "assets/personal-routing-profile.example.json",
    "assets/workspace-routing-profile.example.json",
    "references/evaluation-boundary.md",
    "references/goal-protocol.md",
    "references/personal-routing-profiles.md",
    "references/routing-protocol.md",
)
COPIED_FILES = (
    ("LICENSE", CODEX_PLUGIN / "LICENSE"),
    ("THIRD_PARTY_NOTICES.md", CODEX_PLUGIN / "THIRD_PARTY_NOTICES.md"),
    ("mcp/server.bundle.mjs", CODEX_PLUGIN / "mcp" / "server.bundle.mjs"),
    ("runtime/workflow_skill_router.pyz", CODEX_PLUGIN / "runtime" / "workflow_skill_router.pyz"),
    *(
        (f"skills/workflow-skill-router/{name}", STARTER / name)
        for name in SKILL_SUPPORT_FILES
    ),
)


def _relative_files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    }


def problems() -> list[str]:
    found: list[str] = []
    starter_files = _relative_files(STARTER)
    expected_starter = {"SKILL.md", *SKILL_SUPPORT_FILES}
    if starter_files != expected_starter:
        # Canonical Skill 新增或移除檔案時，必須先決定 Claude Code Plugin 是否要帶上它。
        found.append(f"canonical skill files changed: {sorted(starter_files ^ expected_starter)}")
    if not TARGET.is_dir():
        return [*found, f"missing plugin directory: {TARGET.relative_to(ROOT).as_posix()}"]
    expected = {*HOST_FILES, *(target for target, _ in COPIED_FILES)}
    actual = _relative_files(TARGET)
    for name in sorted(actual - expected):
        found.append(f"unexpected file: {name}")
    for name in HOST_FILES:
        if name not in actual:
            found.append(f"missing host file: {name}")
    for name, source in COPIED_FILES:
        destination = TARGET / name
        if destination.is_symlink():
            found.append(f"link forbidden: {name}")
        elif not destination.is_file():
            found.append(f"missing copied file: {name}")
        elif destination.read_bytes() != source.read_bytes():
            found.append(f"stale copied file: {name}")
    return found


def sync() -> None:
    for name, source in COPIED_FILES:
        destination = TARGET / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail when the plugin is out of sync")
    args = parser.parse_args()
    if not args.check:
        sync()
    found = problems()
    for problem in found:
        print(problem)
    if found:
        hint = "run: python scripts/sync-claude-plugin.py" if args.check else "fix the files listed above"
        print(hint)
        return 1
    print("Claude Code plugin is in sync.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
