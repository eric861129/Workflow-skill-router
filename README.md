# Workflow Skill Router

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Validation](https://img.shields.io/badge/validator-python%20scripts%2Fvalidate--router.py-brightgreen.svg)](scripts/validate-router.py)
[![Languages](https://img.shields.io/badge/docs-English%20%7C%20Traditional%20Chinese-informational.svg)](README.zh-TW.md)

> A practical routing pattern that helps AI agents choose the smallest useful skill set before complex work starts.

Modern AI coding agents can have dozens of skills, tools, connectors, and workflows. The hard part is no longer "can the agent do this?" The hard part is:

```text
Which skills should be active for this task?
Which skills are merely related but should stay inactive?
Should planning, implementation, debugging, and verification use the same skills?
```

Workflow Skill Router turns a flat skill list into a decision layer:

```text
Task nature
  -> Work stage
    -> Technical domain
      -> 1 primary skill + up to 3 supporting skills
```

It is not a super skill. It is a small front door that tells an agent what to load next.

## Before And After

Without routing, a frontend bug can trigger every related skill:

```text
frontend, ui, browser, playwright, qa, design-system, github, docs, deployment
```

With routing, the agent selects a small working set:

```text
Route: Frontend / Debugging > Browser reproduction > Single-page app
Use SKILL: frontend-debugging, browser, systematic-debugging
Reason: frontend-debugging handles rendered UI failures; browser reproduces the issue; systematic-debugging keeps the investigation causal.
```

## 30 Second Quickstart

Website: `https://huangchiyu.com/Workflow-skill-router/`
Traditional Chinese site: `https://huangchiyu.com/Workflow-skill-router/zh-tw/`

1. Copy the starter into your agent's skill directory:

   ```text
   starter/workflow-skill-router/
   ```

2. Ask your agent to inventory its available skills and fill:

   ```text
   workflow-skill-router/
     SKILL.md
     references/
       skill-tree.md
       routing-rules.md
   ```

3. Validate the router:

   ```bash
   python scripts/validate-router.py starter/workflow-skill-router
   ```

Expected result:

```text
OK: workflow-skill-router passed validation
```

## What Is Included

- `starter/workflow-skill-router/`: a Codex-ready starter skill with an agent-agnostic routing contract.
- `examples/`: example routers, from minimal generic routing to realistic engineering workflows.
- `sample-skills/`: copyable public `SKILL.md` examples that pair with the common engineering routes.
- `recipes/`: short practical patterns for API contract sync, frontend debugging, PR/CI work, documentation, and connector-heavy workflows.
- `scripts/validate-router.py`: dependency-free validation for router structure, route size, Primary markers, and privacy leaks.
- `site/`: Astro Starlight website for GitHub Pages.
- `prompts/`: copy-paste prompts for creating or updating a personalized router.
- `docs/`: conceptual docs, customization guidance, and validation checklists.

## Example Routers

| Example | Best for |
| --- | --- |
| `examples/generic-agent` | Any agent with a small skill catalog |
| `examples/common-engineering-routing` | Realistic engineering routes with concrete skill names |
| `examples/enterprise-fullstack` | Backend, frontend, docs, CI, and release routing |
| `examples/frontend-debugging` | Browser vs Playwright vs UI debugging decisions |
| `examples/github-ci-review` | GitHub PR review, CI failure, and release readiness |
| `examples/company-platform-sanitized` | An anonymized company platform workflow with real-world complexity |

## Learn More

- [English guide](README.en.md)
- [繁體中文說明](README.zh-TW.md)
- [Website](https://huangchiyu.com/Workflow-skill-router/)
- [Traditional Chinese site](https://huangchiyu.com/Workflow-skill-router/zh-tw/)
- [Customization guide](docs/adoption-guide.md)
- [System theory](docs/system-theory.en.md)
- [Validation checklist](docs/validation-checklist.en.md)

## License

MIT. See [LICENSE](LICENSE).
