# Plugin Dependency Security Decision

**Reviewed:** 2026-10-20
**Scope:** Plugin production dependencies and documentation site build dependencies

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

Those ten entries were one transitive advisory propagated through
Starlight / Expressive Code / `postcss-nested` 6.2.0 /
`postcss-selector-parser` 6.1.4:
[GHSA-rj75-hqrm-r3gf](https://github.com/advisories/GHSA-rj75-hqrm-r3gf).
It concerns CPU exhaustion during CSS selector parsing. This is part of the
documentation build dependency graph; the count does not mean ten distinct
reachable runtime flaws in the static site.

On **2026-10-20**, the parser was updated to **7.1.6** with an npm override
scoped to `postcss-nested`. Expressive Code still requires `postcss-nested`
6.x, whose parser range excludes the fix. Dependabot PR #107's Starlight
0.42.6 update also retained parser 6.1.4 and the same ten audit entries, so
that upgrade alone did not resolve the advisory. The targeted repair keeps
Starlight 0.41.11 and all other locked package versions unchanged.

The parser override crosses a major version and was checked with a clean
`npm ci`, a 68-page production build, and **34 passing browser smoke and
visual tests**. All seven generated CSS files retained identical paths and
SHA-256 hashes compared with the previous lockfile. A full `npm audit`
reported **zero findings**. The lockfile regression test rejects parser
versions below 7.1.6 at every installation depth; the dated site exception
is now resolved.

Recheck on every site dependency change. Keep the override until the upstream
dependency chain accepts a fixed parser without it; remove it only after a
fresh install, audit, build, and browser tests pass. A future advisory still
requires a new assessment.
