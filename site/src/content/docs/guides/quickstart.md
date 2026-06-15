---
title: Quickstart
description: Install the starter router, fill your skill tree, and validate it.
---

## 1. Copy the starter

Copy this folder into your agent's skill directory:

```text
starter/workflow-skill-router/
```

For Codex on Windows:

```text
C:\Users\<you>\.codex\skills\workflow-skill-router
```

## 2. Ask your agent to fill the router

Use the prompt in the repository:

```text
prompts/agent-prompt.en.md
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

