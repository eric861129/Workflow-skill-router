# Forward Tests

Forward tests record public-safe examples of real agent usage where Workflow Skill Router was used before execution.

Each record should capture:

- `id`: stable test id.
- `captured_at`: ISO date.
- `input`: the original user request, sanitized for public sharing.
- `router_output`: route, primary skill, supporting skills, and reason.
- `final_skill_set`: the skill set actually used.
- `anti_over_routing_note`: why nearby skills were intentionally left out.
- `verification`: what confirmed the route was useful.

Keep entries public-safe. Do not include private paths, hostnames, customer names, secrets, school names, or organization-specific rules.
