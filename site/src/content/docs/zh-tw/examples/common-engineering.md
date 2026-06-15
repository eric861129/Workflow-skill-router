---
title: 常見工程 Routes
description: 從真實軟體工程 workflow 整理出的完整 routing 範例。
---

這個範例展示成熟的 multi-skill agent 如何處理常見工程任務，而不是把所有相關 skill 一次全部載入。

## 適合情境

- 後端、API、OpenAPI、資料庫工作
- 前端、Vue、瀏覽器、Playwright、設計系統工作
- 文件、review、CI、DevOps、安全、資料分析與 connector workflow
- 想看具體 skill 名稱，而不是抽象 placeholder 的讀者

## Sample route catalog

以下 route 使用 public-safe skill 名稱，涵蓋日常工程工作中最常見的大類別。

```text
Route: Requirements / Clarify > Complex feature > Cross-team scope
Use SKILL: requirements-clarity, superpowers:brainstorming, superpowers:writing-plans
Reason: requirements-clarity turns ambiguity into decisions; brainstorming explores options; writing-plans shapes the implementation path.
```

```text
Route: Planning / Implementation plan > Multi-stage engineering > Backend and frontend
Use SKILL: executing-plans, superpowers:executing-plans, karpathy-guidelines
Reason: executing-plans drives staged delivery; superpowers execution supports disciplined workflow; karpathy-guidelines reduces common coding mistakes.
```

```text
Route: Finish / Handoff > Branch completion > Review-ready work
Use SKILL: session-handoff, finishing-a-development-branch, commit-work
Reason: session-handoff preserves context; finishing-a-development-branch checks completion; commit-work keeps the final commit reviewable.
```

```text
Route: Architecture / System design > High-level decisions > Service boundaries
Use SKILL: architecture-designer, c4-architecture, mermaid-diagrams, cloud-architect
Reason: architecture-designer frames tradeoffs; c4-architecture documents boundaries; mermaid-diagrams makes the design visible; cloud-architect checks deployment fit.
```

```text
Route: API / REST governance > Naming and compatibility > Public contract
Use SKILL: api-guidelines-skill, api-designer, openapi-contract-generation-skill
Reason: api-guidelines-skill guards REST consistency; api-designer shapes resources; openapi-contract-generation-skill keeps the contract testable.
```

```text
Route: API / OpenAPI lifecycle > Schema diff and client generation > Frontend sync
Use SKILL: openapi-contract-generation-skill, openapi-to-typescript, api-designer, build-web-apps:frontend-testing-debugging
Reason: openapi-contract-generation-skill manages schema lifecycle; openapi-to-typescript updates types; api-designer checks semantics; frontend-testing-debugging verifies runtime consumption.
```

```text
Route: Backend / C# or .NET > Feature implementation > Service and API layer
Use SKILL: csharp-developer, dotnet-core-expert, database-schema-designer, qa-test-planner
Reason: csharp-developer handles implementation; dotnet-core-expert covers framework patterns; database-schema-designer checks persistence shape; qa-test-planner defines coverage.
```

```text
Route: Database / Schema > Migration > Audit or reporting data
Use SKILL: database-schema-designer, sql-pro, build-web-apps:supabase-postgres-best-practices
Reason: database-schema-designer owns table shape; sql-pro reviews query correctness; supabase-postgres-best-practices adds Postgres operational guidance.
```

```text
Route: Database / Performance > Slow query > Production-like dataset
Use SKILL: database-optimizer, sql-pro, systematic-debugging
Reason: database-optimizer targets query plans; sql-pro improves SQL; systematic-debugging keeps the investigation evidence-driven.
```

```text
Route: Frontend / New page > Vue or general web > Customer workflow
Use SKILL: build-web-apps:frontend-app-builder, frontend-design, ui-ux-pro-max, vue-expert
Reason: frontend-app-builder scaffolds the page; frontend-design improves interaction quality; ui-ux-pro-max checks UX depth; vue-expert handles Vue details.
```

```text
Route: Frontend / Vue composition > Composables and shared state > Reusable logic
Use SKILL: vue-composition-patterns-skill, vue-expert, build-web-apps:frontend-testing-debugging
Reason: vue-composition-patterns-skill owns reactivity boundaries; vue-expert handles implementation; frontend-testing-debugging verifies behavior.
```

```text
Route: Frontend / Public-facing portal > Visual direction > Customer experience
Use SKILL: design-taste-frontend, high-end-visual-design, frontend-design, vue-expert
Reason: design-taste-frontend sets visual direction; high-end-visual-design raises polish; frontend-design keeps UI coherent; vue-expert supports Vue implementation.
```

```text
Route: Frontend / Internal admin > Dashboard, forms, tables > Operational workflow
Use SKILL: minimalist-ui, frontend-design, vue-expert, browser:control-in-app-browser
Reason: minimalist-ui fits dense operations screens; frontend-design keeps interactions polished; vue-expert handles Vue; browser verifies rendered workflow.
```

```text
Route: Design system / Storybook and Tailwind > Component states > Shared UI
Use SKILL: storybook-design-system-skill, tailwind-design-token-skill, frontend-design, design-system-starter
Reason: storybook-design-system-skill captures component states; tailwind-design-token-skill keeps styling consistent; frontend-design checks usability; design-system-starter frames the system.
```

```text
Route: Frontend / Debug > Browser reproduction and regression > Single-page app
Use SKILL: build-web-apps:frontend-testing-debugging, browser:control-in-app-browser, playwright, systematic-debugging
Reason: frontend-testing-debugging maps symptoms to code; browser reproduces rendered behavior; playwright captures regression; systematic-debugging keeps the fix causal.
```

```text
Route: Documentation / Technical guide > Diagrams and developer docs > Platform workflow
Use SKILL: doc-coauthoring, code-documenter, writing-clearly-and-concisely, mermaid-diagrams
Reason: doc-coauthoring structures the guide; code-documenter covers technical accuracy; writing-clearly-and-concisely improves readability; mermaid-diagrams explains flow.
```

```text
Route: GitHub / Review and CI > Security-sensitive PR > Auth and data exposure
Use SKILL: codex-security:security-diff-scan, receiving-code-review, systematic-debugging, github:github
Reason: security-diff-scan checks sensitive diffs; receiving-code-review evaluates feedback; systematic-debugging verifies causes; github fetches PR state.
```

```text
Route: DevOps / Local development > Docker Compose and dependency updates > Repeatable stack
Use SKILL: docker-compose-local-dev-skill, devops-engineer, dependency-updater, systematic-debugging
Reason: docker-compose-local-dev-skill owns local services; devops-engineer checks infrastructure tradeoffs; dependency-updater handles package risk; systematic-debugging helps failures.
```

## Source

- [在 GitHub 開啟 `examples/common-engineering-routing/`](https://github.com/eric861129/Workflow-skill-router/tree/main/examples/common-engineering-routing)
- [查看 `references/sample-routes.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/common-engineering-routing/references/sample-routes.md)
- [查看 `references/skill-tree.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/common-engineering-routing/references/skill-tree.md)
- [查看 `references/routing-rules.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/common-engineering-routing/references/routing-rules.md)

可複製的 skill implementation 請看：

- [在 GitHub 開啟 `sample-skills/`](https://github.com/eric861129/Workflow-skill-router/tree/main/sample-skills)
