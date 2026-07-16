from __future__ import annotations

import sys
import unittest

from workflow_skill_router.evaluation.adapter_registry import AdapterRegistry
from workflow_skill_router.evaluation.contracts import (
    EvalRunAuthorization,
    EvaluationIntegrityError,
    EvaluationProfile,
)


class AdapterRegistryTests(unittest.TestCase):
    def authorization(self, adapter_kind: str = "subprocess") -> EvalRunAuthorization:
        return EvalRunAuthorization(
            "auth-1",
            "session-1",
            "agent",
            "policy-1",
            EvaluationProfile.BEHAVIOR,
            adapter_kind,
            "sha256:suite",
        )

    def test_builds_subprocess_adapter_only_from_trusted_host_configuration(self):
        registry = AdapterRegistry.from_subprocess_command((sys.executable, "driver.py"))

        adapter = registry.require("subprocess", authorization=self.authorization())

        self.assertEqual("subprocess", adapter.kind)

    def test_rejects_duplicate_adapter_ids(self):
        adapter = object()
        with self.assertRaisesRegex(ValueError, "duplicate_adapter_id"):
            AdapterRegistry(("subprocess", adapter), ("subprocess", adapter))

    def test_rejects_authorization_for_a_different_server_owned_adapter(self):
        registry = AdapterRegistry.from_subprocess_command((sys.executable, "driver.py"))
        with self.assertRaisesRegex(EvaluationIntegrityError, "adapter_authorization_mismatch"):
            registry.require("subprocess", authorization=self.authorization("host-task"))

    def test_missing_adapter_is_explicit(self):
        with self.assertRaisesRegex(EvaluationIntegrityError, "adapter_not_configured"):
            AdapterRegistry().require("subprocess", authorization=self.authorization())


if __name__ == "__main__":
    unittest.main()
