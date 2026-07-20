---
title: Install the Skill-only fallback
description: Load the V2 routing contract without Plugin or MCP support.
---

## When to use Skill-only

Use the standalone SKILL when the Host cannot load Plugins/MCP or when you need instruction-only routing. It preserves envelope selection, Explicit Skill Lock, support consent, and usage disclosure. It does not provide durable resume, cross-process compare-and-swap, full drift detection, or sealed activation instrumentation.

## Install a release asset

Download [`workflow-skill-router-skill-v2.0.0-beta.2.zip`](https://github.com/eric861129/Workflow-skill-router/releases/download/v2.0.0-beta.2/workflow-skill-router-skill-v2.0.0-beta.2.zip) from the GitHub prerelease. Extract the inner `workflow-skill-router/` folder into the Codex Skills directory.

Exact archive paths:

```text
workflow-skill-router/SKILL.md
workflow-skill-router/assets/personal-routing-profile.example.json
workflow-skill-router/assets/workspace-routing-profile.example.json
workflow-skill-router/references/evaluation-boundary.md
workflow-skill-router/references/goal-protocol.md
workflow-skill-router/references/personal-routing-profiles.md
workflow-skill-router/references/routing-protocol.md
```

After extraction, `.codex/skills/workflow-skill-router/SKILL.md` must exist directly under the Skill directory.

## Install from a contributor checkout

Windows PowerShell:

```powershell
$Target = Join-Path $env:USERPROFILE ".codex\skills\workflow-skill-router"
Copy-Item -Recurse -Force "starter\v2\workflow-skill-router" $Target
Get-Content -Encoding UTF8 (Join-Path $Target "SKILL.md") | Select-Object -First 8
```

macOS or Linux:

```bash
mkdir -p "$HOME/.codex/skills"
cp -R starter/v2/workflow-skill-router "$HOME/.codex/skills/workflow-skill-router"
sed -n '1,8p' "$HOME/.codex/skills/workflow-skill-router/SKILL.md"
```

## Verify behavior

The package includes `assets/personal-routing-profile.example.json`, `assets/workspace-routing-profile.example.json`, and `references/personal-routing-profiles.md`. Put the workspace example at `.codex/workflow-skill-router.json`; do not copy the personal example there unchanged. Skill-only reads fixed local files only when the Host grants filesystem access. Without it, provide the Profile content in the conversation and treat the result as advisory.

Skill-only interprets the tree as `skill-only-fallback`. It must preserve workspace-over-personal precedence, explicit user SKILL priority, and the `intended-unverified` Runtime Capability Discovery boundary, but it cannot claim deterministic loading or durable enforcement. The `profile preview` CLI belongs to Plugin/Core mode.

Start a new Codex task and ask for a small documentation edit. The Router should declare a `single` route and planned SKILL usage. Then explicitly name one SKILL and request an additional outside support role; the Router must ask before activating that support.

Always label this mode `skill-only-fallback`. A SKILL file cannot self-assert Host exposure or `hybrid-full` conformance.
