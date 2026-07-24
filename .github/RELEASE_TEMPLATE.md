# Workflow Skill Router V2 Release

## Highlights

-

## Compatibility

- V2 tag: `v2.*`
- Plugin/MCP runtime:
- SKILL-only package:
- V1 compatibility impact:

## Verified Evidence

- Router Core and Plugin/MCP tests:
- Documentation site smoke, visual, accessibility, and Lighthouse gates:
- Model evaluation evidence status (`manual-required`, `review-required`, or `attested`):
- Authorized model quota and attempt budget, if behavior evidence was produced:

## Repository Governance

- [ ] `.github/branch-protection.json` still matches the protected `main` branch.
- [ ] Required checks use the Check Run display names, not workflow job IDs.
- [ ] A pull request passed every required check and merged without an administrator bypass.

The versioned contract currently requires these GitHub Actions checks:

- `Core, documentation, and policy contracts`
- `Site visual regression`
- `Required cross-platform V2 gate`

Verify remote release governance before the release dispatch:

```bash
python scripts/verify-remote-governance.py --repo eric861129/Workflow-skill-router
python scripts/verify-plugin-distribution-governance.py
```

This command is read-only and does not change GitHub configuration. A pass confirms
the captured configuration meets the checked-in contract; it does not prove a
release workflow has successfully exercised the Release GitHub App bypass. A failure
means remote settings have not been proven and blocks this release checklist.

For privileged UI or API application of the remote settings, see
[`docs/governance/remote-release-governance.md`](../docs/governance/remote-release-governance.md).

- [ ] Plugin changes originate only in the canonical repository.
- [ ] The generated target `main` requires the HOL Scanner check and the target
      `refs/tags/v*` ruleset is active.
- [ ] No target file, branch history, or tag was manually repaired.

## Supply Chain

- [ ] Artifacts were built from the clean tagged source revision.
- [ ] Deterministic build comparison passed.
- [ ] `checksums.sha256` covers every release asset.
- [ ] SPDX SBOM is attached.
- [ ] Source provenance is marked publishable and names the tagged revision.
- [ ] GitHub artifact attestation was generated and verification instructions were tested.
- [ ] No tracked `downloads/` artifact was used as a release source.

Verification:

```bash
gh attestation verify <downloaded-asset> --repo eric861129/Workflow-skill-router
```

## Security and Limitations

- Security changes:
- Known limitations:
- Migration notes:

## Publication Approvals

- [ ] Release authority approved this tag.
- [ ] Security-sensitive changes were cleared for disclosure.
- [ ] Behavior evidence promotion was independently reviewed.
- [ ] Stable-channel movement and Pages deployment were separately authorized when applicable.
