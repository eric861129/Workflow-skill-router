from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from workflow_skill_router.memory import MemoryMode, MemoryScope
from workflow_skill_router.memory.policy_io import (
    MemoryPolicyRepository,
    default_router_data_dir,
)


def policy_document(*, scope: str = "personal", mode: str = "reviewed") -> dict[str, object]:
    return {
        "schema_id": "workflow-skill-router/memory-policy",
        "schema_version": "1.0.0",
        "artifact_kind": "memory-policy",
        "policy_id": f"{scope}:test",
        "scope": scope,
        "mode": mode,
    }


def policy_yaml(*, scope: str = "personal", mode: str = "reviewed") -> str:
    return (
        "schema_id: workflow-skill-router/memory-policy\n"
        "schema_version: 1.0.0\n"
        "artifact_kind: memory-policy\n"
        f"policy_id: {scope}:test\n"
        f"scope: {scope}\n"
        f"mode: {mode}\n"
    )


class MemoryPolicyRepositoryTests(unittest.TestCase):
    def test_missing_personal_policy_is_non_creating_and_public_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "missing-data-root"
            result = MemoryPolicyRepository(data_dir).inspect_personal()

            self.assertEqual("missing", result.status)
            self.assertIsNone(result.source)
            self.assertEqual(("personal-policy-missing",), result.reason_codes)
            self.assertFalse(data_dir.exists())
            self.assertNotIn(str(data_dir), json.dumps(result.to_public_dict()))

    def test_each_supported_source_format_loads_from_the_fixed_location(self) -> None:
        fixtures = {
            "json": json.dumps(policy_document()),
            "yaml": policy_yaml(),
            "yml": policy_yaml(),
        }
        for extension, content in fixtures.items():
            with self.subTest(extension=extension), tempfile.TemporaryDirectory() as directory:
                data_dir = Path(directory) / "state"
                config = data_dir / "config"
                config.mkdir(parents=True)
                (config / f"workflow-memory.{extension}").write_text(content, encoding="utf-8")

                result = MemoryPolicyRepository(data_dir).inspect_personal()

                self.assertEqual("valid", result.status)
                self.assertIsNotNone(result.source)
                assert result.source is not None
                self.assertEqual(extension if extension == "json" else "yaml", result.source.format)
                self.assertEqual("personal-policy", result.source.source_class)
                self.assertEqual(MemoryMode.REVIEWED, result.source.policy.mode)
                self.assertEqual(MemoryScope.PERSONAL, result.source.policy.scope)
                public = json.dumps(result.to_public_dict())
                self.assertNotIn(str(data_dir), public)
                self.assertNotIn("source_path", public)

    def test_multiple_supported_formats_are_ambiguous_instead_of_ordered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "state"
            config = data_dir / "config"
            config.mkdir(parents=True)
            (config / "workflow-memory.json").write_text(
                json.dumps(policy_document()), encoding="utf-8"
            )
            (config / "workflow-memory.yaml").write_text(policy_yaml(), encoding="utf-8")

            result = MemoryPolicyRepository(data_dir).inspect_personal()

            self.assertEqual("ambiguous", result.status)
            self.assertIsNone(result.source)
            self.assertEqual(("ambiguous-memory-policy",), result.reason_codes)

    def test_invalid_sources_fail_closed_with_sanitized_reason_codes(self) -> None:
        cases: list[tuple[str, bytes | None]] = [
            ("oversize", b"x" * (64 * 1024 + 1)),
            ("invalid-utf8", b"\xff\xfe"),
            ("wrong-scope", json.dumps(policy_document(scope="workspace")).encode("utf-8")),
        ]
        for name, content in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                data_dir = Path(directory) / "state"
                config = data_dir / "config"
                config.mkdir(parents=True)
                target = config / "workflow-memory.json"
                assert content is not None
                target.write_bytes(content)

                result = MemoryPolicyRepository(data_dir).inspect_personal()

                self.assertEqual("invalid", result.status)
                self.assertIsNone(result.source)
                self.assertTrue(result.reason_codes)
                self.assertNotIn(str(data_dir), json.dumps(result.to_public_dict()))

    def test_directory_and_symbolic_link_sources_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "directory-case"
            target = data_dir / "config" / "workflow-memory.json"
            target.mkdir(parents=True)
            result = MemoryPolicyRepository(data_dir).inspect_personal()
            self.assertEqual("invalid", result.status)
            self.assertIn("policy-source-not-regular", result.reason_codes)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "outside.json"
            source.write_text(json.dumps(policy_document()), encoding="utf-8")
            target = root / "state" / "config" / "workflow-memory.json"
            target.parent.mkdir(parents=True)
            try:
                target.symlink_to(source)
            except (OSError, NotImplementedError):
                self.skipTest("symbolic links are unavailable on this runner")
            result = MemoryPolicyRepository(root / "state").inspect_personal()
            self.assertEqual("invalid", result.status)
            self.assertIn("policy-source-link-forbidden", result.reason_codes)

    def test_workspace_policy_uses_only_the_fixed_dot_codex_location(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "state"
            workspace = root / "workspace"
            policy = workspace / ".codex" / "workflow-memory.yaml"
            policy.parent.mkdir(parents=True)
            policy.write_text(policy_yaml(scope="workspace", mode="observe"), encoding="utf-8")

            result = MemoryPolicyRepository(data_dir).inspect_workspace(workspace)

            self.assertEqual("valid", result.status)
            assert result.source is not None
            self.assertEqual("workspace-policy", result.source.source_class)
            self.assertEqual(MemoryMode.OBSERVE, result.source.policy.mode)
            self.assertFalse(data_dir.exists())
            self.assertNotIn(str(workspace), json.dumps(result.to_public_dict()))

    def test_explicit_validation_reuses_the_safe_contract_without_returning_a_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "candidate.yaml"
            source.write_text(policy_yaml(), encoding="utf-8")

            policy = MemoryPolicyRepository(Path(directory) / "state").validate_explicit_file(
                source,
                MemoryScope.PERSONAL,
            )

            self.assertEqual("personal:test", policy.policy_id)
            self.assertEqual(MemoryMode.REVIEWED, policy.mode)

    def test_default_data_root_is_platform_specific_and_environment_override_wins(self) -> None:
        home = Path("/home/tester")
        self.assertEqual(
            Path("/state/codex/workflow-skill-router"),
            default_router_data_dir(
                platform="linux",
                environment={"XDG_STATE_HOME": "/state"},
                home=home,
            ),
        )
        self.assertEqual(
            Path("/custom/router"),
            default_router_data_dir(
                platform="linux",
                environment={"WORKFLOW_SKILL_ROUTER_DATA_DIR": "/custom/router"},
                home=home,
            ),
        )
        windows = default_router_data_dir(
            platform="win32",
            environment={"LOCALAPPDATA": r"C:\Users\tester\AppData\Local"},
            home=Path(r"C:\Users\tester"),
        )
        self.assertTrue(str(windows).endswith(os.path.join("Codex", "workflow-skill-router")))


if __name__ == "__main__":
    unittest.main()
