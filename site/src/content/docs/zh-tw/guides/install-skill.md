---
title: 安裝純 SKILL fallback
description: 只安裝 routing instructions，不啟用 Plugin 或 MCP。
---

## 何時使用純 SKILL

如果你只想讓 Codex 在工作前選擇合適的 SKILL，而目前環境不能載入 Plugin/MCP，使用獨立 SKILL。它仍會判斷任務規模、尊重使用者指定的 SKILL，並在工作前後揭露使用情況。

純 SKILL 不提供 durable resume、跨程序 compare-and-swap、完整 drift detection 或 sealed activation instrumentation。需要這些能力時，請改用 Plugin + MCP。

## 從 release asset 安裝

從 GitHub prerelease 下載 [`workflow-skill-router-skill-v2.0.0-beta.3.zip`](https://github.com/eric861129/Workflow-skill-router/releases/download/v2.0.0-beta.3/workflow-skill-router-skill-v2.0.0-beta.3.zip)，再把內層 `workflow-skill-router/` 解壓縮到 Codex Skills 目錄。

壓縮檔的完整路徑如下：

```text
workflow-skill-router/SKILL.md
workflow-skill-router/assets/personal-routing-profile.example.json
workflow-skill-router/assets/workspace-routing-profile.example.json
workflow-skill-router/references/evaluation-boundary.md
workflow-skill-router/references/goal-protocol.md
workflow-skill-router/references/personal-routing-profiles.md
workflow-skill-router/references/routing-protocol.md
```

解壓縮後，`.codex/skills/workflow-skill-router/SKILL.md` 必須直接存在於 Skill 目錄第一層。

## 從開發 checkout 安裝

Windows PowerShell：

```powershell
$Target = Join-Path $env:USERPROFILE ".codex\skills\workflow-skill-router"
Copy-Item -Recurse -Force "starter\v2\workflow-skill-router" $Target
Get-Content -Encoding UTF8 (Join-Path $Target "SKILL.md") | Select-Object -First 8
```

macOS 或 Linux：

```bash
mkdir -p "$HOME/.codex/skills"
cp -R starter/v2/workflow-skill-router "$HOME/.codex/skills/workflow-skill-router"
sed -n '1,8p' "$HOME/.codex/skills/workflow-skill-router/SKILL.md"
```

## 驗證行為

套件內含 `assets/personal-routing-profile.example.json`、`assets/workspace-routing-profile.example.json` 與 `references/personal-routing-profiles.md`。`.codex/workflow-skill-router.json` 請使用 workspace 範例，不要原樣複製 personal 範例。Skill-only 只有在 Host 授權 filesystem access 時才能讀取固定本機檔案；否則必須在對話中提供 Profile 內容，並把結果視為 advisory。

Skill-only 會以 `skill-only-fallback` 解讀 Skill Tree。它必須保留 workspace 高於 personal、使用者明確指定 SKILL 優先，以及 `intended-unverified` 的 Runtime Capability Discovery 邊界，但不能宣稱 deterministic loading 或 durable enforcement。`profile preview` CLI 屬於 Plugin/Core 模式。

開啟新的 Codex 任務，要求一個小型文件修改。Router 應宣告 `single` route 與預計使用的 SKILL。接著明確指定一個 SKILL，並要求額外的外部輔助角色；Router 必須先詢問，才能啟用該輔助技能。

此模式必須標示為 `skill-only-fallback`。單一 SKILL 檔案不能自行宣稱 Host 已暴露能力，也不能宣稱符合 `hybrid-full`。
