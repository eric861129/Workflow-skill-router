---
name: requirements-clarity
description: Use when a request is ambiguous, high-impact, multi-stakeholder, or likely to need scope boundaries, acceptance criteria, constraints, risks, and staged implementation decisions before coding.
metadata:
  domain: requirements
  scope: planning, clarification
  triggers: ambiguous request, scope boundary, acceptance criteria, stakeholder tradeoff, constraints, staged implementation
  exclusions: trivial command, already-specified implementation task, final verification only
  tags: requirements, planning, acceptance, scope
---

# Requirements Clarity

Use this skill before implementation when the request can be interpreted in more than one reasonable way.

## Workflow

1. Restate the user goal in one sentence.
2. Separate known facts, assumptions, and open questions.
3. Identify users, workflows, inputs, outputs, and failure cases.
4. Define acceptance criteria.
5. Name constraints such as compatibility, privacy, performance, timeline, and migration needs.
6. Recommend the smallest next implementation slice.

## Output Shape

```text
Goal:
Known:
Assumptions:
Open questions:
Acceptance criteria:
Suggested first slice:
```

Ask only the questions that block safe progress. Continue with reasonable assumptions when the risk is low.
