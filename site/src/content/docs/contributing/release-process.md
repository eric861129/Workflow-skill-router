---
title: Release Process
description: Build deterministic assets, review evidence, and promote channels without editing generated files.
---

## 1. Validate source

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
python -m unittest discover -s packages/router-core/tests -v
python -m unittest discover -s tests -v
python scripts/check-markdown-links.py .
```

## 2. Build deterministic assets

```powershell
$Version = (Get-Content -Raw -Encoding UTF8 release/version.json | ConvertFrom-Json).v2_version
$Output = Join-Path "dist" "release-$Version"
python -I -S -B scripts/build-release-artifacts.py --output-dir $Output --provenance-mode test --check-determinism
```

The builder reads sorted allowlists, normalizes ZIP metadata, emits checksums, SBOM, provenance, and channel documents, and rejects missing or unsafe paths. Edit source or allowlists; never patch generated archives.

The output directory may be reused only when every existing entry belongs to the current generated manifest. Any stale, unexpected, symlinked, or otherwise unmanifested path stops the build before writes. Use a version-specific directory; the builder never silently cleans mixed release generations.

## 3. Review evidence

- Contract fixtures and compatibility tests pass.
- Deterministic fixtures, the reference driver, and Pilot preparation do not constitute current behavior-model evidence.
- Behavior evidence is required only when the release makes current behavior-model claims. When required, the paired run must target the exact frozen candidate SHA, complete trusted review, and report zero hard violations before promotion.
- Public artifacts contain no raw traces, local paths, or untrusted scores.
- Plugin and Skill-only install smoke tests pass from extracted release assets.

## 4. Promote through the trusted release dispatch

Before dispatching a release, verify the live GitHub governance configuration:

```powershell
python scripts/verify-remote-governance.py --repo eric861129/Workflow-skill-router
```

This command is read-only and does not change GitHub configuration. A pass confirms the captured configuration meets the checked-in contract; it is not a live release-workflow rehearsal and does not prove the Release GitHub App bypass has been successfully exercised. A failure means the remote settings have not been proven and blocks the release checklist. Applying or changing remote rules is privileged external work; follow the maintainer guide in `docs/governance/remote-release-governance.md`.

The `Release V2` workflow runs only through a `workflow_dispatch` from the trusted default branch. It requires the exact confirmation `CREATE_V2_RELEASE`, but that string is not a publication bypass. The workflow first checks out the trusted dispatch revision and reads both `release_lifecycle` and `release_source_revision` from that revision's `release/version.json`. Only `reviewed-attested-publishable` is executable; `prepared-local-candidate` fails the resolve-source job before any preflight, tag, asset attestation, or GitHub Release publication begins. The frozen source revision must also be reachable from that same trusted checkout.

The future promotion procedure is exact:

1. **Build and freeze a candidate SHA.** Finalize source, release copies, versioned notes, allowlists, and deterministic assets, then record that candidate commit SHA.
2. **Run required evidence and review against that exact SHA.** Run required CI, extracted-asset smoke checks, governance review, and—only when current behavior-model claims require it—the paired Behavior gate against the frozen candidate, not a later branch head.
3. **Create a trusted metadata-only promotion commit.** On the default branch, update `release/version.json` so `release_source_revision` names the reviewed candidate SHA and `release_lifecycle` is `reviewed-attested-publishable`. Do not rebuild or re-evaluate the metadata commit as though it were the frozen source.
4. **Dispatch `Release V2`.** The workflow re-reads the candidate metadata, release notes, builder, and allowlists with read-only Git object inspection before it emits outputs or starts preflight.

An already-reviewed unchanged candidate can be promoted through steps 3 and 4 without rebuilding or re-evaluating it, provided every required evidence record remains bound to that exact SHA. Do not reuse evidence from another source revision or treat `CREATE_V2_RELEASE` as approval.

The three-platform preflight and release build check out that frozen revision, not the branch that dispatches the workflow. Only after they pass does the workflow mint a scoped Release GitHub App token, create or verify the annotated V2 tag with that token, prove that the remote tag resolves to the same frozen revision, attest the assets, and publish the GitHub prerelease. A retry is valid only when the existing tag already resolves to that same revision.

Do not manually push a `v2.*` tag. Protect that tag pattern so that only the scoped Release GitHub App token minted by the release job is the authorized creator; otherwise an older workflow stored at a frozen source revision could run before the trusted dispatch has completed its checks. This repository contract cannot configure the live ruleset for you, so verify that protection separately before release.

`latest-v2` may track reviewed prereleases. `latest` remains V1.3.1 until V2 GA gates pass. Tag, GitHub Release publication, channel promotion, Pages deployment, and push are separate authorized actions; local validation does none of them automatically.

## 5. Preserve V1 recovery

V1 remains recoverable from immutable `v1.3.1`. Legacy files leave the primary branch only after exact manifest review and the manual cleanup gate.
