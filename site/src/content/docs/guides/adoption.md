---
title: Adoption Guide
description: Use a public core and private overlay to keep routing reusable and company-specific.
---

## Recommended structure

Keep public routing rules generic and put company details in a private overlay.

```text
public core
  -> task model
  -> output contract
  -> skill count rules
  -> connector priority

private overlay
  -> repository names
  -> internal systems
  -> deployment rules
  -> customer data policies
```

## Inventory your skills

Group skills by source:

- local custom skills
- connector or plugin skills
- system skills
- meta workflow skills
- file-format skills

Mark skills that are likely to over-trigger, especially broad writing, design, planning, and meta workflow skills.

## Write conflict rules

Conflict rules are the main value of the router.

Common conflicts:

- connector skill vs local reasoning skill
- browser inspection vs scripted browser automation
- PR review connector vs code review reasoning
- file-format tool vs generic documentation skill
- broad meta workflow vs narrow implementation skill

## Sanitize public examples

Before publishing examples, remove:

- real repository paths
- internal project names
- customer names
- hostnames, tokens, and secrets
- deployment branch names
- regulated data details

Use placeholders such as `Acme Corp`, `Customer Portal`, `Internal Admin`, `Revenue Platform`, and `Operations Dashboard`.

