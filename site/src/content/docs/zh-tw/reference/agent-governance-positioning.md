---
title: Agent Governance 定位
description: Workflow Skill Router 在 Agent sprawl 與 Agent governance 中的位置。
---

Workflow Skill Router 處理的是 Agent sprawl 裡的 **Skill 選擇失控** 問題。

它不是權限邊界，也不取代 scope contract、runtime permission、approval policy 或 tool access controls。它的角色是在任務開始前，讓 Agent 先做一個小而可審查的 routing decision。

## 它處理什麼問題

當 Agent 環境越長越大，可用的 skills、tools、connectors 與 workflows 也會變多。這時一個寬泛任務很容易同時觸發太多看似相關的 instructions：

```text
frontend, ui, browser, playwright, qa, design-system, github, docs, deployment
```

Workflow Skill Router 會在執行前先收斂這份清單。它要求 Agent 選出：

- 一個 Primary skill。
- 只保留真正能降低風險或補足必要 context 的 Supporting skills。
- 排除看似相關、但本次不該載入的 skills。
- 用簡短理由說明這條 route。

## 它不處理什麼問題

Workflow Skill Router 不是安全邊界。

下列事情仍然應該交給既有治理層：

- scope contracts。
- runtime permissions。
- approval policies。
- tool access controls。
- sandboxing。
- secrets handling。
- 外部系統授權。

Router 的前提是某個 skill 已經存在，也已經被允許使用。它只判斷這個 skill 對當前任務是否必要。

## 為什麼這一層重要

Skill selection 夠小，可以在 Agent 修改檔案或呼叫工具前先被檢查。這讓它很適合作為早期 checkpoint：

```text
Route: Frontend / Debugging > Browser reproduction > Single-page app
Use SKILL: vue-expert, systematic-debugging, playwright
Reason: vue-expert 處理 component 行為；systematic-debugging 維持因果式排查；playwright 固化回歸驗證。
```

使用者可以在執行前修正這個決策。

## 建議的治理堆疊

Workflow Skill Router 最適合放在執行前：

```text
Task request
  -> Scope contract
  -> Skill selection route
  -> Runtime permissions
  -> Tool approvals
  -> Execution and verification
```

這讓專案定位保持清楚：它控制的是 instruction selection，不是 authorization。

