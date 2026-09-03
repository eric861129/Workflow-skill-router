from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from workflow_skill_router.memory.policy_io import MemoryPolicyRepository


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


if __name__ == "__main__":
    unittest.main()
