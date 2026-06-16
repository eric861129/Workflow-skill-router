---
title: Blank Router Walkthrough
description: Install the blank router, fill it with a fictional skill inventory, validate it, and try a route end to end.
---

This walkthrough shows the full path from a downloaded Blank Router to a working, validated router. The example skill names are fictional so you can copy the structure without leaking private workflow details.

## What you will build

By the end, your installed skill folder will look like this:

```text
workflow-skill-router/
  SKILL.md
  agents/
    openai.yaml
  references/
    skill-tree.md
    routing-rules.md
```

The router will classify requests into one primary skill and up to three supporting skills before the agent starts work.

## 1. Download and install

Install the Blank Router into your Codex skills directory.

Windows PowerShell:

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

macOS or Linux:

```bash
curl -L -o /tmp/workflow-skill-router-blank.zip https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-blank.zip
curl -L -o /tmp/workflow-skill-router-validate-router.py https://github.com/eric861129/Workflow-skill-router/raw/main/scripts/validate-router.py
mkdir -p "$HOME/.codex/skills"
unzip -o /tmp/workflow-skill-router-blank.zip -d "$HOME/.codex/skills"
python /tmp/workflow-skill-router-validate-router.py "$HOME/.codex/skills/workflow-skill-router"
```

Expected:

```text
OK: workflow-skill-router passed validation
```

## 2. Inventory your skills

Start with the skills your agent can actually read. This fictional inventory is enough for a first router:

| Skill | Good at | Likely role |
| --- | --- | --- |
| `requirements-clarifier` | Turning vague requests into acceptance criteria | Primary for unclear work |
| `api-contract-designer` | Endpoint shape, schema compatibility, API examples | Primary for API contract work |
| `vue-ui-debugger` | Vue component behavior and rendered UI bugs | Primary for Vue UI defects |
| `browser-regression-runner` | Browser reproduction and regression checks | Supporting verifier |
| `ci-release-closer` | CI triage, release notes, branch closeout | Primary for release finish work |
| `docs-architecture-writer` | Architecture notes, diagrams, source maps | Primary for docs structure |
| `data-query-reviewer` | SQL correctness and query performance risk | Primary for data tasks |

Mark broad or easy-to-overuse skills as supporting by default. For example, `browser-regression-runner` is valuable, but it should not become the primary skill for every frontend request.

## 3. Fill `SKILL.md`

Open the installed `workflow-skill-router/SKILL.md` and replace placeholder language with a short router contract:

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

Keep `SKILL.md` short. Put the full route tree and conflict rules in the `references/` files so the trigger stays readable.

## 4. Fill `references/skill-tree.md`

Use a tree that goes from task nature to work stage to technical domain:

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

Every route has one primary skill. No route has more than four total skills.

## 5. Fill `references/routing-rules.md`

Add rules that prevent over-routing:

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

## 6. Validate

Validate the installed router folder, not only the repository starter.

Windows PowerShell:

```powershell
$Validator = Join-Path $env:TEMP "workflow-skill-router-validate-router.py"
$Router = Join-Path $env:USERPROFILE ".codex\skills\workflow-skill-router"
python $Validator $Router
```

macOS or Linux:

```bash
python /tmp/workflow-skill-router-validate-router.py "$HOME/.codex/skills/workflow-skill-router"
```

Expected:

```text
OK: workflow-skill-router passed validation
```

If validation fails, open the [Troubleshooting guide](/Workflow-skill-router/guides/troubleshooting/).

## 7. Try realistic routes

Use tasks that should choose different primary skills:

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

## 8. Adapt safely

Replace the fictional skill names with your real skills, then run validation again. When sharing your router publicly, remove private repository paths, internal project names, customer names, hostnames, branch names, and credentials.
