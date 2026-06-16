# Customization Guide

Workflow Skill Router is a starter pattern. Customize it by mapping your agent's actual skills to the routing contract.

It addresses skill selection sprawl, not authorization. Keep your existing scope contracts, runtime permissions, approval policies, and tool access controls in place.

## Step 1: Copy The Starter

Copy `starter/workflow-skill-router/` into your agent skill directory.

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

## Step 5: Share Examples Responsibly

Use fictional company-style examples when sharing routers. Do not include:

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

