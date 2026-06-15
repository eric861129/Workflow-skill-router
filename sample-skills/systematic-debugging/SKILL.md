---
name: systematic-debugging
description: Use when investigating bugs, test failures, flaky behavior, runtime errors, regressions, or unclear symptoms that require reproduction, hypothesis testing, root-cause analysis, and verification.
---

# Systematic Debugging

Use this skill when the cause is not already known.

## Workflow

1. Reproduce the failure or collect exact evidence.
2. State the expected behavior and actual behavior.
3. List plausible causes.
4. Test one hypothesis at a time.
5. Prefer direct evidence over broad rewrites.
6. Fix the smallest confirmed cause.
7. Verify the original failure mode and a nearby regression case.

## Guardrails

- Do not patch symptoms without naming the cause.
- Do not change many unrelated things at once.
- Do not assume the most recent edit caused the bug without evidence.
- Preserve useful logs until the fix is verified.

## Common Supporting Skills

- `playwright` for browser automation.
- `browser:control-in-app-browser` for rendered UI evidence.
- `sql-pro` for data-related failures.
- `github:gh-fix-ci` for CI failures.
