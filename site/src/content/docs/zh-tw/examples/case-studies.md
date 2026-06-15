---
title: Routing Case Studies
description: 六個把模糊需求轉成小而可檢查 route 的例子。
---

這些 case studies 展示 Workflow Skill Router 的核心：不要載入所有相關 skill，而是選一個 primary skill，再補上真正必要的 supporting skills。

## API 合約同步

模糊需求：

```text
新增 customer settings endpoint，更新 OpenAPI，重新產生前端 client，並確認合約有被測試。
```

錯誤 over-route：

```text
Use SKILL: backend-developer, api-designer, openapi-contract-generation-skill, openapi-to-typescript, database-optimizer, qa-test-planner, frontend-design
```

較好的 route：

```text
Route: API / Contract lifecycle > Backend-to-frontend sync
Use SKILL: api-designer, openapi-contract-generation-skill, openapi-to-typescript, qa-test-planner
Reason: api-designer 負責 endpoint 語意；openapi-contract-generation-skill 管理 schema change；openapi-to-typescript 更新 client types；qa-test-planner 定義合約覆蓋。
```

為什麼較小更好：這組 route 保留 API shape 的單一 owner，只加入傳遞與驗證合約真正需要的工具。

## Vue 瀏覽器回歸

模糊需求：

```text
Vue 表單在 refresh 後會遺失已選值。請用瀏覽器重現，並補上 regression check。
```

錯誤 over-route：

```text
Use SKILL: vue-expert, frontend-design, browser, playwright, qa-test-planner, api-designer, database-optimizer
```

較好的 route：

```text
Route: Frontend / Vue / UI > Browser regression > State persistence
Use SKILL: vue-expert, systematic-debugging, playwright, qa-test-planner
Reason: vue-expert 處理 component state；systematic-debugging 找出真正原因；playwright 固化瀏覽器回歸；qa-test-planner 定義驗收覆蓋。
```

為什麼較小更好：route 從症狀出現的位置開始，加入因果式除錯，最後才用可重複的瀏覽器檢查驗證。

## PR Review 與 CI 修復

模糊需求：

```text
Review 這個 auth 相關 PR，處理 review feedback，並在 merge 前修好失敗的 CI checks。
```

錯誤 over-route：

```text
Use SKILL: github, receiving-code-review, security-review, systematic-debugging, qa-test-planner, devops-engineer, commit-work, documentation-writer
```

較好的 route：

```text
Route: Review / CI readiness > Security-sensitive change
Use SKILL: receiving-code-review, systematic-debugging, qa-test-planner, commit-work
Reason: receiving-code-review 把 feedback 轉成行動；systematic-debugging 隔離 CI 失敗；qa-test-planner 保護 auth 表面；commit-work 準備乾淨 commit。
```

為什麼較小更好：route 專注在 merge 前必須完成的工作。只有當 live GitHub comments 或 logs 是 source of truth 時，才需要加 connector skills。

## 文件 source map 清理

模糊需求：

```text
搬移 guide 頁面後，docs source map 已經過期。修正公開連結，並確認每個頁面仍指到正確 source file。
```

錯誤 over-route：

```text
Use SKILL: code-documenter, spec-miner, frontend-design, devops-engineer, qa-test-planner, github
```

正確 route：

```text
Route: Documentation / Source map > Link and provenance cleanup
Use SKILL: code-documenter, spec-miner
Reason: code-documenter 負責開發者文件文字；spec-miner 確認文件來源與 provenance。
```

為什麼較小更好：route 保持在內容與來源追蹤。只有 validation 失敗或需要 live repo state 時，才加 site build 或 GitHub connector skill。

## Database migration 與效能風險

模糊需求：

```text
新增 account changes 的 audit tables，並確認 migration 後 admin activity query 仍然夠快。
```

錯誤 over-route：

```text
Use SKILL: database-schema-designer, sql-pro, database-optimizer, devops-engineer, api-designer, qa-test-planner, frontend-design
```

正確 route：

```text
Route: Database / Schema and performance > Migration plus query review
Use SKILL: database-schema-designer, sql-pro, database-optimizer, qa-test-planner
Reason: database-schema-designer 負責 table shape；sql-pro 保持 SQL 清楚；database-optimizer 檢查 query cost；qa-test-planner 定義 migration coverage。
```

為什麼較小更好：選到的 skills 已覆蓋 schema、SQL、performance 與 verification，不需要讓 API 或 UI 工作干擾 agent。

## Release 與 connector closeout

模糊需求：

```text
完成 release branch，檢查最新 GitHub run，並準備 release note。
```

錯誤 over-route：

```text
Use SKILL: finishing-a-development-branch, github, receiving-code-review, systematic-debugging, devops-engineer, code-documenter, commit-work
```

正確 route：

```text
Route: Release / Closeout > GitHub-backed readiness check
Use SKILL: finishing-a-development-branch, github, code-documenter
Reason: finishing-a-development-branch 負責本機收尾；github 檢查 live run state；code-documenter 準備 release note。
```

為什麼較小更好：connector 被加入是因為 live GitHub state 是 source of truth。除非 run 失敗，否則 debugging 與 DevOps skills 先保持不啟用。
