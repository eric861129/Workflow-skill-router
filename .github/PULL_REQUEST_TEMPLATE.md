## Contract Changed

Describe the user-visible behavior, security boundary, or documentation contract changed by this pull request.

- 

## Surface

- [ ] Router Core
- [ ] Plugin / MCP
- [ ] Evaluation
- [ ] SKILL-only
- [ ] Documentation site
- [ ] Documentation-only / governance
- [ ] Release supply chain

## Evidence

- Focused test or reproduction:
- Full local gate run:
- Remaining limitation:

## Routing Context

If routing behavior changed, include:

- task size and phase:
- available Skills:
- user-specified Skill, if any:
- expected primary and supporting Skills:
- consent state:

## Safety Checklist

- [ ] New behavior has a focused regression test.
- [ ] `python scripts/check-markdown-links.py .` passes.
- [ ] `python -m unittest discover -s tests` passes, or the reason is documented.
- [ ] Plugin/MCP changes pass the bundled runtime and MCP smoke checks.
- [ ] Site changes pass build and relevant smoke/visual checks in both locales.
- [ ] No credentials, private prompts, SQLite state, internal paths, or unsanitized traces are included.
- [ ] Fixtures and contract tests are not described as real model behavior.
- [ ] CI does not invoke a live model or consume model quota.
- [ ] Release artifacts are generated from source and are not edited in `downloads/`.
