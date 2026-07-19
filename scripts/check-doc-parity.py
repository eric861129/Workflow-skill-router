from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC_ROOT = ROOT / "site" / "src" / "content" / "docs"

REQUIRED_ROUTES = {
    "guides/install-plugin.md",
    "guides/install-skill.md",
    "guides/migrate-v1-to-v2.md",
    "concepts/runtime-capability-discovery.md",
    "concepts/routing-envelopes.md",
    "concepts/explicit-skill-lock.md",
    "concepts/phase-state-machine.md",
    "concepts/managed-goals.md",
    "concepts/evaluation-evidence.md",
    "reference/mcp-tools.mdx",
    "reference/cli.md",
    "reference/local-state.md",
    "reference/security-boundaries.md",
    "contributing/release-process.md",
    "contributing/roadmap.md",
}
CONCEPT_ROUTES = {path for path in REQUIRED_ROUTES if path.startswith("concepts/")}
CONCEPT_ANCHORS = {
    "problem",
    "contract",
    "example",
    "failure-modes",
    "security-boundary",
    "verify",
}
ANCHOR_PATTERN = re.compile(r"\bid=[\"']([a-z0-9-]+)[\"']")


def _routes(root: Path, *, locale: str) -> dict[str, Path]:
    base = root / locale if locale else root
    result: dict[str, Path] = {}
    for path in base.rglob("*"):
        if path.suffix not in {".md", ".mdx"}:
            continue
        if not locale and path.relative_to(base).parts[0] == "zh-tw":
            continue
        result[path.relative_to(base).as_posix()] = path
    return result


def check_parity(root: Path = DOC_ROOT) -> list[str]:
    english = _routes(root, locale="")
    traditional_chinese = _routes(root, locale="zh-tw")
    errors: list[str] = []
    for route in sorted(set(english) - set(traditional_chinese)):
        errors.append(f"missing zh-tw route: {route}")
    for route in sorted(set(traditional_chinese) - set(english)):
        errors.append(f"missing English route: {route}")
    for route in sorted(REQUIRED_ROUTES - set(english)):
        errors.append(f"missing required V2 route: {route}")

    for route in sorted(CONCEPT_ROUTES & set(english) & set(traditional_chinese)):
        en_ids = set(ANCHOR_PATTERN.findall(english[route].read_text("utf-8")))
        zh_ids = set(ANCHOR_PATTERN.findall(traditional_chinese[route].read_text("utf-8")))
        missing = CONCEPT_ANCHORS - en_ids
        if missing:
            errors.append(f"{route} missing canonical anchors: {sorted(missing)}")
        if en_ids != zh_ids:
            errors.append(f"{route} locale anchor mismatch: en={sorted(en_ids)} zh-tw={sorted(zh_ids)}")
    return errors


def main() -> int:
    errors = check_parity()
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
