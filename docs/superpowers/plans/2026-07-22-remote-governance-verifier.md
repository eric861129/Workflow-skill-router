# Remote Release Governance Verifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the repository's required `main` and `v2.*` GitHub governance executable, read-only, and fail-closed before a V2 release without pretending that a checked-in JSON file has configured GitHub.

**Architecture:** Keep `.github/branch-protection.json` as the versioned desired-state contract. Add a dependency-free Python verifier with pure parsing/validation functions and a thin `gh api` reader. The command must only issue `GET` requests; it compares the remote branch-protection and tag-ruleset payloads against the checked-in contract, then reports actionable violations. It does not create, update, or delete GitHub configuration.

**Tech Stack:** Python 3.11+, stdlib `json` / `subprocess` / `unittest`, GitHub CLI, GitHub REST API, Markdown.

## Global Constraints

- The verifier is read-only: it may run `gh api` only without an HTTP mutation method and must never send request bodies.
- A missing protection endpoint, an empty ruleset list, malformed JSON, missing `gh`, or a non-zero `gh` exit is a failure, never a pass.
- `main` must be protected, strict, require a pull request, require the three versioned checks in the manifest, reject force-push and deletion, and require conversation resolution.
- `v2.*` must have an active tag ruleset with `creation`, `update`, and `deletion` rules and a GitHub Actions Integration bypass (`actor_id` `15368`) so the trusted release workflow can create the tag.
- The manifest describes required configuration; it is not an assertion that the configuration is already live.
- Do not claim that the bypass has been verified until a live release-workflow rehearsal is separately authorized and reviewed.
- Preserve explicit release authorization, source-revision freeze, fail-closed behavior, and the existing `latest` / `latest-v2` channel boundaries.

---

### Task 1: Add the remote-governance contract and its read-only verifier

**Files:**

- Modify: `.github/branch-protection.json`
- Create: `scripts/remote_governance.py`
- Create: `scripts/verify-remote-governance.py`
- Create: `tests/test_remote_governance.py`

**Interfaces:**

- `load_contract(path: Path) -> dict[str, object]` validates the checked-in contract shape.
- `evaluate_governance(contract: dict[str, object], branch: dict[str, object], protection: dict[str, object], rulesets: list[dict[str, object]]) -> list[str]` returns stable, public-safe violation codes; an empty list means the captured payload meets this contract.
- `fetch_json(repo: str, endpoint: str) -> object` invokes only `gh api <endpoint>` with no mutation flags and decodes an object or list.
- `main(argv: Sequence[str] | None = None) -> int` accepts `--repo OWNER/REPO` and `--contract PATH`, prints `PASS: remote release governance matches contract` only when there are no violations, otherwise prints each violation and returns `1`.

- [ ] **Step 1: Write the failing tests for the pure contract evaluator**

```python
def test_evaluate_governance_accepts_complete_contract_payload() -> None:
    violations = remote_governance.evaluate_governance(
        contract(), protected_branch(), main_protection(), [v2_tag_ruleset()]
    )
    assert violations == []


def test_evaluate_governance_fails_closed_for_unprotected_main_and_missing_tag_ruleset() -> None:
    violations = remote_governance.evaluate_governance(
        contract(), {"protected": False}, {}, []
    )
    assert "main-not-protected" in violations
    assert "v2-tag-ruleset-missing" in violations
```

Add focused cases for a missing required check, direct-push allowance, force-push allowance, deletion allowance, missing conversation resolution, inactive tag ruleset, missing immutable-tag rule, and missing Integration `15368` bypass.

- [ ] **Step 2: Extend the versioned desired-state contract**

Add this exact `tag_protection` object alongside the existing `required_status_checks` object:

```json
"tag_protection": {
  "name": "Immutable V2 release tags",
  "target": "tag",
  "enforcement": "active",
  "ref_name_include": "refs/tags/v2.*",
  "required_rules": ["creation", "update", "deletion"],
  "required_bypass_actor": {
    "actor_id": 15368,
    "actor_type": "Integration",
    "bypass_mode": "always"
  }
}
```

Also add a `required_branch_controls` object with `pull_request`, `conversation_resolution`, `force_pushes`, and `deletions` booleans, set respectively to `true`, `true`, `false`, and `false`.

- [ ] **Step 3: Implement deterministic contract evaluation**

Use stable codes, including:

```python
MAIN_NOT_PROTECTED = "main-not-protected"
TAG_RULESET_MISSING = "v2-tag-ruleset-missing"
```

The evaluator must accept either GitHub's `required_status_checks.checks` entries (`context` plus `app_id`) or legacy `contexts` strings only when every expected context is present. It must treat an absent pull-request object as direct-push enabled. It must accept GitHub's boolean and `{ "enabled": bool }` variants for force-push/deletion fields. It must only select a tag ruleset when all of `target == "tag"`, `enforcement == "active"`, and `ref_name.include` contains `refs/tags/v2.*` are true.

- [ ] **Step 4: Implement the read-only CLI boundary**

The CLI fetches these endpoints only:

```text
repos/{owner}/{repo}/branches/{branch}
repos/{owner}/{repo}/branches/{branch}/protection
repos/{owner}/{repo}/rulesets
```

On an unavailable endpoint or non-object/list payload, return a stable `remote-governance-unavailable` failure without echoing tokens, command lines, filesystem paths, or raw remote payloads.

- [ ] **Step 5: Verify focused tests and the current live repository read-only**

Run:

```powershell
python -m unittest tests.test_remote_governance -v
python scripts/verify-remote-governance.py --repo eric861129/Workflow-skill-router
```

Expected: tests pass. The live command currently exits non-zero and reports missing `main` protection / `v2.*` ruleset until an administrator applies the configuration; that failure is the desired fail-closed behavior.

- [ ] **Step 6: Commit the implementation**

```powershell
git add .github/branch-protection.json scripts/remote_governance.py scripts/verify-remote-governance.py tests/test_remote_governance.py
git commit -m "feat(governance): verify remote release protections"
```

### Task 2: Document application, verification, and the release boundary

**Files:**

- Modify: `.github/RELEASE_TEMPLATE.md`
- Create: `docs/governance/remote-release-governance.md`
- Modify: `site/src/content/docs/contributing/release-process.md`
- Modify: `site/src/content/docs/zh-tw/contributing/release-process.md`
- Modify: `tests/test_github_workflows.py`

**Interfaces:**

- Maintainers run `python scripts/verify-remote-governance.py --repo eric861129/Workflow-skill-router` before the release dispatch.
- A failure means remote settings have not been proven; it does not alter GitHub and must block the release checklist.

- [ ] **Step 1: Add regression tests for the user-facing contract**

```python
def test_release_template_requires_remote_governance_verifier() -> None:
    template = (ROOT / ".github" / "RELEASE_TEMPLATE.md").read_text(encoding="utf-8")
    self.assertIn("verify-remote-governance.py", template)
    self.assertIn("does not change GitHub configuration", template)
```

Add assertions that the English and Traditional-Chinese release-process pages name the same command and state that a verification pass is not a live release-workflow rehearsal.

- [ ] **Step 2: Write the maintainer guide**

The guide must state the exact target: protected `main`; pull requests and the three check-run names; force-push/deletion blocked; active `v2.*` tag ruleset that blocks create/update/delete except the GitHub Actions Integration `15368`. It must give separate UI/API application instructions, mark them as privileged external changes, and end with the read-only verifier command. Do not provide a command that silently applies settings.

- [ ] **Step 3: Update the release template and bilingual release process**

Replace the hand-inspection snippet with the verifier command and say:

```text
This command is read-only. A pass confirms the captured configuration meets the checked-in contract; it does not prove a release workflow has successfully exercised the GitHub Actions bypass.
```

Keep the existing trusted-default-branch dispatch and source-revision freeze language unchanged.

- [ ] **Step 4: Run the focused documentation tests and checks**

Run:

```powershell
python -m unittest tests.test_remote_governance tests.test_github_workflows -v
python scripts/check-markdown-links.py .
python scripts/check-doc-parity.py
git diff --check
```

Expected: all pass; no malformed Markdown, parity drift, or whitespace error.

- [ ] **Step 5: Commit the documentation**

```powershell
git add .github/RELEASE_TEMPLATE.md docs/governance/remote-release-governance.md site/src/content/docs/contributing/release-process.md site/src/content/docs/zh-tw/contributing/release-process.md tests/test_github_workflows.py
git commit -m "docs(governance): make remote release checks executable"
```

### Task 3: Findings-first review and RC evidence refresh

**Files:**

- Modify: `.superpowers/sdd/progress.md` (ignored execution ledger)
- Create: `.superpowers/sdd/task26-remote-governance-review.md` (ignored review evidence)

- [ ] **Step 1: Review the complete Task 1–2 diff**

Verify that the CLI cannot issue non-GET GitHub mutations, missing remote state fails closed, the documentation never claims the ruleset is already applied, and the tag bypass remains explicitly unverified without a live rehearsal.

- [ ] **Step 2: Run the relevant final gate**

Run:

```powershell
python -m unittest tests.test_remote_governance tests.test_github_workflows tests.test_release_copy -v
python scripts/verify-remote-governance.py --repo eric861129/Workflow-skill-router
git diff --check origin/main..HEAD
```

Expected: unit tests pass; the live verifier remains a non-zero, documented precondition until GitHub settings are applied; diff check passes.

- [ ] **Step 3: Record only evidence actually produced**

Record the current remote result as `governance-unconfigured`, with the source branch and UTC timestamp. Do not create an attestation, declare branch protection active, push, open a PR, tag, or publish a release.

