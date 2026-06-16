---
title: Claude, Cursor, and Gemini Adapter Notes
description: Adapt the router pattern for agents that can read custom instructions, rules, or project context.
---

Workflow Skill Router is Codex-ready, but the core contract is plain text. Any agent that can read project instructions, rules, or custom context can use the same pattern:

1. Inventory the available skills or workflows.
2. Build a small routing tree.
3. Add conflict rules.
4. Ask the agent to output `Route`, `Use SKILL`, and `Reason` before complex work.
5. Validate the router text with the repository validator when the folder shape matches the starter.

The exact settings screens for AI tools change over time. Treat this page as an adapter pattern, then check your tool's current official docs for the exact location of custom instructions or project rules.

## What is portable

| Part | Portable? | Notes |
| --- | --- | --- |
| Skill inventory | Yes | Use the tool's real capabilities, commands, and rules as the inventory source. |
| Skill tree | Yes | Plain Markdown works across agents. |
| Routing rules | Yes | Conflict rules are the most important portable part. |
| `SKILL.md` auto-loading | Codex-specific | Other tools may need the router pasted into project instructions or rules. |
| `agents/openai.yaml` | Codex/OpenAI-specific | Treat it as metadata, not required adapter input. |
| Python validator | Yes | It validates the folder shape and public-safe starter files. |

## Claude adapter pattern

Use this when Claude can read repository instructions or project-level context.

```text
Use Workflow Skill Router as a pre-execution routing step.

Before complex work, read the router inventory, skill tree, and routing rules. Then output:

Route: <task nature / work stage > technical domain>
Use SKILL: <one primary skill, up to three supporting skills>
Reason: <why this small working set is enough>

Do not route simple one-step questions. Do not choose more than four skills. If more skills seem necessary, split the work into stages and route the first stage.
```

Recommended placement:

- Put the route contract in the project or repository instruction surface that Claude reads.
- Keep the full skill tree in a linked Markdown file when the tool supports project files.
- Do not paste private skill folders into public chats or shared artifacts.

## Cursor adapter pattern

Use this when Cursor can read repository rules or workspace instructions.

```text
For multi-step coding tasks, first run a Workflow Skill Router decision.

Choose:
- 1 primary workflow or rule set
- 0-3 supporting workflows or rule sets

Return the route before editing files. Keep the route small and explain why unrelated rules were not selected.
```

Recommended placement:

- Put the short route contract in the workspace rules surface.
- Keep detailed route examples in a committed docs file if the team wants shared behavior.
- Keep tool-specific file paths out of public examples unless they are intentionally generic.

## Gemini adapter pattern

Use this when Gemini can read project context, custom instructions, or uploaded Markdown.

```text
Before solving a complex request, classify it with the Workflow Skill Router pattern.

Output:
Route:
Use SKILL:
Reason:

Use the smallest working set. Prefer the primary skill that owns the work stage. Add supporting skills only for distinct actions such as reproduction, verification, documentation, or live-state inspection.
```

Recommended placement:

- Provide the router as a project context document or reusable instruction.
- Keep examples short because long pasted catalogs can bury the actual task.
- Re-run routing when a task changes from planning to implementation, debugging, or release closeout.

## Validation workflow

If your adapted router still uses the starter folder shape, validate it with:

```bash
python scripts/validate-router.py path/to/workflow-skill-router
```

If your target tool does not use a `SKILL.md` folder shape, validate the logic manually:

- Every route has one primary skill.
- Every route has at most three supporting skills.
- Supporting skills have distinct jobs.
- Simple tasks are allowed to skip routing.
- Conflict rules explain why broad skills do not over-trigger.

## Sharing adapter notes publicly

Use fictional examples when publishing adapter notes. Do not include private repository paths, internal project names, customer names, hostnames, tokens, or tool-specific secrets.
