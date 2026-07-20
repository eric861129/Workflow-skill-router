---
title: Install the Skill-only fallback
description: Load the V2 routing contract without Plugin or MCP support.
---

## When to use Skill-only

Use the standalone SKILL when the Host cannot load Plugins/MCP or when you need instruction-only routing. It preserves envelope selection, Explicit Skill Lock, support consent, and usage disclosure. It does not provide durable resume, cross-process compare-and-swap, full drift detection, or sealed activation instrumentation.

## Install a release asset

Download [`workflow-skill-router-skill-v2.0.0-beta.1.zip`](https://github.com/eric861129/Workflow-skill-router/releases/download/v2.0.0-beta.1/workflow-skill-router-skill-v2.0.0-beta.1.zip) from the published GitHub prerelease. Extract the inner `workflow-skill-router/` folder into the Codex Skills directory.

Exact archive paths:

```text
workflow-skill-router/SKILL.md
workflow-skill-router/references/evaluation-boundary.md
workflow-skill-router/references/goal-protocol.md
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

Start a new Codex task and ask for a small documentation edit. The Router should declare a `single` route and planned SKILL usage. Then explicitly name one SKILL and request an additional outside support role; the Router must ask before activating that support.

Always label this mode `skill-only-fallback`. A SKILL file cannot self-assert Host exposure or `hybrid-full` conformance.
