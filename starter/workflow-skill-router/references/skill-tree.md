# Workflow Skill Tree

Use this tree to choose a small skill set.

## Placeholder Policy

**PLACEHOLDER ONLY:** skill names that start with `example-` or use generic names such as `backend-developer`, `browser`, `documentation-writer`, or `release-checklist` are intentionally fake starter placeholders. Replace them with the exact skill names displayed by your own agent.

If you want a public-safe working catalog instead of a blank starter, use the template-aligned example in `examples/template-skill-catalog/references/skill-tree.md`.

Format:

```text
Task nature -> Work stage -> Technical domain -> Primary + Supporting skills
```

Each route must have one Primary skill and zero to three Supporting skills.

## Skill Inventory Summary

Fill this section after inventorying the skills available to your agent.

| Source | Skills | Role | Routing notes |
| --- | --- | --- | --- |
| Local custom | `example-backend-skill`, `example-frontend-skill` | Repo and implementation judgment | Placeholder names. Replace with your actual local skills. |
| Connector/plugin | `example-github`, `example-browser` | Live systems and rendered/runtime evidence | Placeholder names. Replace with your actual connector/plugin skills. |
| Meta workflow | `example-planning`, `example-debugging` | Process control | Placeholder names. Replace with your actual planning or debugging workflow skills. |

## Requirements / Planning

- Requirements / Clarify / Complex feature: Primary: `requirements-clarity`; Supporting: `planning-workflow`
- Planning / Implementation plan / Multi-stage work: Primary: `implementation-planning`; Supporting: `architecture-review`

## Architecture / API / Backend

- Architecture / System design / High-level decisions: Primary: `architecture-designer`; Supporting: `diagramming`, `cloud-architecture`
- API / Contract design / REST or GraphQL: Primary: `api-designer`; Supporting: `schema-generation`, `documentation`
- Backend / Implementation / Service code: Primary: `backend-developer`; Supporting: `database-design`, `test-planning`

## Frontend / Web / UI

- Frontend / New page or app / Web UI: Primary: `frontend-builder`; Supporting: `ui-design`, `browser`
- Frontend / Debugging / Browser reproduction: Primary: `frontend-debugging`; Supporting: `browser`, `systematic-debugging`

## Documentation / Knowledge

- Documentation / Technical guide / Readability and structure: Primary: `documentation-writer`; Supporting: `diagramming`, `code-documentation`
- Documentation / File artifact / Document, spreadsheet, deck, or PDF: Primary: `file-format-tool`; Supporting: `documentation-writer`

## Review / CI / Release

- Review / Pull request feedback / Code review: Primary: `code-review`; Supporting: `github-connector`
- CI / Failed build / Pipeline diagnosis: Primary: `ci-debugging`; Supporting: `github-connector`, `devops`
- Release / Readiness / Final verification: Primary: `release-checklist`; Supporting: `test-planning`, `git-workflow`

## Connectors / External Systems

- Connector / GitHub / PRs, issues, actions: Primary: `github-connector`; Supporting: `code-review`, `ci-debugging`
- Connector / Browser / Rendered local app: Primary: `browser`; Supporting: `frontend-debugging`, `systematic-debugging`
- Connector / Workspace files / Docs, sheets, slides: Primary: `workspace-connector`; Supporting: `file-format-tool`
