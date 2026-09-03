from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from workflow_skill_router.memory.policy_io import MemoryPolicyRepository


def workspace_policy() -> dict[str, object]:
    return {
        "schema_id": "workflow-skill-router/memory-policy",
        "schema_version": "1.0.0",
        "artifact_kind": "memory-policy",
        "policy_id": "workspace:linked-root",
        "scope": "workspace",
        "mode": "observe",
    }


class MissingWorkspacePolicyTests(unittest.TestCase):
    def test_missing_workspace_policy_does_not_create_workspace_or_router_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "missing-state"
            workspace = root / "missing-workspace"

            result = MemoryPolicyRepository(data_dir).inspect_workspace(workspace)

            self.assertEqual("missing", result.status)
            self.assertIsNone(result.source)
            self.assertEqual(("workspace-policy-missing",), result.reason_codes)
            self.assertFalse(data_dir.exists())
            self.assertFalse(workspace.exists())
            public = json.dumps(result.to_public_dict(), sort_keys=True)
            self.assertNotIn(str(data_dir), public)
            self.assertNotIn(str(workspace), public)

    def test_linked_workspace_root_is_rejected_before_policy_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real_workspace = root / "real-workspace"
            policy_dir = real_workspace / ".codex"
            policy_dir.mkdir(parents=True)
            (policy_dir / "workflow-memory.json").write_text(
                json.dumps(workspace_policy()),
                encoding="utf-8",
            )
            linked_workspace = root / "linked-workspace"
            try:
                linked_workspace.symlink_to(real_workspace, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symbolic links are unavailable on this runner")

            result = MemoryPolicyRepository(root / "state").inspect_workspace(
                linked_workspace
            )

            self.assertEqual("invalid", result.status)
            self.assertIsNone(result.source)
            self.assertIn("policy-source-link-forbidden", result.reason_codes)
            public = json.dumps(result.to_public_dict(), sort_keys=True)
            self.assertNotIn(str(real_workspace), public)
            self.assertNotIn(str(linked_workspace), public)


if __name__ == "__main__":
    unittest.main()
