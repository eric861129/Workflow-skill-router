# Evaluation Guide

## V2 evidence classes

The historical 80-case suite is **Tier 0 Contract**. Real Behavior/Outcome evaluation requires fresh execution, three or more attempts, answer isolation, hard-invariant scoring, and paired comparison. No adapter produces `manual-required`; no verified human review produces `review-required` without a public score. `skill-only-fallback` cannot satisfy the bound-content observability required for `hybrid-full`.

Use routing evaluation when you want a workflow-skill-router to improve over time without becoming noisy.

## Design Scenarios

Good scenarios are small, realistic, and tied to a routing decision you care about. Use real incidents, review misses, CI failures, and onboarding questions as source material, but remove private names, paths, URLs, and customer details.

Cover both ordinary and boundary cases:

- single-domain implementation tasks
- cross-domain debugging tasks
- docs-only tasks
- release and review tasks
- broad requests that should be split into stages
- tasks that are close to a forbidden domain

## Design Expected Routes

Pick one primary skill that owns the work. Add supporting skills only when they perform distinct jobs such as contract review, browser reproduction, test planning, or release hygiene.

Avoid expected routes that are just a list of everything related. If more than four skills seem necessary, make the scenario a stage-split case.

## Use Forbidden Skills

Forbidden skills are route boundary tests. Add them when a task is near another domain but should not activate it.

Examples:

- docs metric explanation forbids database and backend skills
- frontend API regression forbids database migration
- one-line typo fix forbids browser and implementation skills

## Choose `max_skills`

Set `max_skills` to the number of skills that are genuinely useful for the scenario. For most tasks:

- `1`: narrow docs, typo, or single-skill maintenance task
- `2`: one owner plus one support skill
- `3`: cross-layer task with verification
- `4`: staged planning or broad release preparation

## Avoid Overfitting

Do not tune the router only to the exact wording in the examples. Vary task text, context length, and domain terms. Keep scenario notes focused on why the route is expected, not on prompt tricks.

## Convert Incidents Into Scenarios

When a router makes a poor selection:

1. Remove private details.
2. Write the original task as `task`.
3. Put the missing context in `context`.
4. Record the route you wanted in `expected`.
5. Add wrong-but-tempting skills to `forbidden`.
6. Set `max_skills` to the smallest useful route.

## Evolve The Benchmark

Add scenarios when new skills are introduced, when route conflicts repeat, or when a new project domain appears. Keep old scenarios unless the routing policy changed intentionally.

When the benchmark grows, compare trends rather than one metric alone. Primary accuracy, forbidden violations, and max skill count violations are usually the most important CI gates.

## Use Reports To Find Gaps

Read the failed scenario table first. Repeated primary mismatches usually mean the skill tree has unclear ownership. Low supporting recall means the router misses secondary jobs. Low precision or high over-routing means the router is pulling in related but unnecessary skills.
