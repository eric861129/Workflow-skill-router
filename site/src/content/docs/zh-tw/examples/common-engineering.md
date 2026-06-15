---
title: 常見工程 Routes
description: 從真實軟體工程 workflow 萃取出的較完整 routing 範例。
---

這個範例展示成熟的 multi-skill agent 如何處理常見工程任務，而不是一次載入所有看起來相關的 skills。

## 適合對象

- backend、API、OpenAPI、database work
- frontend、Vue、browser、Playwright、design-system work
- docs、review、CI、DevOps、security、analytics、connectors
- 想看具體 skill 名稱，而不是抽象 placeholder 的讀者

## Sample route

```text
Route: API / OpenAPI lifecycle > Schema diff and client generation > Frontend sync
Use SKILL: openapi-contract-generation-skill, openapi-to-typescript, api-designer, build-web-apps:frontend-testing-debugging
Reason: openapi-contract-generation-skill manages schema lifecycle; openapi-to-typescript updates types; api-designer checks contract semantics; frontend-testing-debugging verifies runtime behavior.
```

## Source

- [在 GitHub 開啟 `examples/common-engineering-routing/`](https://github.com/eric861129/Workflow-skill-router/tree/main/examples/common-engineering-routing)
- [開啟 `references/skill-tree.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/common-engineering-routing/references/skill-tree.md)
- [開啟 `references/routing-rules.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/common-engineering-routing/references/routing-rules.md)

可複製參考的 skill implementations：

- [在 GitHub 開啟 `sample-skills/`](https://github.com/eric861129/Workflow-skill-router/tree/main/sample-skills)
