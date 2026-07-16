---
title: 安裝純 SKILL fallback
description: 在沒有 Plugin 或 MCP 時，載入 V2 routing contract。
---

## 何時使用純 SKILL

Host 無法載入 Plugin/MCP，或只需要指令式 routing 時，使用獨立 SKILL。它保留 envelope 選擇、Explicit Skill Lock、輔助技能同意與使用揭露；不提供 durable resume、跨程序 compare-and-swap、完整 drift detection 或 sealed activation instrumentation。

## 從 checkout 安裝

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

## 從 release asset 安裝

Beta 發布後，從 GitHub Release 下載 `workflow-skill-router-skill-v2.0.0-beta.1.zip`，把內層 `workflow-skill-router/` 解壓縮到 Codex Skills 目錄。

預期結構：

```text
.codex/skills/workflow-skill-router/
  SKILL.md
  references/
  agents/
```

## 驗證行為

開啟新的 Codex 任務，要求一個小型文件修改。Router 應宣告 `single` route 與預計使用的 SKILL。接著明確指定一個 SKILL，並要求額外的外部輔助角色；Router 必須先詢問，才能啟用該輔助技能。

此模式必須標示為 `skill-only-fallback`。單一 SKILL 檔案不能自行宣稱 Host 已暴露能力，也不能宣稱符合 `hybrid-full`。
