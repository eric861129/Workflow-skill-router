---
title: 快速開始
description: 安裝 starter router、填入 skill tree，並用 validator 驗證。
---

## 1. 複製 starter

把這個資料夾複製到你的 Agent skill 目錄：

```text
starter/workflow-skill-router/
```

或直接下載可安裝的 zip：

- [空白 SKILL 套件](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-blank.zip)

如果你在 Windows 使用 Codex：

```text
C:\Users\<you>\.codex\skills\workflow-skill-router
```

## 2. 請 Agent 補齊 router

使用 repo 內的 prompt：

```text
prompts/agent-prompt.zh-TW.md
```

Agent 應該先盤點可用 skills，再補齊：

```text
workflow-skill-router/
  SKILL.md
  references/
    skill-tree.md
    routing-rules.md
```

## 3. 執行驗證

執行：

```bash
python scripts/validate-router.py starter/workflow-skill-router
```

預期輸出：

```text
OK: workflow-skill-router passed validation
```

如果你想看更完整的參考，可以下載 [範本 SKILL 套件](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template.zip)。裡面包含 common engineering router 和 sample `SKILL.md` folders。

## 4. 試跑一條 route

丟一個複雜任務給 Agent：

```text
Debug a browser-only bug in the customer portal and add a regression check.
```

預期格式：

```text
Route: Frontend / Debugging > Browser reproduction > Customer portal
Use SKILL: frontend-debugging, browser, playwright
Reason: frontend-debugging maps UI symptoms to source; browser reproduces rendered behavior; playwright captures the regression.
```
