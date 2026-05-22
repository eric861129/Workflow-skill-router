# Routing Rules

## Priority

1. Respect explicit user requests. If the user names a SKILL or plugin, include it unless it is unavailable.
2. Prefer connector/plugin SKILLs when external systems are the core task.
3. Prefer local custom SKILLs for broad engineering judgment and repository work.
4. Prefer system SKILLs for OpenAI docs, image generation, plugin creation, skill creation, and skill installation.
5. Use broad Superpowers meta SKILLs only when the workflow is explicitly requested or clearly required.

## Skill Count

- Use one primary SKILL for narrow tasks.
- Use two to four SKILLs for cross-domain work.
- If more than four seem useful, choose the four that cover distinct phases: clarify, design, implement, verify.
- Do not include two skills that do the same job unless one is a connector and one is a local review/process skill.

## Conflict Handling

- `systematic-debugging` vs `superpowers:systematic-debugging`: use local `systematic-debugging` by default; use the Superpowers version when following the Superpowers workflow.
- `executing-plans` vs `superpowers:executing-plans`: use local `executing-plans` for normal plan execution; use the Superpowers version when the user asks for Superpowers or subagent-driven execution.
- `receiving-code-review` vs `github:gh-address-comments`: use GitHub skill to fetch/resolve PR comments; use receiving-code-review to reason about whether comments are valid.
- `frontend-design` vs `build-web-apps:frontend-app-builder`: use frontend-app-builder for full new frontend apps; use frontend-design for visual design quality and targeted UI.
- `playwright` vs `browser:browser`: use browser:browser for the Codex in-app browser and local visual verification; use playwright for scripted browser automation from terminal.
- `documents`, `spreadsheets`, `presentations`, `pdf`: choose by file type; do not replace them with generic documentation skills when file rendering matters.

## Output Examples

Backend API:

```text
路由：架構/API/後端 > API 合約設計 > C#/.NET
使用 SKILL：api-designer, csharp-developer, database-schema-designer, qa-test-planner
原因：api-designer 定義 API 合約；csharp-developer 對應 .NET 實作；database-schema-designer 處理資料模型；qa-test-planner 補驗收案例。
```

Frontend debug:

```text
路由：前端/Web/UI > Debug > Browser 驗證
使用 SKILL：build-web-apps:frontend-testing-debugging, browser:browser, systematic-debugging
原因：frontend-testing-debugging 對應渲染問題；browser:browser 做本機瀏覽器驗證；systematic-debugging 保持根因分析。
```

Simple command:

```text
不需要額外路由：這是單一步驟 shell 查詢，直接執行即可。
```

## Safety Defaults

- For filesystem operations, preserve the user's no bulk-delete rule.
- For repo work, inspect existing structure before deciding implementation.
- For frontend work, include browser or Playwright verification when UI behavior matters.
- For docs work, fit the repo's existing information architecture before writing new content.
- For connector work, use the connector skill and do not simulate unavailable live data.
