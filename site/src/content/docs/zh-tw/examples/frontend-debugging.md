---
title: 前端除錯範例
description: 在 browser inspection、Chrome session、Playwright、framework expertise 與 API debugging 之間選擇正確分工。
---

前端 bug 常從看得到的 UI 問題開始，接著跨到 browser state、framework state、API data、build output、權限與 regression coverage。

## 判斷規則

- 需要視覺重現時，優先使用互動式 browser。
- 只有 cookies、登入狀態、extension 或既有分頁會影響結果時，才使用真實 Chrome session。
- 問題已經理解、需要可重複的 regression coverage 時，使用 Playwright。
- 資料 missing、stale、unauthorized 或 malformed 時，加入 API debugging。

## Sample routes

```text
Route: Frontend / Reproduce > Local rendered app > Runtime behavior
Use SKILL: browser, frontend-debugging, systematic-debugging
Reason: browser captures real rendered behavior; frontend-debugging maps symptoms to UI code; systematic-debugging keeps the investigation causal.
```

```text
Route: Frontend / Reproduce > Logged-in Chrome session > Session-specific behavior
Use SKILL: chrome-session, browser, frontend-debugging, systematic-debugging
Reason: chrome-session preserves user state; browser compares local behavior; frontend-debugging maps the symptom; systematic-debugging avoids guesswork.
```

```text
Route: Frontend / Reproduce > Automated regression > Repeatable failure
Use SKILL: playwright, frontend-debugging, test-planning
Reason: playwright makes the bug repeatable; frontend-debugging identifies the UI path; test-planning defines durable coverage.
```

```text
Route: Frontend / Diagnose > Component state or reactivity > Stale UI
Use SKILL: framework-expert, frontend-debugging, systematic-debugging
Reason: framework-expert handles state and lifecycle; frontend-debugging connects UI symptoms to code; systematic-debugging proves the cause.
```

```text
Route: Frontend / Diagnose > API or data mismatch > Missing or stale records
Use SKILL: api-debugging, frontend-debugging, browser, systematic-debugging
Reason: api-debugging checks the data boundary; frontend-debugging verifies consumption; browser shows runtime state; systematic-debugging keeps evidence ordered.
```

```text
Route: Frontend / Diagnose > Styling or layout > Responsive breakage
Use SKILL: ui-debugging, browser, accessibility-review
Reason: ui-debugging focuses CSS and layout; browser verifies viewport behavior; accessibility-review checks usable states.
```

```text
Route: Frontend / Fix > UI behavior > Interaction bug
Use SKILL: frontend-builder, framework-expert, browser, test-planning
Reason: frontend-builder implements the fix; framework-expert handles component behavior; browser verifies interaction; test-planning captures regression coverage.
```

```text
Route: Frontend / Verify > Visual and interaction QA > Release check
Use SKILL: browser, playwright, frontend-debugging
Reason: browser checks real interaction; playwright covers repeatable paths; frontend-debugging helps interpret failures.
```

```text
Route: Frontend / Diagnose > Build output or env proxy mismatch > Local vs deployed behavior
Use SKILL: frontend-debugging, framework-expert, api-debugging, systematic-debugging
Reason: frontend-debugging compares environments; framework-expert checks build assumptions; api-debugging validates proxy and data calls; systematic-debugging isolates the layer.
```

```text
Route: Frontend / Diagnose > Authorization-visible UI issue > Hidden or disabled controls
Use SKILL: api-debugging, browser, frontend-debugging, systematic-debugging
Reason: api-debugging checks access-shaped data; browser shows actual UI state; frontend-debugging maps conditions; systematic-debugging proves the branch.
```

```text
Route: Frontend / Diagnose > Responsive or mobile viewport bug > Touch and layout
Use SKILL: ui-debugging, browser, playwright, accessibility-review
Reason: ui-debugging handles responsive CSS; browser inspects layout; playwright can preserve viewport regression; accessibility-review checks touch-friendly behavior.
```

```text
Route: Frontend / Handoff > Regression after fix > Reviewer-ready evidence
Use SKILL: test-planning, playwright, frontend-debugging
Reason: test-planning defines the acceptance case; playwright records repeatable proof; frontend-debugging explains the before-and-after behavior.
```

## Source

- [在 GitHub 查看 `examples/frontend-debugging/`](https://github.com/eric861129/Workflow-skill-router/tree/main/examples/frontend-debugging)
- [開啟 `references/sample-routes.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/frontend-debugging/references/sample-routes.md)
- [開啟 `references/skill-tree.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/frontend-debugging/references/skill-tree.md)
- [開啟 `references/routing-rules.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/frontend-debugging/references/routing-rules.md)
