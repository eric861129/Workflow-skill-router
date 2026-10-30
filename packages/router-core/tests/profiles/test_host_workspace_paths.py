from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.cli import main
from workflow_skill_router.hosts import (
    CLAUDE_CODE,
    CODEX,
    HOST_ENVIRONMENT_VARIABLE,
    HostProfileError,
    current_host,
    workspace_profile_path,
)
from workflow_skill_router.memory.policy_io import MemoryPolicyRepository
from workflow_skill_router.profiles.contract import RoutingProfileContractError
from workflow_skill_router.profiles.storage import RoutingProfileRepository

if __package__:
    from .test_contract import profile_document
else:
    from test_contract import profile_document


def write_workspace_profile(workspace: Path, directory: str, profile_id: str) -> Path:
    document = profile_document(scope="workspace")
    document["profile_id"] = profile_id
    path = workspace / directory / "workflow-skill-router.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


def write_workspace_policy(workspace: Path, filename: str, mode: str) -> Path:
    path = workspace / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema_id": "workflow-skill-router/memory-policy",
        "schema_version": "1.0.0",
        "artifact_kind": "memory-policy",
        "policy_id": "workspace:test",
        "scope": "workspace",
        "mode": mode,
    }), encoding="utf-8")
    return path


class HostSelectionTests(unittest.TestCase):
    def test_unset_or_blank_host_keeps_the_codex_default(self) -> None:
        self.assertIs(CODEX, current_host({}))
        self.assertIs(CODEX, current_host({HOST_ENVIRONMENT_VARIABLE: "  "}))

    def test_claude_code_host_is_selected_by_exact_identifier(self) -> None:
        self.assertIs(CLAUDE_CODE, current_host({HOST_ENVIRONMENT_VARIABLE: "claude-code"}))

    def test_unknown_host_fails_closed(self) -> None:
        for value in ("claude", "Claude-Code", "../codex"):
            with self.subTest(value=value), self.assertRaises(HostProfileError):
                current_host({HOST_ENVIRONMENT_VARIABLE: value})

    def test_missing_profiles_resolve_to_the_host_native_location(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            self.assertEqual(
                workspace / ".codex/workflow-skill-router.json",
                workspace_profile_path(workspace, CODEX),
            )
            self.assertEqual(
                workspace / ".claude/workflow-skill-router.json",
                workspace_profile_path(workspace, CLAUDE_CODE),
            )


class HostWorkspaceProfileTests(unittest.TestCase):
    def load_ids(self, root: Path, workspace: Path, host) -> tuple[str, ...]:
        loaded = RoutingProfileRepository(root / "state", host=host).load_layers(
            workspace_root=workspace
        )
        return tuple(item.profile_id for item in loaded)

    def test_codex_host_never_reads_the_claude_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "repo"
            write_workspace_profile(workspace, ".claude", "workspace:claude-delivery")

            self.assertEqual((), self.load_ids(root, workspace, CODEX))

    def test_claude_host_prefers_its_native_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "repo"
            write_workspace_profile(workspace, ".codex", "workspace:codex-delivery")
            write_workspace_profile(workspace, ".claude", "workspace:claude-delivery")

            self.assertEqual(("workspace:claude-delivery",), self.load_ids(root, workspace, CLAUDE_CODE))
            self.assertEqual(("workspace:codex-delivery",), self.load_ids(root, workspace, CODEX))

    def test_claude_host_falls_back_to_the_shared_codex_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "repo"
            write_workspace_profile(workspace, ".codex", "workspace:codex-delivery")
            (workspace / ".claude").mkdir()

            self.assertEqual(("workspace:codex-delivery",), self.load_ids(root, workspace, CLAUDE_CODE))

    def test_claude_native_profile_link_fails_closed_without_falling_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "repo"
            write_workspace_profile(workspace, ".codex", "workspace:codex-delivery")
            source = write_workspace_profile(root / "outside", ".", "workspace:outside-delivery")
            link = workspace / ".claude/workflow-skill-router.json"
            link.parent.mkdir(parents=True)
            try:
                link.symlink_to(source)
            except (OSError, NotImplementedError):
                self.skipTest("symbolic links are unavailable on this runner")

            with self.assertRaises(RoutingProfileContractError):
                self.load_ids(root, workspace, CLAUDE_CODE)


class HostWorkspacePolicyTests(unittest.TestCase):
    def test_claude_host_reads_native_policy_before_codex_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "repo"
            write_workspace_policy(workspace, ".codex/workflow-memory.json", "observe")
            write_workspace_policy(workspace, ".claude/workflow-memory.json", "reviewed")

            claude = MemoryPolicyRepository(root / "state", host=CLAUDE_CODE).inspect_workspace(workspace)
            codex = MemoryPolicyRepository(root / "state", host=CODEX).inspect_workspace(workspace)

            assert claude.source is not None and codex.source is not None
            self.assertEqual("reviewed", claude.source.policy.mode.value)
            self.assertEqual("observe", codex.source.policy.mode.value)

    def test_claude_host_falls_back_to_codex_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "repo"
            write_workspace_policy(workspace, ".codex/workflow-memory.json", "observe")

            result = MemoryPolicyRepository(root / "state", host=CLAUDE_CODE).inspect_workspace(workspace)

            self.assertEqual("valid", result.status)

    def test_ambiguous_native_policy_does_not_fall_through(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "repo"
            write_workspace_policy(workspace, ".claude/workflow-memory.json", "observe")
            write_workspace_policy(workspace, ".claude/workflow-memory.yml", "observe")
            write_workspace_policy(workspace, ".codex/workflow-memory.json", "observe")

            result = MemoryPolicyRepository(root / "state", host=CLAUDE_CODE).inspect_workspace(workspace)

            self.assertEqual("ambiguous", result.status)
            self.assertIsNone(result.source)

    def test_missing_policy_in_every_host_directory_stays_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "repo"
            workspace.mkdir()

            result = MemoryPolicyRepository(root / "state", host=CLAUDE_CODE).inspect_workspace(workspace)

            self.assertEqual("missing", result.status)
            self.assertEqual(("workspace-policy-missing",), result.reason_codes)


class HostCliTests(unittest.TestCase):
    def test_bridge_refuses_to_start_with_an_unknown_host(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {HOST_ENVIRONMENT_VARIABLE: "unknown-host"}
        ):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = main(["serve-jsonl", "--database", str(Path(directory) / "router.sqlite3")])

            self.assertEqual(78, code)
            self.assertIn(HOST_ENVIRONMENT_VARIABLE, stderr.getvalue())
            self.assertFalse((Path(directory) / "router.sqlite3").exists())

    def test_doctor_reports_the_configured_host(self) -> None:
        with mock.patch.dict(os.environ, {HOST_ENVIRONMENT_VARIABLE: "claude-code"}):
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(0, main(["doctor"]))

        self.assertEqual("claude-code", json.loads(stdout.getvalue())["host"])


if __name__ == "__main__":
    unittest.main()
