# Recipe: Connector-Heavy Workflow

Use this route when the task depends on live external state such as GitHub, workspace files, email, calendars, issue trackers, browser sessions, or CI providers.

## Good Route

```text
Route: Connector / Workspace files > Docs, sheets, and comments > Collaboration review
Use SKILL: workspace-connector, document-tool, spreadsheet-tool
Reason: workspace-connector finds the source file; document-tool handles document fidelity; spreadsheet-tool handles tabular data when needed.
```

## Priority Rule

When external state is the source of truth, connector skills come first. Local reasoning skills can support interpretation, but they should not invent data the connector has not retrieved.

## Avoid

- Replacing live connector reads with web search.
- Summarizing unavailable external data as if it had been fetched.
- Loading every connector when the task only names one system.

