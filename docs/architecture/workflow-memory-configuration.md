# Workflow Memory Policy Configuration Contract

- **Status:** Proposed
- **Contract ID:** `workflow-skill-router/memory-policy`
- **Contract version:** `1.0.0`
- **Default effective mode:** `disabled`
- **Canonical representation:** JSON
- **Accepted source formats in Plugin + MCP:** JSON, YAML 1.2 safe subset

This document is the proposed normative configuration reference for Adaptive Workflow Memory.

## 1. Configuration locations

### Personal policy

The Personal Policy defines the maximum memory autonomy the user permits:

```text
Windows:
%LOCALAPPDATA%\Codex\workflow-skill-router\config\workflow-memory.json
%LOCALAPPDATA%\Codex\workflow-skill-router\config\workflow-memory.yaml

macOS:
~/Library/Application Support/Codex/workflow-skill-router/config/workflow-memory.json
~/Library/Application Support/Codex/workflow-skill-router/config/workflow-memory.yaml

Linux:
${XDG_STATE_HOME:-~/.local/state}/codex/workflow-skill-router/config/workflow-memory.json
${XDG_STATE_HOME:-~/.local/state}/codex/workflow-skill-router/config/workflow-memory.yaml
```

`WORKFLOW_SKILL_ROUTER_DATA_DIR` changes the external data root, not the relative `config/workflow-memory.*` location.

### Workspace policy

The Workspace Policy can make a project stricter, but cannot exceed the Personal Policy:

```text
<workspace-root>/.codex/workflow-memory.json
<workspace-root>/.codex/workflow-memory.yaml
```

The workspace root must be advertised by the Client or included in `WORKFLOW_SKILL_ROUTER_WORKSPACE_ROOTS`.

## 2. File selection rules

At each scope, exactly zero or one of the following may exist:

- `workflow-memory.json`
- `workflow-memory.yaml`
- `workflow-memory.yml`

If more than one exists:

```text
effective memory mode = disabled
reason_code = ambiguous-memory-policy
```

The runtime must not choose one based on filename order.

A source must be:

- a regular file;
- UTF-8;
- no larger than 64 KiB;
- inside the fixed policy location;
- not a symlink or reparse point.

## 3. Default behavior

If no valid Personal Policy exists:

```json
{
  "effective_mode": "disabled",
  "reason_code": "personal-policy-missing"
}
```

A Workspace Policy cannot opt the user in by itself.

Disabling memory does not delete existing memory data. Deletion is a separate destructive operation.

## 4. Autonomy levels

The order is fixed:

```text
disabled < observe < reviewed < automatic
```

| Mode | Observation | Analytics | Candidate | User-owned write | Managed write |
| --- | --- | --- | --- | --- | --- |
| `disabled` | none | none | none | never | never |
| `observe` | minimal | local | none | never | never |
| `reviewed` | minimal | local | generated | approval required | approval required by default |
| `automatic` | minimal | local | generated | never automatically | automatic after gates |

The effective mode is the stricter value of the Personal and Workspace modes:

```text
effective_mode = min(personal.mode, workspace.mode)
```

When no Workspace Policy exists, `workspace.mode` is treated as the Personal Mode for this calculation.

## 5. Top-level contract

Minimal valid policy:

```json
{
  "schema_id": "workflow-skill-router/memory-policy",
  "schema_version": "1.0.0",
  "artifact_kind": "memory-policy",
  "policy_id": "personal:default",
  "scope": "personal",
  "mode": "disabled"
}
```

Allowed top-level fields:

| Field | Required | Type | Meaning |
| --- | ---: | --- | --- |
| `schema_id` | yes | string const | `workflow-skill-router/memory-policy` |
| `schema_version` | yes | string const | `1.0.0` |
| `artifact_kind` | yes | string const | `memory-policy` |
| `policy_id` | yes | string | `personal:<id>` or `workspace:<id>` |
| `scope` | yes | enum | `personal` or `workspace` |
| `mode` | yes | enum | `disabled`, `observe`, `reviewed`, `automatic` |
| `storage` | no | object | retention and local-store limits |
| `privacy` | no | object | data minimization |
| `eligibility` | no | object | workflow capture gates |
| `features` | no | object | per-feature behavior |
| `notifications` | no | object | local disclosure behavior |

Unknown fields are rejected. Missing optional sections use the mode preset.

`policy_id` prefix must agree with `scope`.

## 6. Mode presets

### `disabled`

```json
{
  "capture": "none",
  "remember_this_workflow": "disabled",
  "route_feedback": "disabled",
  "history_analytics": "disabled",
  "candidate_generation": "disabled",
  "profile_promotion": "disabled",
  "profile_versioning": "disabled"
}
```

### `observe`

```json
{
  "capture": "minimal",
  "remember_this_workflow": "disabled",
  "route_feedback": "automatic-metadata",
  "history_analytics": "summary",
  "candidate_generation": "disabled",
  "profile_promotion": "disabled",
  "profile_versioning": "disabled"
}
```

### `reviewed`

```json
{
  "capture": "minimal",
  "remember_this_workflow": "prompt",
  "route_feedback": "automatic-metadata",
  "history_analytics": "summary",
  "candidate_generation": "on-completion",
  "profile_promotion": "review-required",
  "profile_versioning": "required"
}
```

### `automatic`

```json
{
  "capture": "minimal",
  "remember_this_workflow": "automatic",
  "route_feedback": "automatic-metadata",
  "history_analytics": "summary",
  "candidate_generation": "on-completion",
  "profile_promotion": "automatic-managed",
  "profile_versioning": "required"
}
```

A feature override may make the preset stricter. It must not exceed the autonomy permitted by `mode`.

## 7. `storage`

```yaml
storage:
  backend: local-sqlite
  retention_days: 90
  max_observations: 1000
  candidate_retention_days: 30
  rejected_suppression_days: 180
  max_revisions_per_profile: 20
  purge_on_disable: false
```

| Field | Type | Default | Constraint |
| --- | --- | ---: | --- |
| `backend` | enum | `local-sqlite` | only supported value in V1 |
| `retention_days` | integer | `90` | `1..3650` |
| `max_observations` | integer | `1000` | `1..100000` |
| `candidate_retention_days` | integer | `30` | `1..365` |
| `rejected_suppression_days` | integer | `180` | `1..3650` |
| `max_revisions_per_profile` | integer | `20` | `2..1000` |
| `purge_on_disable` | boolean | `false` | explicit opt-in only |

A Workspace Policy can lower retention and maximum counts. It cannot increase Personal limits.

`purge_on_disable: true` must apply only to Optional History and Candidate data. It must not silently delete User-owned Profile files.

## 8. `privacy`

```yaml
privacy:
  objective: digest-only
  workspace_identity: digest-only
  raw_prompt: never
  file_paths: never
  file_content: never
  tool_arguments: never
  secrets: never
  free_text_feedback: never
  export_redaction: required
```

Allowed values:

| Field | Allowed |
| --- | --- |
| `objective` | `digest-only`, `never` |
| `workspace_identity` | `digest-only`, `never` |
| `raw_prompt` | `never` |
| `file_paths` | `never` |
| `file_content` | `never` |
| `tool_arguments` | `never` |
| `secrets` | `never` |
| `free_text_feedback` | `never`, `explicit-opt-in` |
| `export_redaction` | `required` |

V1 does not allow a policy to set Raw Prompt, File Content, Tool Arguments, or Secrets to a stored state.

## 9. `eligibility`

```yaml
eligibility:
  require_terminal_success: true
  require_required_gate_pass: true
  reject_unknown_side_effects: true
  exclude_risk_levels:
    - r3
  minimum_distinct_runs_reviewed: 3
  minimum_distinct_runs_automatic: 5
  minimum_distinct_days_reviewed: 2
  minimum_distinct_days_automatic: 3
  minimum_success_rate_reviewed: 0.80
  minimum_success_rate_automatic: 0.90
  maximum_correction_rate_reviewed: 0.20
  maximum_correction_rate_automatic: 0.10
  minimum_route_consistency_reviewed: 0.75
  minimum_route_consistency_automatic: 0.85
```

Hard invariants:

- `automatic` thresholds cannot be weaker than `reviewed`;
- Hard Contract Violation always blocks promotion;
- Explicit `no-memory` always blocks capture;
- R3 is excluded from automatic capture and promotion in V1;
- Resume attempts are deduplicated;
- Unknown Skill IDs are not promotable.

## 10. `features`

### 10.1 Remember This Workflow

```yaml
features:
  remember_this_workflow:
    mode: prompt
    eligible_event: terminal-success
    default_target: managed-personal
```

`mode`:

- `disabled`
- `prompt`
- `automatic`

`default_target`:

- `managed-personal`
- `managed-workspace-local`
- `user-personal`
- `workspace-file`

Constraints:

- `automatic` mode may target only `managed-personal` or `managed-workspace-local`;
- `user-personal` and `workspace-file` require `reviewed` flow;
- `workspace-file` additionally requires verified workspace root and Host file-write authority.

### 10.2 Route Feedback

```yaml
features:
  route_feedback:
    mode: automatic-metadata
    allow_standard_reason_codes: true
    allow_free_text: false
```

`mode`:

- `disabled`
- `manual`
- `automatic-metadata`

Automatic metadata includes route deltas, gate results, consent results, completion status, and capability availability. It does not include free-form conversation text.

### 10.3 History Analytics

```yaml
features:
  history_analytics:
    mode: summary
    run: on-demand
```

`mode`:

- `disabled`
- `summary`
- `detailed-local`

`run`:

- `on-demand`
- `on-completion`
- `scheduled-local`

Scheduled analysis is local only and requires a Host scheduler. The Router must not claim scheduling if the Host does not provide it.

### 10.4 Candidate Generation

```yaml
features:
  candidate_generation:
    mode: on-completion
    confidence_required: medium
    backtest_required: true
```

`mode`:

- `disabled`
- `on-demand`
- `on-completion`

`confidence_required`:

- `medium`
- `high`

Automatic promotion always requires `high`, regardless of a weaker configured value.

### 10.5 Profile Promotion

```yaml
features:
  profile_promotion:
    mode: review-required
    target: managed-personal
    conflict_policy: fail-closed
    require_profile_lint: true
    require_backtest: true
```

`mode`:

- `disabled`
- `review-required`
- `automatic-managed`

`conflict_policy` V1 only supports `fail-closed`.

`automatic-managed` cannot target a User-owned Profile.

### 10.6 Profile Versioning

```yaml
features:
  profile_versioning:
    mode: required
    diff: semantic-and-json
    rollback: enabled
    write_strategy: compare-and-swap
```

Allowed V1 values:

- `mode`: `disabled`, `required`
- `diff`: `semantic-and-json`
- `rollback`: `enabled`
- `write_strategy`: `compare-and-swap`

If Profile Promotion is enabled, Versioning must be `required`.

## 11. `notifications`

```yaml
notifications:
  show_completion_prompt: true
  show_candidate_created: true
  show_auto_promotion: true
  show_retention_purge: true
```

Notifications are local disclosures. They are not telemetry.

In `automatic` mode, `show_auto_promotion` defaults to `true` and cannot be disabled in V1. Automatic changes must remain visible.

## 12. Policy resolution algorithm

```text
1. Load Host hard constraints.
2. Load Personal Policy from fixed external-data location.
3. If Personal Policy is missing or invalid, set effective mode to disabled.
4. Resolve verified Workspace Root.
5. Load zero or one Workspace Policy.
6. If Workspace Policy is invalid or ambiguous, disable memory for that workspace.
7. Compute the lower autonomy level.
8. Intersect target types, retention, privacy, and thresholds.
9. Apply explicit no-memory as a hard per-run reduction.
10. Apply typed one-shot remember request without exceeding the ceiling.
11. Canonicalize the effective policy and calculate its digest.
12. Persist only the sanitized Policy Snapshot when memory is enabled.
```

For numeric constraints:

- minimum evidence thresholds use the larger value;
- maximum correction or retention limits use the smaller value;
- allowed targets use set intersection;
- privacy uses the more restrictive representation;
- feature autonomy uses the lower level.

## 13. YAML safety profile

The YAML loader must reject:

```yaml
# anchors and aliases
defaults: &defaults
  mode: automatic
policy:
  <<: *defaults
```

It must also reject:

- `!!python/*` or any explicit tag;
- more than one YAML document;
- duplicate keys;
- merge keys;
- non-string object keys;
- non-JSON scalar types that cannot be canonicalized consistently.

The loader output must pass the same JSON Schema validation as a JSON source.

## 14. Status output

`get_memory_status` and CLI status should return:

```json
{
  "mode": "reviewed",
  "personal_mode": "automatic",
  "workspace_requested_mode": "reviewed",
  "policy_source": "workspace-restriction",
  "policy_digest": "sha256:...",
  "capture_enabled": true,
  "candidate_generation_enabled": true,
  "profile_promotion": "review-required",
  "allowed_targets": [
    "managed-personal"
  ],
  "memory_store_exists": true,
  "warnings": []
}
```

It must not echo the entire policy document by default.

## 15. Configuration recipes

### No memory

```yaml
schema_id: workflow-skill-router/memory-policy
schema_version: 1.0.0
artifact_kind: memory-policy
policy_id: personal:default
scope: personal
mode: disabled
```

### Observe before enabling recommendations

```yaml
schema_id: workflow-skill-router/memory-policy
schema_version: 1.0.0
artifact_kind: memory-policy
policy_id: personal:pilot
scope: personal
mode: observe
```

### Reviewed, semi-automatic memory

```yaml
schema_id: workflow-skill-router/memory-policy
schema_version: 1.0.0
artifact_kind: memory-policy
policy_id: personal:reviewed
scope: personal
mode: reviewed
features:
  remember_this_workflow:
    mode: prompt
    eligible_event: terminal-success
    default_target: managed-personal
  profile_promotion:
    mode: review-required
    target: managed-personal
    conflict_policy: fail-closed
    require_profile_lint: true
    require_backtest: true
  profile_versioning:
    mode: required
    diff: semantic-and-json
    rollback: enabled
    write_strategy: compare-and-swap
```

### Automatic memory without modifying User-owned files

```json
{
  "schema_id": "workflow-skill-router/memory-policy",
  "schema_version": "1.0.0",
  "artifact_kind": "memory-policy",
  "policy_id": "personal:automatic",
  "scope": "personal",
  "mode": "automatic",
  "features": {
    "remember_this_workflow": {
      "mode": "automatic",
      "eligible_event": "terminal-success",
      "default_target": "managed-personal"
    },
    "profile_promotion": {
      "mode": "automatic-managed",
      "target": "managed-personal",
      "conflict_policy": "fail-closed",
      "require_profile_lint": true,
      "require_backtest": true
    },
    "profile_versioning": {
      "mode": "required",
      "diff": "semantic-and-json",
      "rollback": "enabled",
      "write_strategy": "compare-and-swap"
    }
  }
}
```

## 16. Migration and compatibility

- Existing installations without this file remain `disabled`.
- Existing Routing Profiles remain valid and unchanged.
- Memory Policy does not change the `routing-profile@1.0.0` schema.
- Managed Profiles must be loaded through a new lower-precedence source layer.
- Skill-only remains `skill-only-fallback` and cannot claim durable memory.
- Invalid Memory Policy must never prevent ordinary non-memory routing.

## 17. Repository examples

- [`examples/workflow-memory.disabled.yaml`](examples/workflow-memory.disabled.yaml)
- [`examples/workflow-memory.reviewed.yaml`](examples/workflow-memory.reviewed.yaml)
- [`examples/workflow-memory.automatic.json`](examples/workflow-memory.automatic.json)
