# Plugin Dependency Security Decision

**Reviewed:** 2026-10-19
**Scope:** `plugins/workflow-skill-router` production dependency graph

## Resolved findings

The production lockfile now uses `@modelcontextprotocol/sdk` **1.32.1**,
`@hono/node-server` **2.1.5**, `fast-uri` **3.1.8**, `proxy-addr` **2.0.8**,
`hono` **4.13.13**, `ip-address` **10.7.4**, and `qs` **6.16.1**.
The compatible SDK update and transitive dependency refresh resolve all seven
affected package entries in the pre-update npm audit, including the previous
Moderate Hono exception. No cross-major override or forced downgrade was used.

## Current audit and exposure boundary

`npm audit --omit=dev` reported **zero findings** on 2026-10-19 for this
lockfile. This is a dated registry result, not a claim that future advisories
cannot apply. There is no active dependency exception for this lockfile.

The Plugin runtime uses the MCP stdio transport only. No HTTP listener or
static-file middleware is started by the Plugin runtime. Dependency findings
must still be reviewed even when their reported HTTP path is not used here.

## Regression and release gate

The lockfile regression test checks the reviewed minimum fixed versions.
Whenever dependencies change, rebuild the bundled MCP server, run the Plugin
and release gates, and rerun `npm audit --omit=dev`. A new release candidate
must have zero High or Critical findings; any lower-severity exception requires
a new explicit, dated exposure assessment and exit criterion.

Maintainers must re-check this decision whenever the Plugin
lockfile changes or a GitHub dependency alert changes its affected range.

## Documentation site dependency review

The separate `site/` workspace was refreshed within its declared compatible
ranges on 2026-10-19: Astro **7.4.0**, Starlight **0.41.11**, and Sharp
**0.35.5**. The Astro manifest floor is now **7.2.8**, the fix for
[GHSA-26w7-cxv4-gfx2](https://github.com/advisories/GHSA-26w7-cxv4-gfx2).
The site audit fell from 20 affected entries (including 8 High and 1 Critical)
to **10 Moderate, zero High, zero Critical**.

The remaining entries are one transitive advisory propagated through
Starlight / Expressive Code / `postcss-nested` 6.2.0 /
`postcss-selector-parser` 6.1.4:
[GHSA-rj75-hqrm-r3gf](https://github.com/advisories/GHSA-rj75-hqrm-r3gf).
It concerns CPU exhaustion during CSS selector parsing. This is part of the
documentation build dependency graph; the count does not mean ten distinct
reachable runtime flaws in the static site.

The current upstream Expressive Code package still requires `postcss-nested`
6.x. npm's proposed Starlight downgrade to 0.21.5 is not a compatible repair;
no forced downgrade or unverified cross-major parser override is applied.
Recheck on every site dependency change. Exit criterion: the supported
upstream chain resolves the parser to **7.1.6** or newer, then rebuild the site,
run browser smoke tests, and confirm the advisory is absent from `npm audit`.
