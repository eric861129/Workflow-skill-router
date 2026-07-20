# ADR 0002: Release assets outside Git

## Status

Accepted on 2026-07-17.

## Context

Tracked ZIP files, checksums, SBOMs, and media made the repository large and allowed generated output to drift away from source. A trustworthy public beta needs packages that can be reproduced from one reviewed revision and attributed to that revision.

Codex Git marketplace installation still requires a minimal bundled MCP module and Python runtime in the Plugin source. Those two runtime outputs are therefore retained, allowlisted, and checked for reproducibility; general release archives do not share that exception.

## Decision

- Plugin and SKILL release archives, checksums, SPDX SBOMs, manifests, and provenance are built from source into the ignored `dist/release` directory.
- Published packages belong in GitHub Release Assets and are rebuilt from the exact immutable tag by the release workflow. The workflow also produces build provenance and attestation.
- Archive contents come from sorted explicit allowlists. Builds use fixed metadata, verify determinism, and bind publishable provenance to the source revision and source tree.
- `latest` and `latest-v1` remain pinned to V1.3.1 during beta; generated `latest-v2` metadata identifies the current V2 prerelease (`2.0.0-beta.2` for this release) without promoting the stable channel.
- Product SemVer and persisted schema versions are separate contracts. A beta product release does not silently change schema identifiers or migrate stored state; that requires its own compatibility decision and migration.

## Consequences

- The Git tree contains source and only the two marketplace-required reproducible runtime builds, not downloadable release packages.
- Release consumers can verify checksums, SBOM contents, provenance, and attestation against one source revision.
- Maintainers must build final artifacts only after the release-candidate commit is clean. A failed post-commit gate requires a new reviewed commit and a fresh build.
- Local test artifacts are non-publishable and cannot be presented as GitHub release provenance.
