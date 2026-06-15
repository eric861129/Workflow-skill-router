# Workflow Skill Tree

## Reproduction / Browser / Runtime

- Frontend / Reproduce / Local rendered app: Primary: `browser`; Supporting: `frontend-debugging`, `systematic-debugging`
- Frontend / Reproduce / Logged-in Chrome session: Primary: `chrome-session`; Supporting: `browser`, `frontend-debugging`, `systematic-debugging`
- Frontend / Reproduce / Automated regression: Primary: `playwright`; Supporting: `frontend-debugging`, `test-planning`

## Diagnosis / Framework / Data

- Frontend / Diagnose / Component state or reactivity: Primary: `framework-expert`; Supporting: `frontend-debugging`, `systematic-debugging`
- Frontend / Diagnose / API or data mismatch: Primary: `api-debugging`; Supporting: `frontend-debugging`, `browser`, `systematic-debugging`
- Frontend / Diagnose / Styling or layout: Primary: `ui-debugging`; Supporting: `browser`, `accessibility-review`

## Fix / Verification

- Frontend / Fix / UI behavior: Primary: `frontend-builder`; Supporting: `framework-expert`, `browser`, `test-planning`
- Frontend / Verify / Visual and interaction QA: Primary: `browser`; Supporting: `playwright`, `frontend-debugging`

