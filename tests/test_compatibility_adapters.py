import unittest

from workflow_skill_router.compatibility import AdapterKey, AdapterRegistry, AdapterViolation
from workflow_skill_router.compatibility.legacy_v1 import LegacyV1ContractAdapter


class CompatibilityTests(unittest.TestCase):
    def test_registry_requires_full_schema_family(self):
        key = AdapterKey("workflow-skill-router/v1-predictions", "1.0", "routing-predictions")
        registry = AdapterRegistry({key: LegacyV1ContractAdapter()})
        self.assertEqual("contract-only", registry.resolve(key).adapt({})["evidence_class"])
        with self.assertRaisesRegex(AdapterViolation, "unsupported_artifact"):
            registry.resolve(AdapterKey("workflow-skill-router/v2", "1.0", "routing-predictions"))

    def test_ambiguous_alias_is_not_resolved_by_provider_order(self):
        registry = AdapterRegistry({}, {"shared-name": ("skill:a", "plugin:b")})
        with self.assertRaisesRegex(AdapterViolation, "ambiguous_alias"):
            registry.resolve_capability_alias("shared-name")


if __name__ == "__main__": unittest.main()
