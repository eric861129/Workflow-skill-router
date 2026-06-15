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

Router package validation:

- `SKILL.md` exists.
- YAML frontmatter has only `name` and `description`.
- `references/skill-tree.md` exists.
- `references/routing-rules.md` exists.
- route lines include `Primary:`.
- each route chooses at most four skills.
- examples include a `README.md`.
- placeholder starter skills are clearly marked.
- router files do not contain obvious private identifiers.

## Public-readiness audit

Use this before publishing a router repo, release, or public template package:

```bash
python scripts/validate-router.py --public-readiness .
```

Expected:

```text
OK: public-readiness audit passed
```

The audit checks:

- README, license, security policy, code of conduct, contributing guide, funding metadata, issue templates, and PR template.
- starter router and template example validation.
- blank/template downloads and manifest files.
- Starlight site entrypoints, robots file, and social preview asset.
- stale multi-example pages or source folders that conflict with the single template catalog.
- obvious private identifiers, school or internal names, mojibake, replacement characters, and hidden edit-link UI text.

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

