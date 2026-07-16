# V2 model evaluation adapters

Workflow Skill Router V2 evaluates routing behavior through a sealed subprocess boundary. The adapter is an execution transport, not a scorer: it receives only an opaque case ID, the current prompt, the allowed tool names, a nonce, and an opaque provider context. Scoring keys and expected answers never cross this boundary.

## Evidence classes

| Evidence class | What it proves | Release use |
| --- | --- | --- |
| `reference-driver` | The protocol, orchestration, and artifact pipeline are reproducible. | Contract and smoke evidence only. It is permanently labeled and cannot be promoted to Behavior evidence. |
| `fresh-model-execution` | A configured provider created fresh model contexts and returned real turns. | Behavior or Outcome evidence after integrity checks and review. |
| `manual-import` | An external run was imported with provenance. | Review-required fallback when no trusted adapter is configured. |

Contract or reference-driver results do **not** prove real-model routing quality. Public benchmark claims must name the model/provider configuration, run count, case digest, and evidence class.

## Process protocol

Each `start_attempt` or `execute_turn` is one process invocation:

1. The host writes one UTF-8 JSON object to stdin.
2. The driver writes one UTF-8 JSON object to stdout and exits with code `0`.
3. `start_attempt` returns a fresh, opaque `context_id` bound to the supplied `attempt_nonce`.
4. Later turns return the same nonce and context. A mismatch, reused context, malformed JSON, non-zero exit, timeout, or oversized output invalidates the attempt.

The normative shape is [adapter-protocol.schema.json](adapter-protocol.schema.json). The default timeout is 120 seconds per invocation and the default combined stdout/stderr limit is 1 MiB. Hosts may lower either limit. Provider sessions, credentials, and retry policy remain driver-owned.

## Trusted configuration boundary

The executable is configured by the CLI or MCP host as an absolute path plus separate argv items. The adapter always uses `shell=False`. Model/MCP requests cannot submit an executable, path, environment, command string, or adapter kind; they carry only an authorization reference and sealed-case reference. Environment variables are inherited from the trusted host process and are never accepted from model arguments.

Preview a reference-driver configuration:

```powershell
$Python = (Get-Command python).Source
workflow-skill-router evaluation run `
  --profile behavior `
  --evidence-class reference-driver `
  --adapter subprocess `
  --adapter-executable $Python `
  --adapter-arg evaluation/v2/reference_driver.py `
  --repeats 3
```

For a real Behavior or Outcome run, use `--evidence-class fresh-model-execution` and explicitly add `--confirm-live-run`. This confirmation matters because providers may incur quota, latency, or monetary cost. The CLI prints a dry-run manifest before execution orchestration consumes it.

## Freshness and failure handling

- Every repeat must create a distinct provider context; a driver must not reuse chat/session IDs.
- The nonce is supplied by the orchestrator and must be echoed unchanged.
- The opaque context is the only driver state returned to later turns.
- A failed or ambiguous attempt is evidence of failure, not a reason to relabel or silently synthesize output.
- When a trusted adapter is unavailable, export a manual bundle and keep the resulting evidence review-required.
