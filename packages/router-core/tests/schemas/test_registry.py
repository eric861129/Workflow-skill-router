from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.schemas.artifacts import ArtifactEnvelope, canonical_json
from workflow_skill_router.schemas.errors import SchemaRegistryError
from workflow_skill_router.schemas.registry import SchemaRegistry


class SchemaRegistryTests(unittest.TestCase):
    def test_dispatch_requires_schema_id_version_and_kind(self) -> None:
        registry = SchemaRegistry()
        registry.register("workflow-skill-router/capability", "2.0.0-alpha.1", "capability", dict)
        document = {
            "schema_id": "workflow-skill-router/capability",
            "schema_version": "2.0.0-alpha.1",
            "artifact_kind": "capability",
            "artifact_id": "skill:sample/demo",
            "created_at": "2026-07-15T00:00:00Z",
            "payload": {"display_name": "繁體中文能力"},
        }
        self.assertEqual(document, registry.decode(document))
        document["artifact_kind"] = "capability-snapshot"
        with self.assertRaisesRegex(SchemaRegistryError, "未登錄的 schema contract"):
            registry.decode(document)

    def test_duplicate_registration_is_rejected(self) -> None:
        registry = SchemaRegistry()
        registry.register("x", "2", "kind", dict)
        with self.assertRaisesRegex(SchemaRegistryError, "重複登錄"):
            registry.register("x", "2", "kind", dict)

    def test_envelope_canonical_json_preserves_utf8(self) -> None:
        envelope = ArtifactEnvelope.from_dict({
            "schema_id": "x", "schema_version": "2", "artifact_kind": "kind",
            "artifact_id": "id", "created_at": "2026-07-15T00:00:00Z",
            "payload": {"說明": "能力"},
        })
        self.assertIn("能力", canonical_json(envelope.to_dict()))
        self.assertNotIn("\\u80fd", canonical_json(envelope.to_dict()))


if __name__ == "__main__":
    unittest.main()
