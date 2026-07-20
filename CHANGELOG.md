# Changelog

All notable changes to Workflow Skill Router are documented here.

## Unreleased

### Fixed

- Prioritized immutable release installs for normal Plugin and Skill-only users, while keeping contributor checkout instructions separate.
- Aligned public beta copy with the released 12-tool, four-local-ready Runtime profile and reviewed 36-attempt evaluation evidence.
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
