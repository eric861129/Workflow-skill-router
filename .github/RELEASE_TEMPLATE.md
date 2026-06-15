# Release Notes

## Highlights

-

## Validation

```bash
python scripts/validate-router.py starter/workflow-skill-router
python scripts/validate-router.py examples/template-skill-catalog
python scripts/audit-public-readiness.py .
python -m unittest discover -s tests
```

Site:

```bash
cd site
npm run build
npm run audit:lighthouse
```

## Breaking Changes

- None expected.

## Download Links

- Blank SKILL package: https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-blank.zip
- Full template package: https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template.zip
- Clean template package: https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template-clean.zip

## Contributor Notes

- Keep examples public-safe.
- Keep routes bounded to one primary skill plus focused support.
- Run the scanner and routing evaluator before publishing.
