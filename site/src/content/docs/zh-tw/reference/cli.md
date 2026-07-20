---
title: CLI Reference
description: 檢查 runtime readiness、啟動 JSONL bridge，並準備已授權的 evaluation run。
---

## Entrypoint

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz --help
```

Commands 包括 `serve-jsonl`、`doctor`、`status`、`plan`、`validate-route`、`profile` 與 `evaluation`。MCP server 使用 `serve-jsonl`；直接操作時應先執行 `doctor`。

## Personal Routing Profile commands

Personal 與 workspace Skill Tree 永遠低於使用者當次明確指定 SKILL 與 Host constraints。Profile 命中只是 `intended-unverified`，仍要由 Runtime Capability Discovery 驗證 activation。

這組 command 隨 `v2.0.0-beta.2` 提供。解壓縮的 Plugin root 使用 `python runtime/workflow_skill_router.pyz profile ...`；contributor checkout 則使用較長的 repository-relative 路徑。

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile validate .\my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile install .\my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile list
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile preview --objective "交付 API" --work-mode phased --domain api
```

未來安裝包含 Personal Routing Profiles 的 prerelease 後，可在解壓縮的 Plugin 目錄對 `runtime/workflow_skill_router.pyz` 執行相同 subcommands。只有另外安裝 Router Core 的 Python console script 時，才會有簡寫 `workflow-skill-router ...`。

`profile install` 只接受 `scope: personal`，並寫入 Plugin cache 外部。Workspace Profile 固定放在 `.codex/workflow-skill-router.json`；`profile preview` 可用 `--workspace-root` 一起解析。Skill-only 能依相同 contract 做 advisory `skill-only-fallback`，但不能宣稱 deterministic loading。

## Runtime readiness

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz doctor
```

JSON output 會列出 active runtime profile、telemetry 狀態、content preflight 可見度，以及每個 public tool 的 readiness。

## Plan 與 status

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz plan --help
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz status --help
```

這些 commands 使用外部 local state database。在 verified integration 提供對應 ports 前，受保護的 Host 行為仍不可用。

## Evaluation

Dry-run manifest 不會消耗 quota。Behavior/Outcome subprocess run 需要 trusted operator configuration 提供絕對 executable path，並明確加上 `--confirm-live-run`：

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz evaluation run --help
```

不要把 model output 提供的 executable path 直接放入已授權的執行。先閱讀 [evaluation evidence contract](/Workflow-skill-router/zh-tw/concepts/evaluation-evidence/)。
