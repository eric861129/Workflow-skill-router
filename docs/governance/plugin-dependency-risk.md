# Plugin Dependency Security Decision

**Reviewed:** 2026-11-01
**Scope:** Plugin production dependencies and documentation site build dependencies

## Resolved findings

The production lockfile now uses `@modelcontextprotocol/sdk` **1.32.2**,
`@hono/node-server` **2.1.5**, `fast-uri` **3.1.9**, `proxy-addr` **2.0.8**,
`hono` **4.13.13**, `ip-address` **10.7.4**, `qs` **6.16.1**,
`body-parser` **2.4.0**, and `zod` **4.6.7**.
The compatible SDK update and transitive dependency refresh resolve all seven
affected package entries in the pre-update npm audit, including the previous
Moderate Hono exception. No cross-major override or forced downgrade was used.

On 2026-11-01, three more advisories were closed in the same lockfile:

- `zod` below 4.6.6,
  [GHSA-mrhx-c7xc-m3w5](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5)
  (High): memory exhaustion while validating oversized constrained collections.
  `zod` is bundled into `mcp/server.bundle.mjs` and validates MCP tool input,
  so the `v2.1.0` bundle (`zod` 4.1.12) is affected; `v2.1.1` ships the
  fix. That input
  comes from the local Host over stdio, not from a network listener.
- `body-parser` below 2.4.0,
  [GHSA-27r3-jxmh-p828](https://github.com/advisories/GHSA-27r3-jxmh-p828)
  (High), and `fast-uri` below 3.1.9 (four Moderate/Low advisories, including
  [GHSA-w74x-v6f9-j3xg](https://github.com/advisories/GHSA-w74x-v6f9-j3xg)).
  Both reach the lockfile only through the SDK's HTTP and JSON Schema code;
  neither is in the shipped bundle, which contains only the SDK, `zod`,
  `zod-to-json-schema`, and `@cfworker/json-schema`.

The `zod` update changes the published tool schemas in two ways. Nullable
strings are emitted as `"type": ["string", "null"]` instead of an equivalent
`anyOf`. Memory `date-time` fields now require seconds; the runtime already
writes millisecond UTC timestamps, so valid output is unchanged.

## Current audit and exposure boundary

`npm audit --omit=dev` reported **zero findings** on 2026-10-19 for this
lockfile, and a full `npm audit` reported zero findings again on 2026-11-01
after the updates above. These are dated registry results, not a claim that
future advisories cannot apply. There is no active dependency exception for
this lockfile.

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

On **2026-11-01**, the site moved to Astro **7.4.2** and Starlight **0.42.7**,
and `fast-uri` (a build-time dependency) moved to **3.1.9** for the same four
advisories as the Plugin. The parser override still holds
`postcss-selector-parser` at 7.1.6 under `postcss-nested` 6.2.0, and a full
`npm audit` reported **zero findings**.

Recheck on every site dependency change. Keep the override until the upstream
dependency chain accepts a fixed parser without it; remove it only after a
fresh install, audit, build, and browser tests pass. A future advisory still
requires a new assessment.
