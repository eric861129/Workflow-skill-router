---
title: Quickstart
description: Install the starter router, fill your skill tree, and validate it.
---

## 1. Copy the starter

Copy this folder into your agent's skill directory:

```text
starter/workflow-skill-router/
```

Or download the ready-to-install zip:

- [Blank SKILL package](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-blank.zip)
- [View starter source folder](https://github.com/eric861129/Workflow-skill-router/tree/main/starter/workflow-skill-router)

For Codex on Windows:

```text
C:\Users\<you>\.codex\skills\workflow-skill-router
```

## 2. Ask your agent to fill the router

Use the English prompt below, or open the source file:

- [View `prompts/agent-prompt.en.md` on GitHub](https://github.com/eric861129/Workflow-skill-router/blob/main/prompts/agent-prompt.en.md)

### Initial Setup Prompt

```text
You are helping me build a workflow-skill-router for my current multi-skill AI agent environment.

First, read this repository's method documents:
- README.en.md
- docs/system-theory.en.md
- docs/validation-checklist.en.md
- starter/workflow-skill-router/SKILL.md
- starter/workflow-skill-router/references/skill-tree.md
- starter/workflow-skill-router/references/routing-rules.md

Your goal is not to add many new skills, and it is not to reuse the example skill list. Your goal is to inspect my currently installed, enabled, or agent-readable skills, then fill the blank starter template into a vertical routing system for my environment.

Follow these steps:

1. Inventory currently available skills
   - Find every skill this agent can use.
   - For each skill, capture: name, source, purpose, suitable tasks, whether it is a connector/plugin, and whether it is a meta workflow.
   - If the environment cannot automatically read the skill list, ask me for the skill directory or ask me to paste the list.

2. Build functional classification
   Do not use only flat categories. Use this structure:

   Task nature
     -> Work stage
       -> Technical domain
         -> The actual 1-4 skills to use

   Each leaf route may contain at most 4 skills.
   Each leaf route must have 1 primary skill; the others are supporting skills.
   If a category needs more than 4 skills, split it into multiple work stages.

3. Create conflict rules
   Identify skills that overlap or tend to trigger too broadly, then write selection rules.

   Examples:
   - local custom skill vs plugin connector skill
   - browser automation skill vs scripted Playwright skill
   - code review skill vs GitHub PR comment skill
   - broad meta workflow skill vs narrow task skill
   - docs/writing skill vs file-format connector skill

4. Produce the workflow-skill-router design and fill the starter template
   Output the following:

   A. Skill Inventory Summary
   - Group by source: custom / system / plugin / connector / unknown
   - Mark high-value skills, low-frequency skills, and skills likely to over-trigger

   B. Workflow Skill Tree
   - Use: task nature -> work stage -> technical domain -> skills
   - Keep each route to at most 4 skills

   C. Routing Rules
   - Priority order
   - Conflict handling
   - When not to use the router
   - When connector/plugin skills must come first

   D. Recommended workflow-skill-router Files
   - Actual SKILL.md based on starter/workflow-skill-router/SKILL.md
   - Filled references/skill-tree.md based on the inventory
   - Filled references/routing-rules.md based on conflicts and priority rules
   - If the platform supports UI metadata, filled agents/openai.yaml or the equivalent configuration

5. Validate
   Test the classification with at least 6 realistic task scenarios:
   - Backend API task
   - Frontend UI or browser debugging task
   - Documentation or architecture diagram task
   - GitHub PR / CI task
   - External connector task
   - A simple task that should not over-trigger the router

Important constraints:
- Do not design the router as a super skill.
- Do not suggest disabling every other skill and keeping only the router.
- Do not select more than 4 skills for a single route.
- Do not include a skill merely because it is related; include only what the task truly needs.
- Do not treat this repository's example skill list as my actual skill list; use my current environment as the source of truth.
- If file edits are needed, explain which files will be created or changed before making changes.

Reply in clear Markdown with tables where useful.
```

### Maintenance Prompt: Add Specified New Skills To An Existing Router

```text
I have already configured workflow-skill-router once. I have now added the following skills. Please help me integrate them into the existing workflow-skill-router.

New skills:
- <paste the skill name, path, or description>
- <paste the skill name, path, or description>

First, read my currently installed workflow-skill-router:
- SKILL.md
- references/skill-tree.md
- references/routing-rules.md
- agents/openai.yaml or equivalent metadata file, if present

Your goal is not to rebuild the whole router, and it is not to insert the new skills into every related category.
Your goal is to decide what role these new skills should play in the existing routing system, then make the smallest necessary update.

Follow these steps:

1. Read the specified new skills
   - Confirm each skill's name, source, purpose, and suitable tasks.
   - Decide whether it is a connector/plugin, system skill, custom skill, or meta workflow.
   - If you cannot read the skill content, clearly tell me what information is missing.

2. Compare against the existing workflow-skill-router
   - Check whether references/skill-tree.md already contains the same or highly overlapping skills.
   - Check whether references/routing-rules.md already contains related conflict rules.
   - Decide whether each new skill should add a route, replace an existing supporting skill, or only appear in conflict rules.

3. Update the skill tree
   - Each route must still contain at most 4 skills.
   - Each route must still have 1 Primary skill; the others are Supporting skills.
   - Do not add a new skill merely because it is related. Add it only when it is better suited than the existing skills for a specific task stage.
   - If adding it would make a route exceed 4 skills, split the route into a more precise work stage.

4. Update conflict rules
   - If a new skill overlaps with existing skills, add a selection rule.
   - If a new skill is a connector/plugin, state when it should be preferred.
   - If a new skill is a meta workflow, state when it should not be enabled by default.

5. Validate
   - List which files were changed.
   - List which routes now include the new skills.
   - Test the new routing with 2-3 realistic task scenarios.
   - Confirm that no route contains more than 4 skills.

Important constraints:
- Do not rebuild the whole workflow-skill-router.
- Do not remove existing skills unless a new skill truly replaces one, and explain why.
- Do not add new skills to every place that looks related.
- If file edits are needed, explain which files will be changed before making changes.

Reply with a table covering: new skill, recommended category, Primary/Supporting role, edit location, and reason.
```

### Maintenance Prompt: Detect Newly Added Skills Missing From The Router

```text
I have already configured workflow-skill-router once, but I may have added more skills afterward.
Please inspect the current environment, find skills that are installed or agent-readable but missing from workflow-skill-router, and decide whether they should be added.

First, read my currently installed workflow-skill-router:
- SKILL.md
- references/skill-tree.md
- references/routing-rules.md
- agents/openai.yaml or equivalent metadata file, if present

Then inventory currently available skills:
- Find every skill the current agent can use, has installed, has enabled, or can read.
- Group them by source: custom / system / plugin / connector / meta workflow / unknown.
- Compare them against references/skill-tree.md and references/routing-rules.md to find skills that are missing or only partially recorded.

Follow these steps:

1. Produce a diff list
   - Skills fully recorded in the router.
   - Skills not recorded but recommended for inclusion.
   - Skills not recorded and not recommended for inclusion.
   - Skills that only need routing-rules coverage, not skill-tree routes.

2. Decide whether each missing skill should be added
   Use these criteria:
   - Does it cover a task type the current router does not handle?
   - Is it better than an existing skill as the Primary skill for a route?
   - Is it only useful as a Supporting skill?
   - Is it a connector/plugin that must be preferred for external data or a specific runtime?
   - Is it a broad meta workflow that should avoid default activation?

3. Update workflow-skill-router
   - Update references/skill-tree.md when necessary.
   - Update references/routing-rules.md when necessary.
   - Update the Skill Inventory Summary when necessary.
   - Keep every route to at most 4 skills.
   - Mark Primary and Supporting skills explicitly for every route.

4. Validate
   - Test the updated routing with at least 3 scenarios.
   - Confirm simple tasks do not over-trigger the router.
   - Confirm connector/plugin tasks still prefer the matching connector/plugin skill.
   - Confirm meta workflows were not over-added to normal routes.

Important constraints:
- Do not add every missing skill to skill-tree.
- Do not assume a skill belongs in the router merely because it exists.
- Do not rebuild the whole router; prefer diff-based updates.
- Do not let any single route exceed 4 skills.
- If file edits are needed, explain which files will be changed before making changes.

Reply with:

1. Missing Skill Diff Summary
2. Recommended Additions
3. Skills Not Added And Why
4. Updated Routes
5. Validation Results
```

The agent should inventory available skills and fill:

```text
workflow-skill-router/
  SKILL.md
  references/
    skill-tree.md
    routing-rules.md
```

## 3. Validate

Run:

```bash
python scripts/validate-router.py starter/workflow-skill-router
```

Expected:

```text
OK: workflow-skill-router passed validation
```

For a fuller reference, download the [template SKILL package](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template.zip). It includes a public-safe export of the maintainer's real local Codex skills catalog and a sanitized `workflow-skill-router`.

Source:

- [Template manifest](https://github.com/eric861129/Workflow-skill-router/blob/main/downloads/workflow-skill-router-template-manifest.md)
- [Package builder script](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/package-downloads.py)

## 4. Try a route

Ask a complex task:

```text
Debug a browser-only bug in the customer portal and add a regression check.
```

Expected shape:

```text
Route: Frontend / Debugging > Browser reproduction > Customer portal
Use SKILL: frontend-debugging, browser, playwright
Reason: frontend-debugging maps UI symptoms to source; browser reproduces rendered behavior; playwright captures the regression.
```

