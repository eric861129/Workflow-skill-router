---
title: Downloads
description: Download a blank router skill or a practical template package.
---

## Download packages

Use the blank package when you want to install the router and fill your own skill tree from scratch.

- [Download blank skill](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-blank.zip)

Use the template package when you want a working reference with concrete examples.

- [Download template skill package](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template.zip)

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
  starter/workflow-skill-router/
  examples/common-engineering-routing/
  sample-skills/
```

The template package is public-safe. It includes practical skill writing patterns and realistic engineering routes, but excludes organization-specific names, private paths, deployment details, and internal systems.

## Rebuild locally

```bash
python scripts/package-downloads.py
```

## Source

- [View `downloads/` on GitHub](https://github.com/eric861129/Workflow-skill-router/tree/main/downloads)
- [View package builder script](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/package-downloads.py)
- [View starter source](https://github.com/eric861129/Workflow-skill-router/tree/main/starter/workflow-skill-router)
- [View template example source](https://github.com/eric861129/Workflow-skill-router/tree/main/examples/common-engineering-routing)
- [View sample skills source](https://github.com/eric861129/Workflow-skill-router/tree/main/sample-skills)
