---
title: Blank Router 端到端教學
description: 安裝空白 router、用 fictional skill inventory 填入內容、驗證，並實際跑一次 route。
---

這份教學示範從下載 Blank Router 到完成一套可驗證 router 的完整流程。範例 skill 名稱都是 fictional，方便你複製結構，同時避免洩漏私人工作流程。

## 你會完成什麼

完成後，安裝好的 skill folder 會長這樣：

```text
workflow-skill-router/
  SKILL.md
  agents/
    openai.yaml
  references/
    skill-tree.md
    routing-rules.md
```

這個 router 會在 Agent 開始工作前，先把複雜任務分類成一個 primary skill 與最多三個 supporting skills。

## 1. 下載與安裝

先把 Blank Router 安裝到 Codex skills 目錄。

Windows PowerShell：

```powershell
$Repo = "https://github.com/eric861129/Workflow-skill-router"
$Zip = Join-Path $env:TEMP "workflow-skill-router-blank.zip"
$Validator = Join-Path $env:TEMP "workflow-skill-router-validate-router.py"
$Skills = Join-Path $env:USERPROFILE ".codex\skills"
Invoke-WebRequest "$Repo/raw/main/downloads/workflow-skill-router-blank.zip" -OutFile $Zip
Invoke-WebRequest "$Repo/raw/main/scripts/validate-router.py" -OutFile $Validator
New-Item -ItemType Directory -Force -Path $Skills | Out-Null
Expand-Archive -Force -Path $Zip -DestinationPath $Skills
python $Validator (Join-Path $Skills "workflow-skill-router")
```

macOS 或 Linux：

```bash
curl -L -o /tmp/workflow-skill-router-blank.zip https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-blank.zip
curl -L -o /tmp/workflow-skill-router-validate-router.py https://github.com/eric861129/Workflow-skill-router/raw/main/scripts/validate-router.py
mkdir -p "$HOME/.codex/skills"
unzip -o /tmp/workflow-skill-router-blank.zip -d "$HOME/.codex/skills"
python /tmp/workflow-skill-router-validate-router.py "$HOME/.codex/skills/workflow-skill-router"
```

預期結果：

```text
OK: workflow-skill-router passed validation
```

## 2. 盤點你的 skills

從 Agent 實際讀得到的 skills 開始。下面這組 fictional inventory 足夠做第一版 router：

| Skill | 擅長 | 建議角色 |
| --- | --- | --- |
| `requirements-clarifier` | 把模糊需求整理成 acceptance criteria | 不清楚需求的 primary |
| `api-contract-designer` | Endpoint shape、schema compatibility、API examples | API contract 的 primary |
| `vue-ui-debugger` | Vue component 行為與畫面 bug | Vue UI defect 的 primary |
| `browser-regression-runner` | Browser reproduction 與 regression checks | Supporting verifier |
| `ci-release-closer` | CI triage、release notes、branch closeout | Release finish 的 primary |
| `docs-architecture-writer` | Architecture notes、diagrams、source maps | Docs structure 的 primary |
| `data-query-reviewer` | SQL correctness 與 query performance risk | Data task 的 primary |

容易過度觸發的 broad skills 預設放 supporting。例如 `browser-regression-runner` 很有用，但不應該變成所有 frontend request 的 primary。

## 3. 填寫 `SKILL.md`

打開已安裝的 `workflow-skill-router/SKILL.md`，把 placeholder 改成短而清楚的 router contract：

```md
# Workflow Skill Router

Use this skill when a task is complex enough that choosing the right working set matters before execution starts.

Before acting, classify the request into:

1. Task nature
2. Work stage
3. Technical domain
4. One primary skill
5. Zero to three supporting skills

Output:

- Route
- Use SKILL
- Reason

Do not use this router for simple one-step questions, quick translations, or tasks that clearly need only one known skill.
```

`SKILL.md` 請保持短。完整 route tree 與 conflict rules 放進 `references/`，讓 trigger 本身維持可讀。

## 4. 填寫 `references/skill-tree.md`

用 task nature、work stage、technical domain 的方式建樹：

```md
# Skill Tree

## Clarification / Planning

- Requirements > Ambiguous feature request
  - Primary: `requirements-clarifier`
  - Supporting: `docs-architecture-writer`

## API / Contract Lifecycle

- Backend-to-frontend sync
  - Primary: `api-contract-designer`
  - Supporting: `requirements-clarifier`, `browser-regression-runner`

## Frontend / Vue / UI

- Browser-visible regression
  - Primary: `vue-ui-debugger`
  - Supporting: `browser-regression-runner`, `requirements-clarifier`

## Data / Query Safety

- Query behavior plus performance risk
  - Primary: `data-query-reviewer`
  - Supporting: `api-contract-designer`

## Documentation / Architecture

- Source map, architecture note, or diagram update
  - Primary: `docs-architecture-writer`
  - Supporting: `requirements-clarifier`

## Release / Closeout

- PR readiness, CI status, and release note
  - Primary: `ci-release-closer`
  - Supporting: `docs-architecture-writer`
```

每條 route 都要有一個 primary skill，且總 skill 數不超過四個。

## 5. 填寫 `references/routing-rules.md`

加入防止 over-routing 的規則：

```md
# Routing Rules

## Priority order

1. Prefer the skill that owns the requested work stage.
2. Add supporting skills only when they provide a distinct action: reproduce, verify, document, or inspect live state.
3. Keep each route to one primary skill and at most three supporting skills.
4. If a task needs more than four skills, split it into stages and route the first stage only.

## Conflict rules

- `vue-ui-debugger` beats `browser-regression-runner` as primary when the bug is in Vue component behavior.
- `browser-regression-runner` becomes supporting when the task needs browser reproduction or regression coverage.
- `api-contract-designer` beats `data-query-reviewer` when the request is about API shape rather than query cost.
- `ci-release-closer` is primary only when the user asks for release readiness, CI closeout, or release notes.
- `docs-architecture-writer` is primary for docs, diagrams, source maps, and architecture explanations.

## Do not route

- One-line questions
- Simple copy edits
- Pure translation
- Tasks where the user explicitly names exactly one skill and no supporting work is needed
```

## 6. 驗證

請驗證已安裝的 router folder，不是只驗證 repository starter。

Windows PowerShell：

```powershell
$Validator = Join-Path $env:TEMP "workflow-skill-router-validate-router.py"
$Router = Join-Path $env:USERPROFILE ".codex\skills\workflow-skill-router"
python $Validator $Router
```

macOS 或 Linux：

```bash
python /tmp/workflow-skill-router-validate-router.py "$HOME/.codex/skills/workflow-skill-router"
```

預期結果：

```text
OK: workflow-skill-router passed validation
```

如果驗證失敗，請看 [Troubleshooting guide](/Workflow-skill-router/zh-tw/guides/troubleshooting/)。

## 7. 實測 route

用幾個會選到不同 primary skill 的任務測試：

```text
User: Add a customer settings endpoint, update the schema, and make sure the UI client stays compatible.

Route: API / Contract Lifecycle > Backend-to-frontend sync
Use SKILL: api-contract-designer, requirements-clarifier, browser-regression-runner
Reason: api-contract-designer owns the endpoint and schema; requirements-clarifier turns compatibility into acceptance criteria; browser-regression-runner verifies the UI flow if needed.
```

```text
User: A Vue form loses selected values after browser refresh. Reproduce it and add a regression check.

Route: Frontend / Vue / UI > Browser-visible regression
Use SKILL: vue-ui-debugger, browser-regression-runner, requirements-clarifier
Reason: vue-ui-debugger owns component behavior; browser-regression-runner captures the refresh regression; requirements-clarifier keeps the acceptance criteria explicit.
```

```text
User: Finish this release branch, check CI status, and write the release note.

Route: Release / Closeout > PR readiness, CI status, and release note
Use SKILL: ci-release-closer, docs-architecture-writer
Reason: ci-release-closer owns release readiness and CI closeout; docs-architecture-writer keeps the release note clear.
```

## 8. 安全改造成自己的版本

把 fictional skill names 換成你的真實 skills，然後再次驗證。公開分享 router 前，請移除私人 repository paths、內部專案名、客戶名、hostname、branch names 與 credentials。
