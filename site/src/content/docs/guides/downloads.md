---
title: Downloads
description: Download a blank router skill or a practical template package.
---

## Download packages

Use the blank package when you want to install the router and fill your own skill tree from scratch.

- [Download blank skill](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-blank.zip)

Use the template package when you want a public-safe copy of a real local Codex skills catalog.

- [Download template skill package](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template.zip)
- [View template manifest](https://github.com/eric861129/Workflow-skill-router/blob/main/downloads/workflow-skill-router-template-manifest.md)

## What is inside

The blank package contains:

```text
workflow-skill-router/
  SKILL.md
  agents/openai.yaml
  references/skill-tree.md
  references/routing-rules.md
```

The template package contains:

```text
workflow-skill-router-template/
  README.md
  MANIFEST.md
  skills/
    workflow-skill-router/
    .system/
    <public-safe skill folders>
```

The template package is public-safe. It is generated from the maintainer's real `.codex/skills` folder, excludes private organization-specific skills, and omits private lines from otherwise public skill files.

## Rebuild locally

```bash
python scripts/package-downloads.py --skills-root <path-to-local-codex-skills> --exclude-prefix <private-prefix> --exclude-name <private-skill-name> --private-marker <private-text-marker>
```

## Source

- [View `downloads/` on GitHub](https://github.com/eric861129/Workflow-skill-router/tree/main/downloads)
- [View package builder script](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/package-downloads.py)
- [View template manifest](https://github.com/eric861129/Workflow-skill-router/blob/main/downloads/workflow-skill-router-template-manifest.md)
- [View starter source](https://github.com/eric861129/Workflow-skill-router/tree/main/starter/workflow-skill-router)
