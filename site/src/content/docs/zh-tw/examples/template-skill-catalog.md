---
title: Template Skill Catalog
description: 對齊範本下載包的單一公開範例，展示 public-safe skills 如何被 router 分類使用。
---

這個範例是理解範本下載包最快的入口。它展示下載後會拿到哪些 public-safe skills，以及在真實工程工作中可以怎麼路由。

- [下載範本 SKILL 套件](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template.zip)
- [查看範例 source folder](https://github.com/eric861129/Workflow-skill-router/tree/main/examples/template-skill-catalog)
- [查看 sample routes](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/template-skill-catalog/references/sample-routes.md)

## 完整案例

這些案例示範一個使用者需求，如何被 router 轉成清楚的 Route、Primary SKILL 與 Supporting SKILL。

### API 合約同步

使用者需求：

```text
新增 customer settings endpoint，更新 OpenAPI，重新產生 TypeScript client，並補上合約測試。
```

Route: API / 合約生命週期 > 後端到前端同步
Use SKILL: `api-designer`, `openapi-contract-generation-skill`, `openapi-to-typescript`, `qa-test-planner`
Reason: `api-designer` 先穩定 endpoint 語意；`openapi-contract-generation-skill` 處理 schema diff 與產生流程；`openapi-to-typescript` 更新前端型別；`qa-test-planner` 補齊合約測試覆蓋。

### 資料庫 Migration 與效能風險

使用者需求：

```text
替帳號異動新增 audit tables，並確認 admin activity query 在 migration 後仍然夠快。
```

Route: 資料庫 / Schema 與效能 > Migration 加查詢檢查
Use SKILL: `database-schema-designer`, `sql-pro`, `database-optimizer`, `qa-test-planner`
Reason: `database-schema-designer` 設計 audit tables；`sql-pro` 保持 SQL 清楚可維護；`database-optimizer` 檢查 runtime cost；`qa-test-planner` 規劃 migration 與回歸測試。

### 只在瀏覽器出現的 Vue Regression

使用者需求：

```text
Vue 表單重新整理後會遺失已選值，請在瀏覽器重現並補一個 regression check。
```

Route: 前端 / Vue / UI > 瀏覽器回歸 > 狀態保存
Use SKILL: `vue-expert`, `systematic-debugging`, `playwright`, `qa-test-planner`
Reason: `vue-expert` 處理 component 與 reactivity；`systematic-debugging` 找出真正原因；`playwright` 建立可重複的瀏覽器檢查；`qa-test-planner` 定義驗收覆蓋。

### PR Review 與 CI 修復

使用者需求：

```text
Review 一個 auth 相關 PR，處理 review feedback，並在 merge 前修好失敗的 CI checks。
```

Route: Review / CI readiness > 權限敏感變更
Use SKILL: `receiving-code-review`, `systematic-debugging`, `qa-test-planner`, `commit-work`
Reason: `receiving-code-review` 把 feedback 轉成可執行修改；`systematic-debugging` 隔離 CI 失敗原因；`qa-test-planner` 保護 auth 表面；`commit-work` 準備乾淨的最後 commit。

### 架構討論整理成 Handoff

使用者需求：

```text
把一段系統設計討論整理成 C4 diagram、實作計畫與 handoff notes。
```

Route: 架構 / 文件化 > 決策紀錄與交接
Use SKILL: `architecture-designer`, `c4-architecture`, `code-documenter`, `session-handoff`
Reason: `architecture-designer` 先整理架構決策；`c4-architecture` 產出可讀圖表；`code-documenter` 轉成開發者文件；`session-handoff` 保留下一步脈絡。

### Dependency Upgrade 與 Release 風險

使用者需求：

```text
升級前端 build dependencies，找出 regression risk，並準備讓這個 branch 可以 release。
```

Route: DevOps / Dependency / Release > 安全升級路徑
Use SKILL: `dependency-updater`, `systematic-debugging`, `qa-test-planner`, `finishing-a-development-branch`
Reason: `dependency-updater` 規劃升級；`systematic-debugging` 處理升級後破掉的地方；`qa-test-planner` 盤點回歸風險；`finishing-a-development-branch` 確認 release readiness。

## 需求 / 規劃 / 任務拆解

- 需求 / 釐清 / 複雜功能: Primary: `requirements-clarity`; Supporting: `writing-clearly-and-concisely`, `spec-miner`
- 規劃 / 實作計畫 / 多階段工程: Primary: `executing-plans`; Supporting: `karpathy-guidelines`, `qa-test-planner`
- 收尾 / 分支完成 / 交接紀錄: Primary: `session-handoff`; Supporting: `finishing-a-development-branch`, `commit-work`

## 架構 / API / 後端

- 架構 / 系統設計 / 高階決策: Primary: `architecture-designer`; Supporting: `c4-architecture`, `cloud-architect`
- API / REST Governance / 命名、分頁、版本、錯誤語意: Primary: `api-guidelines-skill`; Supporting: `api-designer`, `openapi-contract-generation-skill`
- API / OpenAPI 同步 / Schema diff 與 client generation: Primary: `openapi-contract-generation-skill`; Supporting: `openapi-to-typescript`, `api-designer`
- 後端 / C# 或 .NET / Service 實作: Primary: `csharp-developer`; Supporting: `dotnet-core-expert`, `database-schema-designer`, `qa-test-planner`

## 資料庫 / SQL

- 資料庫 / Schema / Migration: Primary: `database-schema-designer`; Supporting: `sql-pro`, `database-optimizer`
- 資料庫 / 效能 / 慢查詢: Primary: `database-optimizer`; Supporting: `sql-pro`, `systematic-debugging`
- 資料合約 / API 與 DB 邊界: Primary: `api-designer`; Supporting: `openapi-to-typescript`, `database-schema-designer`

## 前端 / Vue / UI

- 前端 / Vue Component / 新功能頁面: Primary: `vue-expert`; Supporting: `vue-composition-patterns-skill`, `frontend-design`
- 前端 / 共用狀態 / Composition API 重構: Primary: `vue-composition-patterns-skill`; Supporting: `vue-expert`, `systematic-debugging`
- 前端 / 產品 UI / 對外頁面: Primary: `frontend-design`; Supporting: `ui-ux-pro-max`, `ui-styling`
- 前端 / Screenshot to implementation / 視覺還原: Primary: `image-to-code-skill`; Supporting: `frontend-design`, `tailwind-design-token-skill`

## 設計系統 / 視覺品質

- 設計系統 / Tokens 與 primitives / Starter setup: Primary: `design-system-starter`; Supporting: `design-system`, `tailwind-design-token-skill`, `storybook-design-system-skill`
- Storybook / Component states / 視覺 review: Primary: `storybook-design-system-skill`; Supporting: `frontend-design`, `qa-test-planner`
- UI Redesign / Premium polish / 既有專案升級: Primary: `redesign-skill`; Supporting: `gpt-tasteskill`, `ui-ux-pro-max`
- 極簡介面 / 文件可讀性 / 安靜的 docs UI: Primary: `minimalist-skill`; Supporting: `ui-styling`, `frontend-design`

## 除錯 / 測試 / Browser

- 除錯 / 未知失敗 / 原因追查: Primary: `systematic-debugging`; Supporting: `playwright`, `qa-test-planner`
- Browser QA / Regression / 可重複互動驗證: Primary: `playwright`; Supporting: `qa-test-planner`, `systematic-debugging`
- 測試規劃 / 驗收覆蓋 / Release confidence: Primary: `qa-test-planner`; Supporting: `receiving-code-review`, `systematic-debugging`

## 文件 / 圖表 / 規格

- 文件 / 技術指南 / Developer-facing docs: Primary: `code-documenter`; Supporting: `mermaid-diagrams`, `c4-architecture`
- 規格 / 既有系統探索 / 行為抽取: Primary: `spec-miner`; Supporting: `code-documenter`, `architecture-designer`
- 協作寫作 / 使用者指南 / 共同撰寫: Primary: `doc-coauthoring`; Supporting: `writing-clearly-and-concisely`, `code-documenter`
- PDF / 文件 review / 檔案交付: Primary: `pdf`; Supporting: `code-documenter`, `file-organizer`
- Agent docs / 大型 instruction 文件 / 重構與整理: Primary: `agent-md-refactor`; Supporting: `writing-clearly-and-concisely`, `code-documenter`

## DevOps / Dependency / Release

- 本機開發 / Docker Compose / Service stack: Primary: `docker-compose-local-dev-skill`; Supporting: `devops-engineer`, `dependency-updater`
- 依賴升級 / Upgrade / 風險與回歸: Primary: `dependency-updater`; Supporting: `systematic-debugging`, `qa-test-planner`
- DevOps / 部署規劃 / Cloud readiness: Primary: `devops-engineer`; Supporting: `cloud-architect`, `docker-compose-local-dev-skill`
- Release / 最終驗證 / Commit readiness: Primary: `finishing-a-development-branch`; Supporting: `commit-work`, `qa-test-planner`

## Brand / Product / Cross-platform

- 品牌 / 語氣與訊息 / 產品敘事: Primary: `brand`; Supporting: `design`, `banner-design`
- 跨平台 / Flutter App / Mobile implementation: Primary: `flutter-expert`; Supporting: `frontend-design`, `qa-test-planner`
- 產品視覺 / Web hero assets / 生成式概念: Primary: `imagegen-frontend-web`; Supporting: `frontend-design`, `brand`
- Mobile 視覺 / App concept / 生成式畫面方向: Primary: `imagegen-frontend-mobile`; Supporting: `flutter-expert`, `ui-ux-pro-max`
- 視覺方向 / Taste 與 polish / 產品介面: Primary: `design`; Supporting: `soft-skill`, `taste-skill`

## Source

- [查看 GitHub `examples/template-skill-catalog/`](https://github.com/eric861129/Workflow-skill-router/tree/main/examples/template-skill-catalog)
- [查看 `references/skill-tree.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/template-skill-catalog/references/skill-tree.md)
- [查看 `references/routing-rules.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/template-skill-catalog/references/routing-rules.md)
- [查看 `references/sample-routes.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/template-skill-catalog/references/sample-routes.md)
