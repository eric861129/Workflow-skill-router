#!/usr/bin/env python3
"""Check local Markdown and MDX links without external dependencies."""

from __future__ import annotations

import argparse
import re
import sys
import urllib.parse
from pathlib import Path

MARKDOWN_EXTENSIONS = {".md", ".mdx"}
SKIP_DIR_NAMES = {
    ".astro",
    ".git",
    ".pagefind",
    "dist",
    "lighthouse-reports",
    "node_modules",
    "pagefind",
    "playwright-report",
    "test-results",
}
SITE_BASE_PATH = "/Workflow-skill-router/"
SITE_PUBLIC_PREFIXES = ("assets/", "og/", "favicon.svg", "robots.txt")

MARKDOWN_LINK_PATTERN = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")
HTML_LINK_PATTERN = re.compile(r"""\b(?:href|poster|src)=["']([^"']+)["']""", re.IGNORECASE)
FENCE_PATTERN = re.compile(r"^\s*(```|~~~)")


def should_skip_path(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True

    return any(part in SKIP_DIR_NAMES or part.startswith(".chrome") for part in relative.parts)


def iter_markdown_files(root: Path):
    for path in root.rglob("*"):
        if should_skip_path(path, root):
            continue
        if path.is_file() and path.suffix.lower() in MARKDOWN_EXTENSIONS:
            yield path


def strip_markdown_title(target: str) -> str:
    target = target.strip()
    if target.startswith("<") and ">" in target:
        return target[1 : target.index(">")].strip()
    if " " in target:
        return target.split(" ", 1)[0].strip()
    return target


def normalize_target(raw_target: str) -> str:
    target = strip_markdown_title(raw_target)
    target = target.split("#", 1)[0].split("?", 1)[0]
    return urllib.parse.unquote(target.strip())


def is_external_or_virtual(target: str) -> bool:
    lowered = target.lower()
    return (
        not target
        or target.startswith("#")
        or lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("mailto:")
        or lowered.startswith("tel:")
        or lowered.startswith("data:")
        or lowered.startswith("javascript:")
    )


def resolve_site_public_target(target: str, root: Path) -> Path | None:
    if not target.startswith(SITE_BASE_PATH):
        return None

    relative = target[len(SITE_BASE_PATH) :]
    if not relative.startswith(SITE_PUBLIC_PREFIXES):
        return None

    return root / "site" / "public" / relative


def resolve_target(source: Path, target: str, root: Path) -> Path | None:
    site_public_target = resolve_site_public_target(target, root)
    if site_public_target is not None:
        return site_public_target

    if target.startswith("/"):
        return None

    return source.parent / target


def iter_rendered_targets(path: Path):
    in_fence = False
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if FENCE_PATTERN.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        for pattern in (MARKDOWN_LINK_PATTERN, HTML_LINK_PATTERN):
            for match in pattern.finditer(line):
                yield line_number, match.group(1)


def check_links(root: Path) -> list[str]:
    issues: list[str] = []
    for path in iter_markdown_files(root):
        for line_number, raw_target in iter_rendered_targets(path):
            if is_external_or_virtual(raw_target):
                continue

            target = normalize_target(raw_target)
            if is_external_or_virtual(target):
                continue

            resolved = resolve_target(path, target, root)
            if resolved is None:
                continue
            if not resolved.exists():
                display_path = path.relative_to(root)
                issues.append(f"{display_path}:{line_number} -> {raw_target}")
    return issues


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Check local Markdown and MDX links.")
    parser.add_argument("path", nargs="?", default=".", help="Repository root to scan.")
    args = parser.parse_args(argv)

    root = Path(args.path).resolve()
    issues = check_links(root)
    if issues:
        print("Missing local Markdown links:")
        for issue in issues:
            print(issue)
        return 1

    print("OK: markdown local links passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
