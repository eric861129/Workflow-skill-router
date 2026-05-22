# Workflow Skill Router System Theory

Workflow Skill Router is a vertical routing layer for multi-skill AI agents. It does not add capability by itself. It decides which capabilities to use, in what order, and which ones to avoid for the current task.

## 1. The Problem

When a system has only a few skills, a flat list is easy to manage:

```text
api-designer
csharp-developer
vue-expert
systematic-debugging
qa-test-planner
```

When the list grows to dozens of skills, flat discovery starts to fail:

- Selection cost increases.
- Several skills overlap.
- Meta skills trigger too often.
- Connector skills get replaced by generic docs or engineering skills.
- The agent loads too many workflows and performs worse.

The router turns a flat capability list into workflow decisions.

## 2. Core Model

```text
Task nature
  -> Work stage
    -> Technical domain
      -> 1 primary skill + 0-3 supporting skills
```

Example:

```text
Architecture/API/Backend
  -> API contract design
    -> C#/.NET
      -> api-designer, csharp-developer, database-schema-designer, qa-test-planner
```

The same technical domain should use different skills at different stages:

| Work stage | Main question | Skill |
|---|---|---|
| Requirements | What should be built, and what is out of scope? | `requirements-clarity` |
| Contract design | API resources, versions, and error shape | `api-designer` |
| Implementation | C# / .NET implementation patterns | `csharp-developer` |
| Data design | Schema, indexes, relationships | `database-schema-designer` |
| Acceptance | Test cases and risks | `qa-test-planner` |

## 3. The Router Is Not A Super Skill

The router does three things:

1. Classify the task.
2. Select the smallest sufficient skill set.
3. Explain the choice.

It should not copy the full content of every skill into itself. That would create another large, vague, noisy meta skill.

## 4. Recommended Files

```text
workflow-skill-router/
  SKILL.md
  references/
    skill-tree.md
    routing-rules.md
  agents/
    openai.yaml
```

### SKILL.md

Keep only:

- When to use it.
- When not to use it.
- The routing workflow.
- The output contract.
- The maximum number of skills.

### skill-tree.md

Store the full decision tree:

```text
task nature / work stage / technical domain: `skill-a`, `skill-b`, `skill-c`
```

Each leaf route should select at most 4 skills.

### routing-rules.md

Store overlap and priority rules:

- Local skill vs plugin skill.
- Browser vs Playwright.
- Review skill vs GitHub connector.
- When meta skills are allowed.

## 5. Priority Rules

Recommended priority:

1. Respect explicit user skill requests.
2. Prefer connector/plugin skills when an external system is central to the task.
3. Prefer local custom skills for general engineering judgment.
4. Use system skills for OpenAI, image, plugin, and skill installation tasks.
5. Use large meta skills only when explicitly needed.

## 6. Skill Count Rule

```text
Narrow task: 1 primary skill
Cross-domain task: 2-4 skills
More than 4: split into stages
```

If a route needs more than 4 skills, it is not a route. It is a multi-stage project.

## 7. Output Contract

```text
Route: task nature > work stage > technical domain
Use SKILL: skill-a, skill-b, skill-c
Reason: one short sentence per skill
```

Simple task:

```text
No extra routing needed: this is a single-step task.
```

This contract gives the user a chance to correct the route before the agent goes too far.

## 8. Common Anti-Patterns

### Only Keeping The Router

Wrong:

```text
Disable every other skill and keep only workflow-skill-router.
```

Right:

```text
Keep the other skills. Let the router choose and order them.
```

### Listing Everything Related

Wrong:

```text
UI task: frontend-design, ui-ux-pro-max, vue-expert, shadcn, browser, playwright, qa-test-planner, ...
```

Right:

```text
UI task: frontend-design, ui-ux-pro-max, vue-expert, browser
```

### Enabling Meta Skills By Default

Large workflows should be conservative. Use them only when the task needs that method.

### Ignoring Connectors

When the task involves GitHub, Teams, Notion, Word, Excel, Slides, or another external system, connector skills should come first.

## 9. Validation

The router should pass at least:

- Valid `SKILL.md` frontmatter.
- At most 4 skills per leaf route.
- At least 6 realistic scenario tests.
- Simple tasks do not trigger multi-skill routing.
- Connector tasks prefer connectors.

See [validation-checklist.en.md](validation-checklist.en.md).

## 10. Summary

The core idea:

```text
Use vertical structure to manage horizontal expansion.
```

When the skill list grows, do not rush to delete everything or let the agent scatter freely. Add a thin routing layer so each task loads the smallest, sharpest, most useful skill set.
