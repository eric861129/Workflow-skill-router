---
title: Troubleshooting
description: Fix common install, PowerShell, Python, zip extraction, and validator issues.
---

Use this guide when the quickstart command does not produce:

```text
OK: workflow-skill-router passed validation
```

## Install path

Codex skills usually live under:

| Platform | Expected folder |
| --- | --- |
| Windows | `%USERPROFILE%\.codex\skills\workflow-skill-router` |
| macOS / Linux | `$HOME/.codex/skills/workflow-skill-router` |

Windows PowerShell check:

```powershell
$Router = Join-Path $env:USERPROFILE ".codex\skills\workflow-skill-router"
Test-Path $Router
Get-ChildItem $Router
```

macOS or Linux check:

```bash
test -d "$HOME/.codex/skills/workflow-skill-router"
ls "$HOME/.codex/skills/workflow-skill-router"
```

The folder should contain `SKILL.md`, `agents/`, and `references/`.

## PowerShell issues

### `python` is not recognized

Install Python 3, then open a new terminal and run:

```powershell
python --version
```

If Windows opens the Microsoft Store instead, install Python from python.org or disable the Python app execution alias in Windows settings.

### `Invoke-WebRequest` fails

Some corporate networks block direct GitHub raw downloads. Download the zip from the [GitHub releases page](https://github.com/eric861129/Workflow-skill-router/releases) in a browser, then run:

```powershell
$Skills = Join-Path $env:USERPROFILE ".codex\skills"
New-Item -ItemType Directory -Force -Path $Skills | Out-Null
Expand-Archive -Force -Path "$env:USERPROFILE\Downloads\workflow-skill-router-blank.zip" -DestinationPath $Skills
```

### Chinese text looks broken in terminal output

That is often a console display problem, not file corruption. Read the file with explicit UTF-8:

```powershell
Get-Content -Encoding UTF8 "$env:USERPROFILE\.codex\skills\workflow-skill-router\SKILL.md"
```

If the file itself contains Unicode replacement-character markers such as `U+FFFD`, download the package again.

## Zip extraction issues

After extraction, the path should be:

```text
.codex/
  skills/
    workflow-skill-router/
      SKILL.md
```

If you see this instead:

```text
.codex/
  skills/
    workflow-skill-router-blank/
      workflow-skill-router/
        SKILL.md
```

Move the inner `workflow-skill-router/` folder into `.codex/skills/`, then validate again.

## Validator issues

### `Missing SKILL.md`

You are validating the wrong folder. Pass the folder that directly contains `SKILL.md`:

```powershell
python $Validator (Join-Path $env:USERPROFILE ".codex\skills\workflow-skill-router")
```

### `Missing references/skill-tree.md`

The router folder is incomplete. Re-extract `workflow-skill-router-blank.zip` and confirm the `references/` folder exists.

### `Missing references/routing-rules.md`

The router cannot explain conflict handling yet. Restore `references/routing-rules.md` from the blank package, then adapt it.

### `Route selects too many skills`

Each route should have one primary skill and at most three supporting skills. If the work needs more than four skills, split it into stages.

### Placeholder text remains

Replace template placeholders with your real skill names, route categories, and conflict rules. The validator expects the router to be adapted before publishing.

### Public-readiness audit fails

`validate-router.py` checks router structure. `audit-public-readiness.py` checks the public repository surface: docs, downloads, manifests, examples, and stale assets. A local private router can be structurally valid while still failing public-readiness checks because it contains private names or paths.

## Still stuck

Open an issue with:

- Your operating system
- The exact command you ran
- The exact validator output
- The extracted folder tree around `workflow-skill-router/`

Do not paste private project names, customer names, hostnames, tokens, or internal repository paths.
