---
title: V2 Roadmap
description: Track evidence-backed milestones from alpha to GA.
---

## Alpha — contract and local control plane

- Runtime Capability Discovery and merge authority
- Single, Phased, and Managed Goal policy
- Explicit Skill Lock and consent semantics
- Phase/Goal state machines and durable event contracts
- Plugin packaging, MCP schemas, local R0 `plan_work` and status
- Sealed subprocess evaluation adapter and reference fixtures
- Inspectable Flight Recorder

## Beta 2.0.0-beta.1 — completed

- [x] Published the immutable `v2.0.0-beta.1` marketplace snapshot

## Beta 2.0.0-beta.2 — completed

- [x] Add Personal and Workspace Routing Profiles with packaged examples
- [x] Close junction, symlink, migration, and evidence-labeling gaps
- [x] Pass Windows, macOS, and Linux CI on the frozen source revision
- [x] Publish the prerelease and move only `latest-v2`
- [x] Completed the corrected 36-attempt Behavior smoke with explicit quota authorization
- [x] Reviewed paired results and published only attested, sanitized evidence
- [x] Validated Plugin and Skill-only release-archive contracts on Windows, macOS, and Linux

## Beta 2.0.0-beta.3 — completed

- [x] Close the Lighthouse/OpenTelemetry development-tooling advisory with a scoped dependency boundary
- [x] Remove the privileged `workflow_run` checkout from Pages deployment
- [x] Bind Pages publication to the validated trusted `main` revision
- [x] Publish a new immutable prerelease and move only `latest-v2`

## Beta 2.0.0-beta.4 — local candidate

- [x] Add explainable no-hint classification for Single, Phased, and Managed Goal work
- [x] Add deterministic Profile explain/lint and the Contract 2.3.0 Profile-miss case
- [x] Seal attempt nonce, tool inventory, instruction digest, public case digest, model version, and private scoring-spec digest
- [x] Prepare deterministic Plugin and Skill-only release artifacts locally
- [ ] Obtain explicit authorization for the 36-attempt / 42-turn model run
- [ ] Review sanitized evidence, attest zero hard violations, and publish the immutable prerelease

The reference-driver validates the offline contract but does not prove real-model behavior. Until the remaining review and publication gates finish, beta.3 remains the latest published V2 snapshot.

## Next beta milestone

- [ ] Exercise a verified Host scheduler/evidence integration beyond fixtures

## GA — promotion gate

- [ ] Pass the 13-case, 78-attempt, 96-model-turn paired Behavior suite
- [ ] Maintain zero hard violations
- [ ] Complete security review, dependency/SBOM checks, docs parity, and release rehearsal
- [ ] Remove reviewed V1 public clutter through the manual manifest gate
- [ ] Promote `latest` only after every required gate passes

Roadmap items are not availability claims. Current readiness remains the generated runtime matrix.
