# Capability-unavailable attestation template

Use this template only when a real Host capability is absent. It is a safe
preparation aid, not a Host Pilot result, release approval, Host-access grant,
or evidence that `hybrid-full` is available.

Schema: [`evaluation/v2/pilots/capability-unavailable-attestation.schema.json`](../../evaluation/v2/pilots/capability-unavailable-attestation.schema.json)

Validator: [`evaluation/v2/pilots/validate_capability_unavailable_attestation.py`](../../evaluation/v2/pilots/validate_capability_unavailable_attestation.py)

## Discovery/preflight note — draft-not-attested

Use an internal discovery/preflight note to identify the capability that still
needs review. Mark it `draft-not-attested`. Do not add a reviewer, timestamp,
Host receipt, result, transcript, secret, local path, workspace path, or source
path. A draft-not-attested note is not public evidence and is rejected by the
reviewed-attestation validator.

Before requesting review, confirm only these safe facts:

- the checked capability is `sync_runtime_context` or `validate_route`;
- it remains `verified-host-required`;
- the observed runtime binding is `bundled-local-r0`, no conformance profile,
  and `skill-only-fallback`;
- the selected evidence lane is `capability-unavailable`, never
  `verified-host-pilot`.

## Reviewed attestation — future use only

Only an authorized human reviewer may create a reviewed attestation after an
actual capability check. Use the canonical schema fields and no others:

| Field | Future reviewed value |
| --- | --- |
| `schema_version` | `workflow-skill-router/capability-unavailable-attestation/1.0` |
| `record_type` | `reviewed-capability-unavailable-attestation` |
| `attestation_status` | `reviewed` |
| `evidence_lane` | `capability-unavailable` |
| `claim_boundary` | `unavailable-evidence-only-not-a-verified-host-pilot` |
| `checked_capability` | ID plus `verified-host-required` authority requirement |
| `source_revision` | Public-safe `git:` revision identifier only |
| `runtime` | The exact safe runtime binding plus the public-safe `sha256:` runtime package digest defined by the schema |
| `authority_boundary` | `real-host-apis-absent` |
| `safe_diagnostic` | `verified-host-capability-unavailable` |
| `reviewer` | Opaque UUIDv4 reviewer ID prefixed with `reviewer:`, never a Host receipt or secret |
| `timestamp` | Canonical RFC3339 UTC: `YYYY-MM-DDTHH:MM:SSZ` |
| `claims` | `verified_host_pilot`, `production_authority`, and `hybrid_full` all `false` |

Validate a proposed reviewed record without printing its content:

```powershell
python evaluation/v2/pilots/validate_capability_unavailable_attestation.py `
  --record <reviewed-attestation.json>
```

The command emits only `valid` and a safe code. A valid result means the record
stays inside the capability-unavailable claim boundary; it does not establish
`hybrid-full`, a verified Host Pilot, or production authority.

## Public-evidence exclusions

Never add raw Host receipts, secrets, repository or workspace paths, local
configuration, raw transcripts, objectives, or unreviewed evidence. Keep any
real review material in the separately authorized restricted review process;
the reviewed public record is intentionally minimal and non-executable.
