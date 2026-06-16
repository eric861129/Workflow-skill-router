# Dependency Governance

Workflow Skill Router ships Markdown, starter templates, Python validation scripts, release archives, and a static documentation site. It does not ship a Node.js runtime to end users.

## Runtime Dependency Policy

Release downloads are validated with Python standard-library scripts and do not require the `site/` Node dependency tree.

Before a public release, the runtime dependency audit must pass:

```bash
cd site
npm audit --omit=dev --audit-level=moderate
```

This command should report no moderate, high, or critical production dependency vulnerabilities.

## Dev Tooling Advisory

The documentation site uses Lighthouse as a local quality gate. The current Lighthouse 13 dependency chain may report a moderate advisory through Sentry and OpenTelemetry packages in `npm audit` when dev dependencies are included.

This risk is monitored rather than force-fixed in `v1.3.1` because:

- Lighthouse is a development and CI audit tool, not code served by the static site.
- The generated GitHub Pages output does not bundle the Lighthouse dependency tree.
- `npm audit fix --force` recommends a major Lighthouse downgrade, which would reduce confidence in the existing Lighthouse gate.

The maintainer will revisit this when Lighthouse or its transitive dependencies publish a non-breaking fix. Dependabot remains enabled for routine dependency update review.

## Release Gate

Public releases should run:

```bash
python scripts/audit-public-readiness.py .
python scripts/check-markdown-links.py .
cd site
npm audit --omit=dev --audit-level=moderate
npm run build
npm run test:site:smoke
npm run test:site:visual
npm run audit:lighthouse
```
