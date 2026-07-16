from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.capabilities.codecs import encode_snapshot
from workflow_skill_router.persistence.artifacts import ContentAddressedArtifactStore
from workflow_skill_router.persistence.migrator import migrate
from workflow_skill_router.persistence.projections import CapabilitySnapshotProjection, ProjectionRunner
from workflow_skill_router.persistence.sqlite_store import SQLiteEventStore
from workflow_skill_router.schemas.artifacts import canonical_json_bytes
from workflow_skill_router.workflow.events import EventDraft

try:
    from ..routing.test_route_validator import SNAPSHOT
except ImportError:
    from routing.test_route_validator import SNAPSHOT


class Clock:
    def now_utc(self):
        return datetime(2026, 7, 15, tzinfo=timezone.utc)


class Ids:
    def new_event_id(self):
        return "snapshot-event-1"


class CapabilitySnapshotReplayTests(unittest.TestCase):
    def test_snapshot_rebuild_is_typed_and_materializes_all_risks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "router.db"
            migrate(database)
            artifacts = ContentAddressedArtifactStore(
                root / "artifacts", database, clock=Clock(),
            )
            document = encode_snapshot(SNAPSHOT).to_dict()
            reference = artifacts.put_bytes(
                canonical_json_bytes(document), "application/json", "internal", "discovery",
            )
            store = SQLiteEventStore(database, clock=Clock(), id_factory=Ids())
            store.append("runtime-context", "runtime-a", [EventDraft(
                event_type="CAPABILITY_SNAPSHOT_CREATED", actor="router-core", plan_revision=1,
                inline_payload={
                    "snapshot_id": SNAPSHOT.snapshot_id,
                    "schema_version": SNAPSHOT.schema_version,
                    "runtime_fingerprint": SNAPSHOT.runtime_fingerprint,
                    "provider_revisions": list(SNAPSHOT.provider_revisions),
                    "provider_failures": [],
                    "artifact_digest": reference.digest,
                },
                payload_ref=reference.digest, correlation_id="sync-1", causation_id=None,
            )], 0, "sync-1")
            runner = ProjectionRunner(database, artifact_store=artifacts)
            runner.catch_up()
            before = CapabilitySnapshotProjection(database).canonical_rows(SNAPSHOT.snapshot_id)
            restored = CapabilitySnapshotProjection(database).require(SNAPSHOT.snapshot_id)
            self.assertEqual(SNAPSHOT, restored)
            self.assertTrue(all(all(row[name] for name in (
                "availability_r0", "availability_r1", "availability_r2", "availability_r3",
            )) for row in before["capabilities"]))
            runner.rebuild()
            after = CapabilitySnapshotProjection(database).canonical_rows(SNAPSHOT.snapshot_id)
            self.assertEqual(before, after)

    def test_tampered_artifact_fails_without_advancing_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "router.db"
            migrate(database)
            artifacts = ContentAddressedArtifactStore(root / "artifacts", database, clock=Clock())
            reference = artifacts.put_bytes(b"{}", "application/json", "internal", "test")
            store = SQLiteEventStore(database, clock=Clock(), id_factory=Ids())
            store.append("runtime-context", "runtime-a", [EventDraft(
                "CAPABILITY_SNAPSHOT_CREATED", "router-core", 1,
                {"snapshot_id": "bad", "schema_version": "2.0.0-alpha.1",
                 "runtime_fingerprint": "runtime-a", "provider_revisions": [],
                 "provider_failures": [], "artifact_digest": reference.digest},
                reference.digest, "sync-bad", None,
            )], 0, "sync-bad")
            with self.assertRaises(Exception):
                ProjectionRunner(database, artifact_store=artifacts).catch_up()
            self.assertEqual(0, ProjectionRunner(database).checkpoint())


if __name__ == "__main__":
    unittest.main()
