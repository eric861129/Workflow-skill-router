# Plugin Dependency Security Decision

**Recorded:** 2026-07-22  
**Scope:** `plugins/workflow-skill-router` production dependency graph

## Resolved finding

The locked `fast-uri` dependency is pinned to **3.1.4**. This is outside the
known vulnerable `>=3.0.0 <=3.1.3` range for
[GHSA-v2hh-gcrm-f6hx](https://github.com/advisories/GHSA-v2hh-gcrm-f6hx).
The lockfile regression test keeps that lower boundary from silently returning.

## Temporary, upstream-tracked exception

`@modelcontextprotocol/sdk` **1.29.0** currently brings
`@hono/node-server` 1.x transitively. npm audit reports the latter as a
Moderate dependency issue for
[GHSA-frvp-7c67-39w9](https://github.com/advisories/GHSA-frvp-7c67-39w9).
The SDK's available non-forced resolver would downgrade the SDK to 1.24.3, but
that version introduces two High SDK advisories instead. This project therefore
keeps the current SDK and does not use a cross-major Hono override.

The Plugin runtime uses the MCP stdio transport only. No HTTP listener or
static-file middleware is started by the Plugin runtime. This limits exposure to
the affected `serve-static` path; it is not a substitute for an upstream fix.

## Exit criterion

Remove this exception as soon as a compatible
`@modelcontextprotocol/sdk` release resolves `@hono/node-server` to **2.0.5**
or newer. At that point, update the lockfile, rebuild the bundled MCP server,
run the Plugin and release gates, and require `npm audit --omit=dev` to report
zero High or Critical findings before a new release candidate is published.

Until then, maintainers must re-check this decision whenever the Plugin
lockfile changes or a GitHub dependency alert changes its affected range.
