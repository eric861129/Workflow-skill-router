# Workflow Skill Router

> Help a multi-skill AI agent choose the right workflow before it starts working.

Language: [繁體中文](README.zh-TW.md)

As an AI agent gains more skills, the main problem is often no longer capability. The main problem becomes:

```text
Which skills should be used for this task?
Which skills are merely related but should stay inactive?
Should requirements, design, implementation, and verification use the same skills?
```

Workflow Skill Router is a method and blank starter template for turning a user's actual skill set into a vertical routing system:

```text
Task nature
  -> Work stage
    -> Technical domain
      -> The actual 1-4 skills to use
```

This repository is not a fixed skill list. It teaches the method and provides a blank router skill template. The user can copy the template, then use the included prompt to ask an AI agent to inspect the currently installed skills and fill in a personalized `workflow-skill-router`.

## Why This Design

### 1. More Skills Do Not Automatically Mean Better Work

After a system gains many skills, the agent faces a selection problem:

- An API task may involve API, backend, database, testing, and documentation skills.
- A frontend task may involve UI, framework, browser, Playwright, and QA skills.
- A GitHub task may need a connector skill, but also review reasoning.

Without a routing layer, an agent may treat "related" as "needed."

### 2. A Flat List Cannot Represent Work Stages

The same backend task needs different skills at different stages:

| Work stage | Question |
|---|---|
| Requirements | What problem are we solving, and what is out of scope? |
| API design | What are the resources, errors, and versioning rules? |
| Implementation | Which framework and existing architecture should be used? |
| Database | What schema, indexes, and transaction boundaries are needed? |
| Verification | Which success and failure cases should be tested? |

Workflow Skill Router adds a work-stage layer on top of technical categories, so the agent does not load every related skill at once.

### 3. The Router Does Not Replace Skills

The router is not a super skill. It does only three things:

1. Classify the task.
2. Select the smallest sufficient skill set.
3. Explain why those skills were selected.

API design, UI design, debugging, documentation, and implementation still belong to the actual selected skills.

## How To Use

### Step 1: Copy The Blank Starter

Copy this folder into your agent's skill directory:

```text
starter/workflow-skill-router/
```

For Codex on Windows:

```text
C:\Users\<you>\.codex\skills\workflow-skill-router
```

This is a blank starter. It contains the full specification and structure, but it does not yet contain your actual skill inventory.

### Step 2: Give The Prompt To Your AI Agent

Use the English prompt:

[prompts/agent-prompt.en.md](prompts/agent-prompt.en.md)

The prompt asks the agent to:

- Read this repository's method.
- Inventory your currently available skills.
- Classify skills by task nature, work stage, and technical domain.
- Generate `skill-tree.md` and `routing-rules.md`.
- Validate that each route selects no more than 4 skills.

### Step 3: Let The Agent Fill Your Router

The agent should update these starter files:

```text
workflow-skill-router/
  SKILL.md
  references/
    skill-tree.md
    routing-rules.md
  agents/
    openai.yaml
```

After that, the skill becomes your environment-specific multi-skill router.

## Blank Starter

The starter is here:

[starter/workflow-skill-router](starter/workflow-skill-router)

It includes:

- `SKILL.md`: the router skill specification with placeholders.
- `references/skill-tree.md`: a placeholder tree for the agent to fill from the user's installed skills.
- `references/routing-rules.md`: placeholder priority and conflict rules.
- `agents/openai.yaml`: Codex UI metadata template.

## Chinese Area And English Area

This repository is split by language so readers can stay in one language path.

Chinese area:

- [README.zh-TW.md](README.zh-TW.md): Chinese introduction and usage flow.
- [docs/system-theory.zh-TW.md](docs/system-theory.zh-TW.md): method details.
- [docs/validation-checklist.zh-TW.md](docs/validation-checklist.zh-TW.md): validation checklist.
- [prompts/agent-prompt.zh-TW.md](prompts/agent-prompt.zh-TW.md): Chinese agent prompt.

English area:

- [README.en.md](README.en.md): English introduction and usage flow.
- [docs/system-theory.en.md](docs/system-theory.en.md): method details.
- [docs/validation-checklist.en.md](docs/validation-checklist.en.md): validation checklist.
- [prompts/agent-prompt.en.md](prompts/agent-prompt.en.md): English agent prompt.

Shared templates:

- [starter/workflow-skill-router](starter/workflow-skill-router): blank skill starter.
- [templates](templates): single-file templates.

## Routing Output Contract

For complex work:

```text
Route: task nature > work stage > technical domain
Use SKILL: primary-skill, supporting-skill, supporting-skill
Reason: one short sentence per skill
```

For simple work:

```text
No extra routing needed: this is a single-step task.
```

## Design Principles

- Do not disable every other skill and keep only the router.
- Do not turn the router into a giant super skill.
- Select at most 4 skills per route.
- The router chooses and explains; the selected skills do the work.
- When the task needs GitHub, Teams, Notion, Word, Excel, Browser, or other live external data, connector/plugin skills come first.
- If a route appears to need more than 4 skills, split it into work stages.

## License

No license is included yet. Add a license before publishing if you want others to reuse, modify, or redistribute this project.
