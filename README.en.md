# Workflow Skill Router

> A lightweight routing layer for multi-skill AI agents.

As an AI agent gains more skills, the hard problem is often no longer capability. The hard problem is choosing the right skills for the current task. Workflow Skill Router provides a reusable method for turning a flat skill list into a vertical decision tree.

Language: [繁體中文](README.zh-TW.md)

## Core Model

```text
Task nature
  -> Work stage
    -> Technical domain
      -> 1-4 actual skills
```

This project provides:

- A method for routing multi-skill AI agent work.
- Reusable `SKILL.md`, `skill-tree.md`, and `routing-rules.md` templates.
- A working Codex `workflow-skill-router` example.
- Chinese and English copy-paste prompts for AI agents.
- A validation checklist to avoid trigger noise and skill sprawl.

## Why

Multi-skill systems usually hit three problems:

1. **Higher selection cost**: one task may appear relevant to many skills.
2. **More trigger noise**: broad meta skills may activate too often.
3. **Unclear execution order**: requirements, design, implementation, tests, and handoff are mixed at the same level.

Workflow Skill Router does not replace other skills. It chooses the smallest sufficient skill set before work starts.

```text
workflow-skill-router
  -> select 1 primary skill
  -> select up to 3 supporting skills
  -> explain why
  -> continue with the actual task
```

## Project Structure

```text
workflow-skill-router/
  README.md
  README.zh-TW.md
  README.en.md
  docs/
    system-theory.zh-TW.md
    system-theory.en.md
    validation-checklist.zh-TW.md
    validation-checklist.en.md
  prompts/
    agent-prompt.zh-TW.md
    agent-prompt.en.md
  templates/
    SKILL.md
    skill-tree.md
    routing-rules.md
  examples/
    codex-workflow-skill-router/
      SKILL.md
      references/
        skill-tree.md
        routing-rules.md
      agents/
        openai.yaml
```

## Quick Start

1. Copy `examples/codex-workflow-skill-router/` into your Codex skills folder.
2. Replace the example skill names in `references/skill-tree.md` with your own installed skills.
3. Update `references/routing-rules.md` with your overlap and priority rules.
4. Validate that each leaf route chooses no more than 4 skills.
5. Test it against real prompts before relying on it.

A typical Codex target path on Windows:

```text
C:\Users\<you>\.codex\skills\workflow-skill-router
```

## Copy-paste Agent Prompt

Full English version:

[prompts/agent-prompt.en.md](prompts/agent-prompt.en.md)

Short version:

```text
Read this repository's method docs, inspect my currently available skills, then build a workflow-skill-router using the structure: task nature -> work stage -> technical domain -> 1-4 skills.

Output:
1. Skill Inventory Summary
2. Workflow Skill Tree
3. Routing Rules
4. Recommended workflow-skill-router files
5. At least 6 scenario validations

Constraints: do not design the router as a super skill; do not suggest disabling all other skills; keep each route to at most 4 skills.
```

## Routing Output Contract

For complex work:

```text
Route: task nature > work stage > technical domain
Use SKILL: primary-skill, supporting-skill, supporting-skill
Reason: one short sentence per SKILL
```

For simple work:

```text
No extra routing needed: this is a single-step task.
```

## Design Principles

- The router is not a super skill.
- Keep `SKILL.md` short.
- Put the full tree in `references/skill-tree.md`.
- Put conflict rules in `references/routing-rules.md`.
- Choose at most 4 skills per route.
- Prefer connector/plugin skills when the task needs live external data.
- Keep broad meta skills opt-in unless the workflow truly requires them.

See [docs/system-theory.en.md](docs/system-theory.en.md) for the full method.

## Example

Backend API task:

```text
Route: Architecture/API/Backend > API contract design > C#/.NET
Use SKILL: api-designer, csharp-developer, database-schema-designer, qa-test-planner
Reason: api-designer defines the API contract; csharp-developer handles .NET implementation; database-schema-designer covers the data model; qa-test-planner adds acceptance cases.
```

Frontend debugging task:

```text
Route: Frontend/Web/UI > Debug > Browser verification
Use SKILL: frontend-testing-debugging, browser, systematic-debugging
Reason: frontend-testing-debugging targets rendered UI failures; browser verifies the local app visually; systematic-debugging keeps the work grounded in root cause.
```

## License

No license is included yet. Add a license before publishing if you want others to reuse, modify, or redistribute this project.
