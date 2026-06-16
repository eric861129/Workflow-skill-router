# Security Policy

Workflow Skill Router is a documentation, template, and validation-tooling project. It does not run a hosted service or collect user data.

## Supported Versions

Security fixes apply to the latest commit on `main` and the latest published GitHub release.

## Reporting A Vulnerability

Please do not open a public issue for sensitive reports.

Report suspected vulnerabilities by using GitHub private vulnerability reporting if it is available for this repository. If private reporting is not available, open a minimal public issue that says you need a private security contact, without including exploit details.

Useful reports include:

- A private skill, path, organization name, credential, or deployment detail accidentally included in a public package.
- A validator bypass that allows obvious private strings to pass.
- A release asset or download package that does not match the documented public-safe manifest.
- A site or workflow configuration issue that could mislead users about what they are downloading.

## Scope

In scope:

- Repository files.
- Download packages published from this repository.
- Validator and packaging scripts.
- GitHub Pages documentation output.

Out of scope:

- Third-party AI agent behavior after users modify the starter.
- User-created private overlays.
- Vulnerabilities in unrelated local Codex skill folders outside this repository.

## Dependency Governance

The public release packages do not ship the documentation site's Node.js development dependency tree. Production/runtime dependency audits for the static site should pass with:

```bash
cd site
npm audit --omit=dev --audit-level=moderate
```

Development-only audit findings, including the monitored Lighthouse tooling advisory, are tracked in [docs/dependency-governance.md](docs/dependency-governance.md).

## Maintainer Response

The maintainer will review credible reports, remove exposed private content if needed, and publish a fix or advisory when the issue affects released assets.
