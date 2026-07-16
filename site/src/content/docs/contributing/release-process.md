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
python scripts/build-release-artifacts.py --output-dir dist/release --provenance-mode test --check-determinism
```

The builder reads sorted allowlists, normalizes ZIP metadata, emits checksums, SBOM, provenance, and channel documents, and rejects missing or unsafe paths. Edit source or allowlists; never patch generated archives.

## 3. Review evidence

- Contract fixtures and compatibility tests pass.
- Corrected Behavior evidence is complete, paired, and reviewed.
- Hard violations are zero.
- Public artifacts contain no raw traces, local paths, or untrusted scores.
- Plugin and Skill-only install smoke tests pass from extracted release assets.

## 4. Promote deliberately

`latest-v2` may track reviewed prereleases. `latest` remains V1.3.1 until V2 GA gates pass. Tag, GitHub Release publication, channel promotion, Pages deployment, and push are separate authorized actions; local validation does none of them automatically.

## 5. Preserve V1 recovery

V1 remains recoverable from immutable `v1.3.1`. Legacy files leave the primary branch only after exact manifest review and the manual cleanup gate.
