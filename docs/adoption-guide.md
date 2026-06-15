# Adoption Guide

Workflow Skill Router works best when you separate the public routing pattern from your private company rules.

## Recommended Model

```text
public core
  -> shared task model
  -> output contract
  -> skill count rules
  -> connector priority

private overlay
  -> repository names
  -> internal systems
  -> deployment rules
  -> customer data policies
  -> team-specific review gates
```

## Step 1: Start With The Public Core

Copy `starter/workflow-skill-router/` into your agent skill directory and keep it generic. The starter should describe how routing works, not every detail of your company.

## Step 2: Inventory Your Skills

Group your agent skills by source:

- local custom skills
- connector or plugin skills
- system skills
- meta workflow skills
- file-format skills

Mark skills that are likely to over-trigger. These usually include broad design, writing, planning, and meta workflow skills.

## Step 3: Build Routes By Work Stage

Avoid a flat category like "frontend skills." Split by work stage:

- new app or page
- browser debugging
- visual design
- design system work
- scripted regression testing

Each route should choose one Primary skill and up to three Supporting skills.

## Step 4: Add Conflict Rules

Conflict rules are what make the router valuable. Add rules for common overlaps:

- connector skill vs local reasoning skill
- browser inspection vs scripted browser automation
- PR review connector vs code review reasoning
- file-format tool vs generic documentation skill
- broad meta workflow vs narrow implementation skill

## Step 5: Keep Private Details Out Of Public Examples

Before publishing examples, remove:

- real repository paths
- internal project names
- customer names
- deployment branch names
- secrets, domains, tokens, or hostnames
- regulated data references

Use company-style placeholders such as `Acme Corp`, `Customer Portal`, `Internal Admin`, `Revenue Platform`, and `Operations Dashboard`.

## Step 6: Validate

Run:

```bash
python scripts/validate-router.py starter/workflow-skill-router
```

Then validate every example router before publishing.

