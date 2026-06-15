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

## Public-readiness audit

Use this before publishing a router repo, release, or public template package:

```bash
python scripts/audit-public-readiness.py .
```

Expected:

```text
OK: public-readiness audit passed
```

The audit checks:

- README, license, security policy, code of conduct, contributing guide, funding metadata, issue templates, and PR template.
- starter router and template example validation.
- blank/template downloads and manifest files.
- template catalog routes cover every skill listed in the template manifest and do not reference skills outside it.
- Starlight site entrypoints, robots file, and social preview asset.
- stale multi-example pages or source folders that conflict with the single template catalog.
- mojibake, replacement characters, and hidden edit-link UI text.

The legacy validator flag remains available for existing scripts:

```bash
python scripts/validate-router.py --public-readiness .
```

## Lighthouse / Accessibility audit

Use this before a public launch to score the generated Starlight site:

```bash
cd site
npm run audit:lighthouse
```

Expected:

```text
OK: Lighthouse audit passed. Reports written to lighthouse-reports
```

The audit builds the site, serves `site/dist` locally, runs Lighthouse on key English and Traditional Chinese pages, and writes JSON/HTML reports to `site/lighthouse-reports/`.

## Self-test

```bash
python scripts/validate-router.py --self-test
```

Expected:

```text
OK: validator self-test passed
```

## Source

- [View `scripts/audit-public-readiness.py` on GitHub](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/audit-public-readiness.py)
- [View `scripts/validate-router.py` on GitHub](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/validate-router.py)
- [View `site/scripts/lighthouse-audit.mjs` on GitHub](https://github.com/eric861129/Workflow-skill-router/blob/main/site/scripts/lighthouse-audit.mjs)
- [View starter router used by the command](https://github.com/eric861129/Workflow-skill-router/tree/main/starter/workflow-skill-router)
- [View example routers](https://github.com/eric861129/Workflow-skill-router/tree/main/examples)

