# Workflow Skill Router V2 GA Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the reviewed V2 candidate into a verifiable `v2.0.0` GA release without overstating runtime authority, model evidence, or Host integration.

**Architecture:** Preserve the existing two-commit release model: a frozen, fully tested source revision first; only after independent model evidence and maintainer review may a metadata-only trusted promotion bind that revision for publication. GA unifies Core, Plugin, artifacts, docs, and release metadata under one version while retaining V1.3.1 as an immutable recovery point.

**Tech Stack:** Python 3.11 Router Core and `unittest`, TypeScript/Node 24 MCP server with Zod, SQLite runtime, Astro/Starlight documentation site, GitHub Actions, GitHub provenance attestations.

---

### Task 1: Establish the GA version contract

**Files:**
- Modify: `release/version.json`
- Modify: `packages/router-core/pyproject.toml`
- Modify: `packages/router-core/src/workflow_skill_router/__init__.py`
- Modify: `plugins/workflow-skill-router/package.json`
- Modify: `plugins/workflow-skill-router/package-lock.json`
- Modify: `plugins/workflow-skill-router/mcp/src/server.ts`
- Create: `tests/test_release_versions.py`

- [ ] **Step 1: Write the failing cross-surface version test.**

```python
def test_ga_version_is_identical_across_runtime_surfaces(self) -> None:
    self.assertEqual("2.0.0", version["v2_version"])
    self.assertEqual(version["v2_version"], core_pyproject_version)
    self.assertEqual(version["v2_version"], core_init_version)
    self.assertEqual(version["v2_version"], plugin_package_version)
    self.assertIn(f'version: "{version["v2_version"]}"', server_source)
```

- [ ] **Step 2: Run `python -m unittest tests/test_release_versions.py -v`.**

Expected: FAIL because Core exposes `2.0.0a1` and the Plugin exposes `2.0.0-beta.5`.

- [ ] **Step 3: Replace every product-facing candidate version with `2.0.0`.**

Keep `published_v2_version: "2.0.0-beta.3"` as historical provenance, set `v2_version: "2.0.0"`, retain `v1_pinned_version: "1.3.1"`, and remove the misleading `target_prerelease` metadata field. Do not set `release_lifecycle` publishable yet.

- [ ] **Step 4: Rebuild and lock the generated Plugin bundle.**

Run: `npm.cmd run build` in `plugins/workflow-skill-router`.

Expected: `mcp/server.bundle.mjs` includes `version: "2.0.0"` and has no stale source-only changes.

- [ ] **Step 5: Run the focused version test.**

Run: `python -m unittest tests/test_release_versions.py -v`.

Expected: PASS.

- [ ] **Step 6: Commit the self-consistent version contract.**

```text
git commit -m "chore(release): establish v2.0.0 version contract"
```

### Task 2: Close the Explicit Skill Lock MCP contract gap

**Files:**
- Modify: `plugins/workflow-skill-router/mcp/src/tool-schemas.ts`
- Modify: `plugins/workflow-skill-router/mcp/test/tool-surface.test.ts`
- Modify: `plugins/workflow-skill-router/mcp/test/bundled-runtime.test.ts`
- Modify: `plugins/workflow-skill-router/skills/workflow-skill-router/SKILL.md`
- Modify: `site/src/content/docs/concepts/explicit-skill-lock.md`
- Modify: `site/src/content/docs/zh-tw/concepts/explicit-skill-lock.md`

- [ ] **Step 1: Add a failing MCP schema assertion for `all`.**

```ts
assert.equal(schema.safeParse({
  ...base,
  explicit_skill_ids: ["skill:api-designer", "skill:qa-test-planner"],
  explicit_semantics: "all",
}).success, true);
```

Also assert an internal value such as `required-all` remains rejected at the public MCP boundary.

- [ ] **Step 2: Run `npm.cmd test` in `plugins/workflow-skill-router`.**

Expected: FAIL because the Zod enum only admits `use` and `only`.

- [ ] **Step 3: Expose the supported directive token, not the internal enum.**

Change the schema to `z.enum(["use", "only", "all"])`; keep Core’s `all -> REQUIRED_ALL` mapping in `routing/directives.py` unchanged. This preserves one public syntax and one internal semantic representation.

- [ ] **Step 4: Add a bundled-runtime assertion.**

Send `plan_work` with two explicit Skills and `explicit_semantics: "all"`; assert the returned route reports `required-all` and includes coverage for both requested Skills.

- [ ] **Step 5: Update both language surfaces.**

Explain `use`, `only`, and `all` with one compact table. State that `all` requires every named Skill to be represented; it does not grant activation authority or bypass scoped consent for extra support.

- [ ] **Step 6: Rebuild and verify the Plugin contract.**

Run: `npm.cmd run check` in `plugins/workflow-skill-router`.

Expected: bundle regenerated, all Node tests pass, and `required-all` is absent from client input examples.

- [ ] **Step 7: Commit the public Explicit Skill Lock contract.**

```text
git commit -m "fix(mcp): support all explicit skill semantics"
```

### Task 3: Make MCP failure behavior truthful and request-isolated

**Files:**
- Modify: `plugins/workflow-skill-router/mcp/src/server.ts`
- Modify: `plugins/workflow-skill-router/mcp/src/core-client.ts`
- Modify: `plugins/workflow-skill-router/mcp/test/bundled-runtime.test.ts`
- Create: `plugins/workflow-skill-router/mcp/test/core-client.test.ts`
- Modify: `site/src/content/docs/guides/troubleshooting.md`
- Modify: `site/src/content/docs/zh-tw/guides/troubleshooting.md`

- [ ] **Step 1: Write failing bridge isolation tests.**

```ts
test("a timeout rejects only its own request", async () => {
  const first = client.call("plan_work", firstArguments);
  const second = client.call("get_router_status", secondArguments);
  await assert.rejects(first, /bridge-timeout/);
  await assert.doesNotReject(second);
});
```

Use a fake child process with deterministic JSONL responses; do not start a real Python process.

- [ ] **Step 2: Run `npm.cmd test` in `plugins/workflow-skill-router`.**

Expected: FAIL because `failGeneration` rejects every pending request on one timeout or abort.

- [ ] **Step 3: Split per-request expiry from process-generation failure.**

Implement an `expireRequest(requestId, error)` helper that clears only that request’s timer, removes that pending entry, and rejects only that Promise. Keep `failGeneration` for child `exit`, spawn/write failure, explicit close, and an unrecoverable protocol failure.

- [ ] **Step 4: Correct the startup message.**

Replace the automatic-switch claim with: `Python runtime 不可用；MCP server 無法啟動。請改用獨立安裝的 Skill-only 模式。` The server must still exit with code 78 because it did not actually activate a fallback.

- [ ] **Step 5: Update troubleshooting documents.**

Tell users to install/use the standalone Skill-only package after an MCP startup failure; do not state that the Plugin silently changes mode. State that a crashed bridge returns a request failure and may require a retry.

- [ ] **Step 6: Run `npm.cmd run check` in `plugins/workflow-skill-router`.**

Expected: all existing and new request-isolation tests pass; normal child-exit behavior still rejects remaining pending requests safely.

- [ ] **Step 7: Commit the Runtime reliability improvements.**

```text
git commit -m "fix(mcp): isolate request expiry and clarify fallback"
```

### Task 4: Convert release metadata, notes, and public copy to GA

**Files:**
- Modify: `scripts/release-publication-gate.py`
- Modify: `tests/test_github_workflows.py`
- Modify: `tests/test_public_surface_policy.py`
- Modify: `tests/test_v2_release_candidate.py`
- Modify: `tests/test_beta5_pilot_protocol.py`
- Modify: `README.md`
- Modify: `README.en.md`
- Create: `release/notes/v2.0.0.md`
- Modify: `CHANGELOG.md`
- Modify: `site/src/content/docs/contributing/release-process.md`
- Modify: `site/src/content/docs/zh-tw/contributing/release-process.md`
- Modify: `site/src/content/docs/contributing/roadmap.md`
- Modify: `site/src/content/docs/zh-tw/contributing/roadmap.md`

- [ ] **Step 1: Write release-gate tests for a GA tag.**

```python
metadata = publishable_metadata(version="2.0.0")
result = run_gate(metadata, trusted_revision)
self.assertEqual("v2.0.0", result.release_tag)
```

Also retain an explicit test that an unreviewed candidate lifecycle fails before tag creation.

- [ ] **Step 2: Run the focused release workflow suite.**

Run: `python -m unittest tests/test_github_workflows.py tests/test_v2_release_candidate.py -v`.

Expected: FAIL until GA naming and metadata assertions replace beta-specific assumptions.

- [ ] **Step 3: Generalize the gate from prerelease terminology.**

Make frozen metadata validation require only `v2_version`; remove `target_prerelease` coupling. Keep the existing strict tag regex, immutable V1.3.1 recovery requirement, trusted revision check, builder closure check, and metadata-only promotion model.

- [ ] **Step 4: Write GA release notes with bounded claims.**

Document the three execution modes, current local-ready boundaries, real-model evidence status, no-telemetry default, upgrade/recovery path, checksums/SBOM/provenance, and the fact that Host authority remains external.

- [ ] **Step 5: Replace stale candidate copy in README and bilingual site docs.**

Use `v2.0.0` only after the release metadata promotion occurs. Until then, the frozen source and docs must label themselves `GA candidate` and state that the final release needs attested model evidence. Do not announce performance, token savings, or full Host orchestration without evidence.

- [ ] **Step 6: Run documentation and release policy tests.**

Run: `python -m unittest tests/test_github_workflows.py tests/test_public_surface_policy.py tests/test_v2_release_candidate.py tests/test_release_copy.py -v`.

Expected: PASS with V1.3.1 recovery retained and no stale beta.5 product claim.

- [ ] **Step 7: Commit GA public surface changes.**

```text
git commit -m "docs(release): prepare v2.0.0 GA public surface"
```

### Task 5: Validate and freeze the GA candidate

**Files:**
- Modify: `release/version.json` only in the later metadata-only promotion commit
- Generate (ignored): `dist/release/`

- [ ] **Step 1: Run deterministic local gates from the candidate source.**

```text
python -m unittest discover -s tests -v
python -I -S -B scripts/build-release-artifacts.py --check
python plugins/workflow-skill-router/scripts/build-runtime.py --check
npm.cmd run check                 # plugins/workflow-skill-router
npm.cmd run assets:demo:check     # site
npm.cmd run assets:social:check   # site
npm.cmd run build                 # site
git diff --check
git status -sb
```

Expected: every command succeeds and the worktree is clean except for intentional commits.

- [ ] **Step 2: Commit and record the immutable candidate source revision.**

```text
git commit -m "chore(release): freeze v2.0.0 GA candidate"
git rev-parse HEAD
```

Expected: a single 40-character SHA to bind the evaluation manifest.

- [ ] **Step 3: Obtain explicit authorization for the new revision’s real-model smoke.**

Required authorization text must name the frozen SHA, `36 attempts / 42 turns`, and `gpt-5.6-sol`. Do not reuse authorization issued for an earlier beta source.

- [ ] **Step 4: Run the sealed beta-smoke and inspect only sanitized evidence.**

Expected: 36 attempts, 42 turns, zero hard violations, complete population accounting, correct consent transition behavior, and no unreviewed raw output in public artifacts.

- [ ] **Step 5: Create the reviewed evidence and maintainer attestation.**

The attestation must bind source SHA, evaluator adapter digest, evaluation manifest digest, timestamp, reviewer, evidence class, known limitations, and release decision. A failure remains a release block; it is not rewritten as a pass.

- [ ] **Step 6: Create a metadata-only publication promotion.**

Change `release_lifecycle` to `reviewed-attested-publishable`, set `release_source_revision` to the frozen candidate SHA, and do not alter the candidate’s release assets, notes, builder, or allowlists.

- [ ] **Step 7: Commit the reviewed publication binding.**

```text
git commit -m "chore(release): attest v2.0.0 GA candidate"
```

### Task 6: Publish and verify the official release

**Files:**
- No unreviewed source edits; use `.github/workflows/release-v2.yml` and the trusted GitHub release process.

- [ ] **Step 1: Push the reviewed branch and open a release PR.**

Run: `git push -u origin codex/router-beta4-optimization-plan`, then create a PR to `main`.

Expected: Windows, macOS, and Linux required checks are queued against the reviewed commits.

- [ ] **Step 2: Review required CI and merge only after all checks succeed.**

Expected: no bypass, no force-push, and remote branch protection evidence is retained.

- [ ] **Step 3: Dispatch `Release V2` from trusted `main`.**

Input: `CREATE_V2_RELEASE`.

Expected: workflow verifies metadata binding, builds source-derived ZIPs/SBOM/checksums, creates immutable `v2.0.0`, attests assets, and publishes a non-prerelease GitHub Release.

- [ ] **Step 4: Verify consumer installation paths.**

Verify the Plugin marketplace command against `--ref v2.0.0`, validate both Plugin and Skill ZIP checksums, run `doctor`, and run the extracted Plugin smoke test.

- [ ] **Step 5: Verify public surfaces.**

Confirm GitHub README, release notes, and deployed English/Traditional Chinese documentation return the GA version and no stale `prepared-local-candidate` copy. Announce only the bounded GA claim: a pre-execution Skill-selection layer, not a replacement for permissions, approvals, sandboxing, or production orchestration.

- [ ] **Step 6: Commit no post-release source changes without a separate follow-up branch.**

Expected: tag and provenance remain immutable; follow-up refinements start from a new branch.

## Self-review

- Spec coverage: Tasks 1–3 close every confirmed P0/P1 implementation gap; Task 4 removes beta-only public release semantics; Task 5 enforces independent behavior evidence; Task 6 covers protected remote publication, supply-chain assets, installation, and public verification.
- Placeholder scan: no `TODO`, unbounded implementation direction, or implied approval bypass is present.
- Type consistency: public input remains `use | only | all`; Core maps `all` to internal `REQUIRED_ALL`; the GA product version is `2.0.0`; `release_source_revision` always references the earlier frozen candidate SHA.
