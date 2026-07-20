---
title: Install modes and release assets
description: Choose the V2 runtime boundary that matches your Codex Host, then install or inspect the correct package.
---

## Choose your V2 install mode

Workflow Skill Router has one policy core and several runtime boundaries. Choose by the authority your Host can actually provide—not by the largest feature list.

<div class="wsr-download-picker" aria-label="V2 install mode comparison">
  <article class="wsr-download-card wsr-download-card-featured">
    <div>
      <span class="wsr-download-kicker">Primary install</span>
      <h3>Bundled Plugin + MCP</h3>
      <p>Use the Codex Plugin when you want durable local R0 planning, runtime readiness, typed MCP results, and fail-closed handoff to stronger Host capabilities.</p>
    </div>
    <dl class="wsr-download-specs">
      <div><dt>Local-ready</dt><dd><code>plan_work</code>, <code>propose_support_consent</code>, <code>transition_support_consent</code>, and <code>get_router_status</code></dd></div>
      <div><dt>Runtime label</dt><dd><code>bundled-local-r0</code></dd></div>
      <div><dt>Requirements</dt><dd>Codex Plugin/MCP support, Python 3.11+, Node.js 24+</dd></div>
    </dl>
    <a class="wsr-download-button" href="/Workflow-skill-router/guides/install-plugin/">Install Plugin + MCP</a>
  </article>

  <article class="wsr-download-card">
    <div>
      <span class="wsr-download-kicker">Host integration</span>
      <h3>Verified-host integration</h3>
      <p>Add scheduler, compare-and-swap state, protected route validation, gates, and Goal progression only through Host-verified ports and receipts.</p>
    </div>
    <dl class="wsr-download-specs">
      <div><dt>Best for</dt><dd>Codex or platform integrators</dd></div>
      <div><dt>Authority</dt><dd>Host-owned; never inferred from local files</dd></div>
      <div><dt>Fallback</dt><dd>Typed <code>capability-unavailable</code></dd></div>
    </dl>
    <a class="wsr-download-button wsr-download-button-secondary" href="/Workflow-skill-router/concepts/managed-goals/">Inspect the Host boundary</a>
  </article>

  <article class="wsr-download-card">
    <div>
      <span class="wsr-download-kicker">Authorized evaluation</span>
      <h3>Configured evaluation adapter</h3>
      <p>Run fresh Behavior or Outcome attempts through a server-configured executable. Model input cannot choose the executable, quota, or publication status.</p>
    </div>
    <dl class="wsr-download-specs">
      <div><dt>Best for</dt><dd>Maintainers running reviewed benchmarks</dd></div>
      <div><dt>Requires</dt><dd>Trusted adapter configuration and explicit quota authorization</dd></div>
      <div><dt>Publication</dt><dd>Remains review-required until attested</dd></div>
    </dl>
    <a class="wsr-download-button wsr-download-button-secondary" href="/Workflow-skill-router/concepts/evaluation-evidence/">Read the evidence contract</a>
  </article>

  <article class="wsr-download-card">
    <div>
      <span class="wsr-download-kicker">Instruction-only fallback</span>
      <h3>Skill-only</h3>
      <p>Load the V2 routing instructions when the Host cannot run Plugins or MCP. Explicit Skill Lock and usage disclosure remain; durable runtime guarantees do not.</p>
    </div>
    <dl class="wsr-download-specs">
      <div><dt>Runtime label</dt><dd><code>skill-only-fallback</code></dd></div>
      <div><dt>Includes</dt><dd><code>SKILL.md</code>, <code>references/evaluation-boundary.md</code>, <code>references/goal-protocol.md</code>, and <code>references/routing-protocol.md</code></dd></div>
      <div><dt>Excludes</dt><dd>Durable resume, cross-process CAS, sealed instrumentation</dd></div>
    </dl>
    <a class="wsr-download-button wsr-download-button-secondary" href="/Workflow-skill-router/guides/install-skill/">Use Skill only</a>
  </article>

  <article class="wsr-download-card">
    <div>
      <span class="wsr-download-kicker">Contributors and integrators</span>
      <h3>Source checkout</h3>
      <p>Use source when changing the policy core, transport, deterministic builders, documentation, or a Host adapter. Generated release files are never edited by hand.</p>
    </div>
    <dl class="wsr-download-specs">
      <div><dt>Primary source</dt><dd>Git repository and pinned dependency locks</dd></div>
      <div><dt>Build output</dt><dd>Ignored <code>dist/release/</code></dd></div>
      <div><dt>Verification</dt><dd>Core, MCP, docs, site, install, SBOM, provenance</dd></div>
    </dl>
    <a class="wsr-download-button wsr-download-button-secondary" href="https://github.com/eric861129/Workflow-skill-router">View source on GitHub</a>
  </article>
</div>

## Marketplace install

For normal installations, pin the published immutable marketplace snapshot:

```powershell
codex plugin marketplace add eric861129/Workflow-skill-router --ref v2.0.0-beta.1
codex plugin add workflow-skill-router@workflow-skill-router
codex plugin list
```

Contributors who are changing the Router can install from a checkout instead:

```powershell
git clone https://github.com/eric861129/Workflow-skill-router.git
Set-Location Workflow-skill-router
codex plugin marketplace add .
codex plugin add workflow-skill-router@workflow-skill-router
```

## Offline inspection assets

The `v2.0.0-beta.1` GitHub prerelease is available now. These immutable release assets are safer to inspect or install than mutable `raw/main/downloads` files.

- [Plugin ZIP: `workflow-skill-router-plugin-v2.0.0-beta.1.zip`](https://github.com/eric861129/Workflow-skill-router/releases/download/v2.0.0-beta.1/workflow-skill-router-plugin-v2.0.0-beta.1.zip)
- [Skill-only ZIP: `workflow-skill-router-skill-v2.0.0-beta.1.zip`](https://github.com/eric861129/Workflow-skill-router/releases/download/v2.0.0-beta.1/workflow-skill-router-skill-v2.0.0-beta.1.zip)
- [All releases](https://github.com/eric861129/Workflow-skill-router/releases)

The ZIPs are for offline inspection and fallback installation. Verify published checksums, SBOM, and provenance before use. Do not treat a local prerelease build as a published asset.

## Verify after installation

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz doctor
```

Expected bundled result: `runtime_profile` is `bundled-local-r0`, telemetry is disabled, and `plan_work`, `propose_support_consent`, `transition_support_consent`, and `get_router_status` are local-ready. Continue with the [V2 Quickstart](/Workflow-skill-router/guides/quickstart/).
