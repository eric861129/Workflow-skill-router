---
title: 前端除錯範例
description: 在 browser inspection、Chrome session、Playwright、framework expertise 與 API debugging 之間做取捨。
---

前端 bug 常常看起來很小，但實際上可能跨越 UI、資料、權限、browser state、build output 與 API boundary。

## 決策規則

- 需要視覺重現時，先用互動式 browser。
- 只有 cookies、登入狀態、extension 或目前分頁真的重要時，才用真實 Chrome session。
- 問題理解清楚且需要 regression coverage 時，再使用 Playwright。
- 資料 missing、stale、unauthorized 或 malformed 時，切到 API debugging。

## Sample route

```text
Route: Frontend / Reproduce > Local rendered app > Runtime behavior
Use SKILL: browser, frontend-debugging, systematic-debugging
Reason: browser captures rendered behavior; frontend-debugging maps symptoms to UI code; systematic-debugging keeps the investigation causal.
```

## Source

- [在 GitHub 開啟 `examples/frontend-debugging/`](https://github.com/eric861129/Workflow-skill-router/tree/main/examples/frontend-debugging)
- [開啟 `references/skill-tree.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/frontend-debugging/references/skill-tree.md)
- [開啟 `references/routing-rules.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/frontend-debugging/references/routing-rules.md)
