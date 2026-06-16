---
title: Privacy-first Analytics
description: How the documentation site tracks conversion without tracking GitHub README views directly.
---

Workflow Skill Router uses a Plausible-compatible analytics hook that is disabled by default. When no public environment variables are set, the site builds normally and no analytics script is loaded.

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `PUBLIC_ANALYTICS_PROVIDER` | Yes | Set to `plausible` to enable analytics. |
| `PUBLIC_PLAUSIBLE_DOMAIN` | Yes | Domain configured in Plausible or a compatible service. |
| `PUBLIC_PLAUSIBLE_SCRIPT_URL` | No | Override script URL. Defaults to Plausible outbound-link and file-download tracking. |

## What can be measured

- site page views,
- outbound clicks from the documentation site,
- file download events from the documentation site,
- README CTA click-throughs that pass through `/go/readme/.../`,
- GitHub Release asset download counts from GitHub itself.

## What cannot be measured

GitHub README views cannot load project analytics scripts. The README therefore links major CTAs through transparent `/go/readme/.../` landing pages. Those pages can measure click-through intent, then redirect to GitHub or the release asset.

No short-link service is used, and each redirect page includes a manual fallback link.
