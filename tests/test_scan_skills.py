from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_scanner():
    module_path = REPO_ROOT / "scripts" / "scan-skills.py"
    spec = importlib.util.spec_from_file_location("scan_skills", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ScanSkillsTests(unittest.TestCase):
    def run_scanner(self, roots: list[Path], *extra_args: str) -> tuple[int, dict, str, str, str]:
        scanner = load_scanner()
        with tempfile.TemporaryDirectory() as temp_dir:
            out_root = Path(temp_dir)
            json_path = out_root / "skill-index.json"
            markdown_path = out_root / "skill-index.md"
            warnings_path = out_root / "warnings.md"
            tree_path = out_root / "tree.md"
            code = scanner.main(
                [
                    *[str(root) for root in roots],
                    "--out",
                    str(json_path),
                    "--markdown",
                    str(markdown_path),
                    "--warnings",
                    str(warnings_path),
                    "--suggest-tree",
                    str(tree_path),
                    "--generated-at",
                    "2026-01-01T00:00:00Z",
                    *extra_args,
                ]
            )
            data = json.loads(json_path.read_text(encoding="utf-8")) if json_path.exists() else {}
            markdown = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
            warnings = warnings_path.read_text(encoding="utf-8") if warnings_path.exists() else ""
            tree = tree_path.read_text(encoding="utf-8") if tree_path.exists() else ""
            return code, data, markdown, warnings, tree

    def test_parse_skill_with_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_dir = root / "api-contract-review"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                """---
id: api-contract-review
name: API Contract Review
description: Review API request and response contracts for compatibility.
domains: [backend, frontend, api]
stages:
  - planning
  - debugging
triggers: [api change, contract mismatch]
exclusions: [database migration]
tags: [api, contract, compatibility]
visibility: public
---

# API Contract Review

Use this skill to review API compatibility.
""",
                encoding="utf-8",
            )

            code, data, markdown, warnings, tree = self.run_scanner([root])

            self.assertEqual(code, 0)
            self.assertEqual(data["generated_at"], "2026-01-01T00:00:00Z")
            self.assertEqual(data["skill_count"], 1)
            skill = data["skills"][0]
            self.assertEqual(skill["skill_id"], "api-contract-review")
            self.assertEqual(skill["name"], "API Contract Review")
            self.assertEqual(skill["domains"], ["backend", "frontend", "api"])
            self.assertTrue(skill["has_frontmatter"])
            self.assertIn("| api-contract-review | API Contract Review |", markdown)
            self.assertIn("# Skill Scan Warnings", warnings)
            self.assertIn("api-contract-review", tree)

    def test_parse_nested_metadata_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_dir = root / "architecture-designer"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                """---
name: architecture-designer
description: Design high-level software architecture and document tradeoffs.
metadata:
  author: public-maintainer
  version: "1.1.0"
  domain: architecture
  triggers: architecture, ADR, system design
  scope: planning
  related-skills: c4-architecture, code-documenter
---

# Architecture Designer
""",
                encoding="utf-8",
            )

            code, data, _markdown, warnings, tree = self.run_scanner([root])

            self.assertEqual(code, 0)
            skill = data["skills"][0]
            self.assertEqual(skill["domains"], ["architecture"])
            self.assertEqual(skill["stages"], ["planning"])
            self.assertEqual(skill["triggers"], ["architecture", "ADR", "system design"])
            self.assertEqual(skill["dependencies"], ["c4-architecture", "code-documenter"])
            self.assertNotIn("frontmatter field 'metadata'", warnings)
            self.assertIn("## Architecture", tree)

    def test_parse_markdown_without_frontmatter_and_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Markdown Publishing.md").write_text(
                """# Markdown Publishing

Publish markdown content with consistent links and headings.
""",
                encoding="utf-8",
            )
            folder = root / "fallback-folder"
            folder.mkdir()
            (folder / "SKILL.md").write_text(
                """This skill has no heading.

It still has enough body text for a fallback description.
""",
                encoding="utf-8",
            )

            code, data, _markdown, _warnings, _tree = self.run_scanner([root])

            self.assertEqual(code, 0)
            skills = {skill["skill_id"]: skill for skill in data["skills"]}
            self.assertEqual(skills["markdown-publishing"]["name"], "Markdown Publishing")
            self.assertEqual(skills["fallback-folder"]["name"], "fallback-folder")
            self.assertFalse(skills["fallback-folder"]["has_frontmatter"])

    def test_duplicate_skill_id_fails_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for folder_name in ["one", "two"]:
                skill_dir = root / folder_name
                skill_dir.mkdir()
                (skill_dir / "SKILL.md").write_text(
                    """---
id: duplicate-skill
name: Duplicate Skill
description: This description is long enough for duplicate testing.
tags: [dup]
triggers: [duplicate]
exclusions: [none]
domains: [testing]
stages: [planning]
---

# Duplicate Skill
""",
                    encoding="utf-8",
                )

            code, data, _markdown, warnings, _tree = self.run_scanner([root], "--fail-on-duplicates")

            self.assertEqual(code, 1)
            self.assertIn("duplicate skill_id", warnings)
            self.assertTrue(any("duplicate skill_id" in warning for warning in data["warnings"]))

    def test_public_safety_warnings_and_fail_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_dir = root / "private-marker"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                """# Private Marker

Contact admin@example.com or visit http://localhost:3000 before using this token-like value sk-test-1234567890abcdef.
""",
                encoding="utf-8",
            )

            code, data, _markdown, warnings, _tree = self.run_scanner([root], "--fail-on-private")

            self.assertEqual(code, 1)
            skill = data["skills"][0]
            self.assertTrue(any("email address" in warning for warning in skill["private_warnings"]))
            self.assertTrue(any("localhost URL" in warning for warning in skill["private_warnings"]))
            self.assertIn("private-marker", warnings)

    def test_quality_warnings_for_short_description_and_missing_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_dir = root / "thin-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                """---
name: Thin Skill
description: Short.
---

# Thin Skill
""",
                encoding="utf-8",
            )

            code, data, _markdown, warnings, _tree = self.run_scanner([root])

            self.assertEqual(code, 0)
            quality_warnings = data["skills"][0]["quality_warnings"]
            self.assertTrue(any("description is short" in warning for warning in quality_warnings))
            self.assertTrue(any("missing triggers" in warning for warning in quality_warnings))
            self.assertIn("thin-skill", warnings)

    def test_overlap_warning_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for skill_id in ["api-review-one", "api-review-two"]:
                skill_dir = root / skill_id
                skill_dir.mkdir()
                (skill_dir / "SKILL.md").write_text(
                    f"""---
id: {skill_id}
name: {skill_id}
description: Review API contracts and route compatibility issues.
domains: [api, backend]
stages: [planning]
triggers: [api contract, compatibility]
exclusions: [frontend visual design]
tags: [api, contract]
---

# {skill_id}
""",
                    encoding="utf-8",
                )

            code, data, _markdown, warnings, _tree = self.run_scanner([root])

            self.assertEqual(code, 0)
            self.assertIn("overlap", warnings)
            self.assertTrue(any("overlap" in warning for warning in data["warnings"]))


if __name__ == "__main__":
    unittest.main()
