# Contributing

Thanks for helping improve Workflow Skill Router.

The best contributions are concrete routing scenarios. A useful issue or PR should include:

- the user request
- the available skills
- the route the agent chose
- the route you expected
- the conflict rule or example that would prevent the mistake next time

## Contribution Types

- New example router for a company-style workflow.
- New recipe for a common routing pattern.
- Validator improvement.
- Documentation improvement.
- Routing failure report with reproducible inputs.

## Privacy Rules

Do not include:

- private repository paths
- internal project names
- customer names
- hostnames, secrets, tokens, or domains
- regulated data
- deployment branch names from a real organization

Use placeholders such as `Acme Corp`, `Customer Portal`, `Internal Admin`, `Revenue Platform`, and `Operations Dashboard`.

## Validation

Run the validator before opening a PR:

```bash
python scripts/validate-router.py starter/workflow-skill-router
```

For examples:

```bash
python scripts/validate-router.py examples/generic-agent
```

