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

## Download Skill Packages

- [Blank SKILL package](downloads/workflow-skill-router-blank.zip): a ready-to-install `workflow-skill-router/` starter for people who want to fill their own skill tree.
- [Template SKILL package](downloads/workflow-skill-router-template.zip): the blank starter plus realistic common engineering routes and copyable sample `SKILL.md` folders.

Regenerate both archives locally:

```bash
python scripts/package-downloads.py
```

The template package is built from public-safe material in this repo. It includes real skill-writing patterns and common engineering routing examples, but excludes private organization names, paths, deployment details, and internal systems.

## Practical Routing Examples

### API contract sync

```text
User: Add a new customer settings endpoint, update OpenAPI, and make the frontend client follow it.

Route: API / Contract lifecycle > Backend-to-frontend sync
Use SKILL: api-designer, openapi-contract-generation-skill, openapi-to-typescript, build-web-apps:frontend-testing-debugging
Reason: api-designer stabilizes the endpoint; openapi-contract-generation-skill manages schema diff and contract generation; openapi-to-typescript updates the client types; frontend-testing-debugging verifies rendered consumption.
```

### Database migration with performance risk

```text
User: Add audit tables for account changes and make sure the admin query does not become slow.

Route: Database / Schema and performance > Migration plus query review
Use SKILL: database-schema-designer, sql-pro, database-optimizer, qa-test-planner
Reason: database-schema-designer owns migration shape; sql-pro reviews SQL correctness; database-optimizer checks query plans; qa-test-planner defines regression coverage.
```

### Browser-only frontend bug

```text
User: A customer portal form only fails after a browser refresh. Reproduce it and add a regression check.

Route: Frontend / Debugging > Browser reproduction
Use SKILL: build-web-apps:frontend-testing-debugging, browser:control-in-app-browser, playwright, systematic-debugging
Reason: frontend-testing-debugging maps UI symptoms to source; browser reproduces real runtime behavior; playwright captures the regression; systematic-debugging keeps the investigation causal.
```

### PR review and CI repair

```text
User: Review this auth PR, address comments, and fix the failing checks.

Route: GitHub / Review and CI > Security-sensitive PR
Use SKILL: github:github, receiving-code-review, codex-security:security-diff-scan, github:gh-fix-ci
Reason: github:github orients the PR; receiving-code-review handles comments; security-diff-scan checks auth and data exposure; gh-fix-ci diagnoses failing checks.
```

### Local development stack

```text
User: Create a Docker Compose setup with PostgreSQL, Redis, and MailDev for local development.

Route: DevOps / Local development > Repeatable service stack
Use SKILL: docker-compose-local-dev-skill, devops-engineer, systematic-debugging
Reason: docker-compose-local-dev-skill owns local service ergonomics; devops-engineer checks infra tradeoffs; systematic-debugging helps when startup order or health checks fail.
```

## What Is Included

- `starter/workflow-skill-router/`: a Codex-ready starter skill with an agent-agnostic routing contract.
- `examples/`: example routers, from minimal generic routing to realistic engineering workflows.
- `sample-skills/`: copyable public `SKILL.md` examples that pair with the common engineering routes.
- `downloads/`: generated blank and template SKILL zip packages.
- `recipes/`: short practical patterns for API contract sync, frontend debugging, PR/CI work, documentation, and connector-heavy workflows.
- `scripts/validate-router.py`: dependency-free validation for router structure, route size, Primary markers, and privacy leaks.
- `scripts/package-downloads.py`: dependency-free packaging for downloadable SKILL archives.
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
