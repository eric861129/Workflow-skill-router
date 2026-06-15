# Routing Metrics

These metrics are produced by `scripts/evaluate-routing.py`. Use them to understand whether a router is focused, explainable, and bounded.

## Primary Accuracy

Definition: the share of scenarios where `selected.primary` equals `expected.primary`.

Why it matters: the primary skill owns the work. If it is wrong, supporting skills rarely save the route.

How to improve it: sharpen routing rules around task nature, work stage, and domain ownership.

Common failure examples: a frontend rendering bug routes to API design first; a docs-only task routes to implementation.

## Supporting Recall

Definition: the share of expected supporting skills that were selected.

Why it matters: a route can choose the right owner while missing required verification or contract support.

How to improve it: add scenario notes that explain which supporting jobs are required.

Common failure examples: API contract sync misses generated-client support; release prep misses test planning.

## Supporting Precision

Definition: the share of selected supporting skills that were expected.

Why it matters: low precision signals noisy routes and wasted context.

How to improve it: forbid broad related skills in narrow scenarios and keep the maximum route size small.

Common failure examples: a typo fix selects frontend, browser, and release skills.

## Exact Route Match Rate

Definition: the primary skill matches and the supporting skill set matches exactly.

Why it matters: this is the strictest route quality signal.

How to improve it: split large tasks into stage-specific scenarios and keep expected routes small.

Common failure examples: the router selects the right primary but adds an extra broad meta skill.

## Forbidden Skill Violation Rate

Definition: the share of scenarios where a forbidden skill appears in primary or supporting selections.

Why it matters: forbidden skills test domain boundaries and over-routing risk.

How to improve it: add conflict rules for repeated mistakes and include forbidden examples in CI.

Common failure examples: documentation metrics select database skills; frontend regressions select database migration skills.

## Max Skill Count Violation Rate

Definition: the share of scenarios where selected primary plus supporting count exceeds `max_skills`.

Why it matters: the router should protect context budget.

How to improve it: stage large tasks and prefer one primary plus only distinct supporting jobs.

Common failure examples: a broad modernization request selects six implementation skills instead of planning stages.

## Over-routing Rate

Definition: the share of scenarios where selected skill count is larger than the expected count or exceeds `max_skills`.

Why it matters: over-routing often looks harmless, but it dilutes attention and increases instruction conflicts.

How to improve it: add narrow scenarios and forbid skills that are related but unnecessary.

Common failure examples: a docs edit selects implementation, QA, and release skills.

## Average Selected Skill Count

Definition: average count of selected primary plus supporting skills across scenarios.

Why it matters: this shows whether routes are generally compact.

How to improve it: audit scenarios with high selected counts and split stage-heavy tasks.

Common failure examples: every route defaults to three or four skills regardless of task size.

## Route Explanation Present Rate

Definition: the share of predictions with a non-empty explanation.

Why it matters: explanations make routing decisions reviewable.

How to improve it: require one concrete reason for the primary skill and avoid generic boilerplate.

Common failure examples: predictions include skill ids but no reason, or use vague explanations like "these are relevant."
