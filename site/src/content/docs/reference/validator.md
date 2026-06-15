---
title: Validator CLI
description: Validate router packages before publishing or sharing them.
---

The repository includes a dependency-free validator:

```bash
python scripts/validate-router.py starter/workflow-skill-router
```

Expected:

```text
OK: workflow-skill-router passed validation
```

## What it checks

- `SKILL.md` exists.
- YAML frontmatter has only `name` and `description`.
- `references/skill-tree.md` exists.
- `references/routing-rules.md` exists.
- route lines include `Primary:`.
- each route chooses at most four skills.
- examples include a `README.md`.
- public examples do not contain obvious private identifiers.

## Self-test

```bash
python scripts/validate-router.py --self-test
```

Expected:

```text
OK: validator self-test passed
```

## Source

- [View `scripts/validate-router.py` on GitHub](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/validate-router.py)
- [View starter router used by the command](https://github.com/eric861129/Workflow-skill-router/tree/main/starter/workflow-skill-router)
- [View example routers](https://github.com/eric861129/Workflow-skill-router/tree/main/examples)

