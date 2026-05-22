# Agent Prompt English

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
