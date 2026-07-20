# Security Policy

Workflow Skill Router V2 runs locally as a Codex Plugin, MCP server, Python router core, and optional standalone SKILL. It does not operate a hosted service, but it does process developer prompts, capability metadata, execution traces, adapter configuration, and local SQLite state. That local attack surface is part of the security model.

## Supported Versions

| Surface | Status | Security support |
| --- | --- | --- |
| V2 prerelease on `main` and the latest `v2.*` release | Active | Full security fixes |
| V1.3.1 compatibility release | Maintenance | Critical packaging or disclosure fixes only |
| Older V1 releases and source snapshots | Unsupported | Upgrade required |

The SKILL-only package has no MCP runtime or durable state guarantees. Security reports about its instructions and package contents are still in scope.

## Reporting a Vulnerability

Do not disclose a vulnerability, exploit, private prompt, credential, or state database in a public issue or Discussion.

Use GitHub **[private vulnerability reporting](https://github.com/eric861129/Workflow-skill-router/security/advisories/new)** from the repository Security tab. If that feature is unavailable, open a content-free issue asking the maintainer to enable a private contact channel; do not include technical details in that issue.

Useful private reports include:

- the affected version, installation mode, operating system, and minimal reproduction;
- whether the issue affects the Plugin runtime, MCP server, router core, SKILL-only package, release archive, or documentation site;
- sanitized logs with secrets, prompts, local paths, and personal data removed;
- expected impact and any known workaround.

## In Scope

- MCP tool schemas, command boundaries, and capability or permission reporting.
- Plugin runtime packaging, Node/Python bridge execution, and executable adapter activation.
- Local SQLite state, migrations, trace export, path handling, and unintended data disclosure.
- Evaluation adapters, bounded subprocess execution, case sealing, and evidence classification.
- Release archives, checksums, SBOM, provenance, attestations, and GitHub Actions supply chain.
- Public documentation, demo data, and repository privacy checks.

## Out of Scope

- A modified fork that bypasses V2 guards or adds untrusted executable adapters.
- General behavior of third-party models, Codex, operating systems, or tools outside this repository.
- Social engineering, denial-of-service traffic, or testing that accesses another person's machine or data.
- Claims based only on synthetic fixtures when no production path is affected.

## Local Security Expectations

- Treat local state and traces as sensitive developer data; do not attach them without redaction.
- Configure adapters with explicit executable allowlists and bounded output/time limits.
- Keep Plugin installation, SKILL selection consent, runtime permission, and production authorization as separate decisions.
- Verify release checksums and GitHub artifact attestations before trusting downloaded runtime code.

## Maintainer Response Timeline

- We aim to acknowledge a credible private report within **3 business days**.
- We aim to provide an initial triage decision within **7 business days**.
- For accepted issues, we will communicate remediation status at least every **14 days** until a fix, advisory, or documented risk decision is available.

These are response targets, not a guaranteed fix deadline. Coordinated disclosure timing will be agreed with the reporter based on severity, exploitability, and release availability.

## Supply-chain Reports

Dependency alerts, suspicious Action updates, checksum mismatches, missing SBOM entries, and unverifiable provenance are security-relevant. Report exploitable details privately; ordinary update requests may use a pull request.
