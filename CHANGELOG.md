# Changelog

All notable changes to Workflow Skill Router are documented here.

## Unreleased

## 2.0.0-beta.5 (prepared, not yet published)

### Added

- Added the Router-owned Local Work Loop: `get_next_work`, `record_work_event`, and `evaluate_gate` are available only as bounded `conditional-local` operations for a validated Router-owned graph.
- Added the verified Host Integration Kit, a reference adapter, capability manifest, and conformance suite without granting bundled local runtime Host authority.
- Added frozen beta.5 Pilot protocols for twenty real local tasks, verified-Host evidence, and the semantic-recommender decision gate.

### Changed

- The prepared product surface now identifies `2.0.0-beta.5` while `latest` remains pinned to V1.3.1 and every public installation link remains on published beta.3.
- The candidate reports **4 always local-ready + 3 Router-owned conditional-local** operations, never `7/12 local-ready`; Explicit Skill Lock, scoped consent, Native Goal protection, and fail-closed authority separation remain unchanged.

### Evidence

- The reference driver and deterministic conformance suites do not prove real-model behavior, Skill activation, task outcome, a completed Pilot, or a verified Host deployment.
- No beta.5 live model evaluation, real Pilot result, maintainer attestation, external prerelease, tag, or channel update is claimed by this prepared candidate.

## 2.0.0-beta.4 (prepared, not yet published)

### Added

- Added deterministic no-hint classification evidence for Single, Phased, and Managed Goal work plus public-safe `profile preview --explain` miss evidence.
- Added sealed Contract 2.3.0 dimensions for envelope source, classification reasons, local authority, Profile explain, and unnecessary consent.
- Added hard-violation detection for native Goal mutation by local output, false local activation claims, and direct semantic-candidate persistence.
- Added mandatory bounded evidence, a shared public non-oracle reason-code vocabulary, and attestation-blocking failures for missing or invalid evidence.

### Changed

- Bound every evaluation attempt nonce to the tool inventory, instruction digest, public case payload, configured model or reference-driver version, and an irreversible scoring-spec digest covering the private oracle and scoring policy.
- Kept the full suite at 13 cases and beta smoke at six cases with one two-turn consent case; `profile-explain-miss` replaces `evaluation-manual-required` to preserve the frozen 36-attempt / 42-turn beta budget.
- Prepared local Plugin and Skill-only beta.4 metadata while keeping `latest` on V1.3.1 and the published V2 installation links on beta.3 until review and publication occur.

### Evidence

- Contract 2.3.0 reference-driver results are deterministic Tier 0 Contract evidence only. They do not prove real-model behavior, Skill activation, or task Outcome.
- No beta.4 live model evaluation or external prerelease publication is claimed by this source preparation.

## 2.0.0-beta.3

### Security

- Eliminated the privileged `workflow_run` checkout from Pages deployment; the trusted `main` revision now deploys only after deterministic artifacts, core contracts, and site visual gates pass in the same workflow.
- Updated Lighthouse's scoped Sentry dependency to the patched OpenTelemetry 2.x line and added a lockfile regression test for `GHSA-8988-4f7v-96qf`.

### Changed

- Published a new immutable prerelease snapshot so source, Plugin, Skill-only, checksums, SBOM, and `latest-v2` all describe the security-hardened revision.
- Preserved V1.3.1 on stable `latest` and retained beta.1 model evaluation as historical evidence; beta.3 does not claim a new behavior evaluation.

## 2.0.0-beta.2

### Added

- Added strict Personal and Workspace Routing Profiles so users can own repeatable Skill Trees without forking the Plugin or bypassing Runtime Capability Discovery.
- Added packaged personal and workspace examples, deterministic validate/install/list/preview commands, workspace trust-root binding, and current-Phase-only route selection.

### Fixed

- Closed MCP workspace junction and symlink escapes by authorizing canonical existing directories instead of lexical paths.
- Prevented linked Profile directories and linked install sources from writing outside the Router data directory.
- Preserved beta.1 explicit Skill intent and idempotent replay when migration `0005` adds Profile planning fields.
- Separated beta.1 real-model evidence from beta.2 Profile claims across the homepage, documentation, release notes, and Blog.
- Aligned public beta copy with the released 12-tool, four-local-ready Runtime profile and reviewed 36-attempt evaluation evidence.

### Changed

- Clarified that Skill-only Profile loading requires Host filesystem access and remains advisory `skill-only-fallback`.
- Kept the public MCP surface at twelve tools and the bundled local-ready surface at four tools.
- Prioritized immutable release installs for normal Plugin and Skill-only users while keeping contributor checkout instructions separate.
- Pointed Plugin metadata directly at the canonical documentation URL and clarified the beta roadmap status.

## 2.0.0-beta.1

### Added

- Rebuilt the project around the V2 hybrid architecture: deterministic Router Core, installable Plugin/MCP runtime, and a standalone SKILL-only package.
- Added runtime capability discovery, task-size-aware phase routing, explicit user-specified SKILL consent rules, durable local state, and inspectable execution traces.
- Added sealed model-evaluation adapters, reproducible benchmark manifests, evidence classifications, and a review gate that separates fixtures from real model behavior.
- Added a bilingual V2-first documentation site, interactive trace demo, Plugin and SKILL-only installation guides, and automated accessibility, visual, smoke, and Lighthouse checks.
- Added V2 community governance, focused issue forms, CodeQL, OpenSSF Scorecard, immutable Action pins, deterministic release artifacts, SBOM output, and GitHub build-provenance attestations.

### Changed

- CI now validates deterministic local contracts without Codex credentials or live model quota.
- V1 remains a pinned compatibility surface; V1 gallery, evaluator, metrics, and starter-generation tooling are no longer accepted as V2 public proof.
- Release automation accepts only full `v2.*` version tags and builds every published artifact from the tagged source revision.
- Removed the reviewed 225-file V1, generated-download, duplicate-media, sample-catalog, and obsolete evaluator surface while preserving immutable V1.3.1 recovery.
- Removed the separately reviewed 27-file residual set covering superseded issue forms, migrated internal plans, V1 CLI goldens, retired generators, and the orphaned Route Gallery component.

## v1.3.1

- Removed hard-coded private markers from public validator source and added environment-based marker injection for local/private scans.
- Made public-readiness scan validator source and added self-tests for validator self-scan coverage.
- Added a standard-library Markdown/MDX local link checker and wired it into CI.
- Replaced heavy showcase GIF embedding with MP4/WebM demo assets, a poster image, and GIF fallback links.
- Regenerated social preview assets for the documentation site and GitHub repository settings.
- Added dependency governance notes for the monitored Lighthouse development-tooling audit advisory.
- Added v1.3.1 launch checklist and ready-to-post community announcement drafts.

## v1.3.0

- Added a public-safe Routing Gallery generated from root-level `route-cases/*.json`.
- Added route case validation and generated gallery/evaluation data.
- Expanded the routing benchmark from 30 to 80 scenarios across API, frontend, database, docs, release, connector, simple task, and anti-over-routing boundaries.
- Added routing metrics history and a documentation site trend page for release-level metrics.
- Added Playwright site smoke tests and key visual regression snapshots.
- Added disabled-by-default Plausible-compatible analytics hooks and transparent README CTA redirect pages.
- Added route case contribution guidance, an issue template, and monthly release cadence documentation.
- Updated README proof, package CTA links, roadmap, CI validation, and release documentation for the v1.3.0 quality gate.

## v1.2.0

- Added a complete Blank Router walkthrough from install to validation.
- Added Troubleshooting and FAQ coverage for install paths, PowerShell, Python, zip extraction, validator errors, and public-readiness checks.
- Added Claude, Cursor, and Gemini adapter notes for non-Codex instruction surfaces.
- Added a 60-second demo GIF and connected it from README and the documentation site showcase.
- Calibrated the public onboarding links across README, Quickstart, and the Starlight sidebar.

## v1.1.2

- Synced the patch release target with the latest `main` branch.
- Added README package selector guidance for Blank Router, Reference Template, and Full source archive.
- Added release asset smoke testing for downloadable zip packages and manifest contents.
- Added the documentation site build to the main validation workflow.

## v1.1.1

- Added public launch showcase material for before/after routing examples.
- Added anti-over-routing guidance for keeping routes small and reviewable.
- Added forward-test records for real agent routing usage.
- Completed sample skill metadata coverage to reduce scanner warnings.
- Improved release packaging with clearer download comparison and release-note workflow.
- Added a clean installable Reference Template package.
- Updated the documentation site dependency baseline.

## v1.1.0

See the immutable V1.1.0 tag and GitHub Release for the original notes.

- Added routing evaluation scenarios, predictions, and generated reports.
- Added dependency-free skill inventory scanner.
- Added CI quality gates for validation, scanning, routing evaluation, and unit tests.

## v1.0.0

See the immutable V1.0.0 tag and GitHub Release for the original notes.

- Introduced the Codex-ready Workflow Skill Router starter.
- Added the template skill catalog and downloadable starter packages.
- Added English and Traditional Chinese documentation site.
