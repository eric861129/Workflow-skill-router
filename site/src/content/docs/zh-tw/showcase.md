---
title: Routing Showcase
description: 五個適合轉貼分享的 Workflow Skill Router before/after 案例。
---

V2 首頁提供六個由 core 產生的 Single、Phased、Managed Goal、Explicit Skill Lock、consent 與真實評測情境。**Tier 0 Contract** 不會冒充 Behavior evidence；沒有 adapter 是 `manual-required`，沒有可信任審查是 `review-required`。前端不會把 `skill-only-fallback` 升格成 `hybrid-full`。

這些範例適合放在貼文、issue 或 README 片段中，快速說明為什麼 route 要小而可檢查。

## 視覺預覽

這段影片只是讓頁面不那麼單調的視覺輔助，不是互動 Demo，也不是實際操作教學。真正的 route before/after 範例在下方。

<video controls muted playsinline preload="metadata" poster="/Workflow-skill-router/assets/workflow-skill-router-demo-poster.png" width="1280" height="720">
  <source src="/Workflow-skill-router/assets/workflow-skill-router-demo.mp4" type="video/mp4" />
  <source src="/Workflow-skill-router/assets/workflow-skill-router-demo.webm" type="video/webm" />
  <a href="/Workflow-skill-router/assets/workflow-skill-router-demo.mp4">開啟視覺預覽影片</a>
</video>

## API 合約同步

Before：

```text
Over-route: backend-developer, api-designer, openapi-contract-generation-skill, openapi-to-typescript, database-optimizer, frontend-design, qa-test-planner
```

After：

```text
Route: API / Contract lifecycle > Backend-to-frontend sync
Use SKILL: api-designer, openapi-contract-generation-skill, openapi-to-typescript, qa-test-planner
```

## Vue 瀏覽器 regression

Before：

```text
Over-route: vue-expert, frontend-design, browser, playwright, qa-test-planner, api-designer, database-optimizer
```

After：

```text
Route: Frontend / Vue / UI > Browser regression > State persistence
Use SKILL: vue-expert, systematic-debugging, playwright, qa-test-planner
```

## 文件 source-map 清理

Before：

```text
Over-route: code-documenter, spec-miner, frontend-design, devops-engineer, qa-test-planner, github
```

After：

```text
Route: Documentation / Source map > Link and provenance cleanup
Use SKILL: code-documenter, spec-miner
```

## Database migration 與效能風險

Before：

```text
Over-route: database-schema-designer, sql-pro, database-optimizer, devops-engineer, api-designer, qa-test-planner, frontend-design
```

After：

```text
Route: Database / Schema and performance > Migration plus query review
Use SKILL: database-schema-designer, sql-pro, database-optimizer, qa-test-planner
```

## Release 與 connector closeout

Before：

```text
Over-route: finishing-a-development-branch, github, receiving-code-review, systematic-debugging, devops-engineer, code-documenter, commit-work
```

After：

```text
Route: Release / Closeout > GitHub-backed readiness check
Use SKILL: finishing-a-development-branch, github, code-documenter
```
