# Frontend Debugging Sample Routes

Use these examples to choose between browser inspection, Chrome session work, Playwright automation, framework expertise, UI debugging, and API boundary investigation.

## Route Catalog

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
