from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.persistence.artifacts import (
    ArtifactProtectionError,
    ContentAddressedArtifactStore,
    ProtectedArtifact,
)
from workflow_skill_router.persistence.migrator import migrate


NOW = datetime(2026, 7, 15, tzinfo=timezone.utc)


class Clock:
    def now_utc(self):
        return NOW


class LifecycleSink:
    def __init__(self):
        self.receipts = []

    def append(self, receipt):
        self.receipts.append(receipt)


class Protector:
    def __init__(self, *, private=True, permissions=True, encrypt=True):
        self.private = private
        self.permissions = permissions
        self.encrypt = encrypt
        self.destroyed = []

    def verify_private_directory(self, root):
        return self.private

    def protect(self, plaintext, digest):
        stored = bytes(value ^ 0xA5 for value in plaintext) if self.encrypt else plaintext
        return ProtectedArtifact(stored, "test-encryption", f"key:{digest[-8:]}")

    def verify_effective_permissions(self, path):
        return self.permissions

    def open_verified(self, path, protection_ref):
        del protection_ref
        stored = path.read_bytes()
        return bytes(value ^ 0xA5 for value in stored) if self.encrypt else stored

    def destroy_key(self, protection_ref):
        self.destroyed.append(protection_ref)


class ArtifactStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name) / "artifacts"
        self.restricted = Path(self.directory.name) / "private"
        self.database = Path(self.directory.name) / "router.db"
        migrate(self.database)
        self.sink = LifecycleSink()

    def tearDown(self):
        self.directory.cleanup()

    def store(self, protector=None):
        return ContentAddressedArtifactStore(
            self.root,
            self.database,
            clock=Clock(),
            protector=protector,
            restricted_root=self.restricted if protector else None,
            lifecycle_sink=self.sink,
        )

    def test_identical_bytes_deduplicate_and_metadata_has_no_absolute_path(self):
        store = self.store()
        first = store.put_bytes("繁體中文".encode(), "text/plain", "internal", "test")
        second = store.put_bytes("繁體中文".encode(), "text/plain", "internal", "test")
        self.assertEqual(first, second)
        metadata = store.metadata(first.digest)
        self.assertFalse(Path(metadata.relative_path).is_absolute())
        self.assertEqual("繁體中文".encode(), store.open_verified(first.digest))

    def test_tampered_object_and_forged_digest_fail_closed(self):
        store = self.store()
        reference = store.put_bytes(b"safe", "text/plain", "internal", "test")
        path = self.root / store.metadata(reference.digest).relative_path
        path.write_bytes(b"tampered")
        with self.assertRaises(ArtifactProtectionError):
            store.open_verified(reference.digest)
        with self.assertRaises(ValueError):
            store.open_verified("sha256:../escape")

    def test_restricted_requires_verified_protector_and_never_stores_plaintext(self):
        with self.assertRaises(ArtifactProtectionError):
            self.store().put_bytes(b"secret", "text/plain", "restricted", "test")
        protector = Protector()
        store = self.store(protector)
        reference = store.put_bytes(b"secret", "text/plain", "restricted", "test")
        path = self.restricted / store.metadata(reference.digest).relative_path
        self.assertNotEqual(b"secret", path.read_bytes())
        self.assertEqual(b"secret", store.open_verified(reference.digest))

    def test_permission_failure_does_not_register_artifact(self):
        store = self.store(Protector(permissions=False))
        with self.assertRaises(ArtifactProtectionError):
            store.put_bytes(b"secret", "text/plain", "restricted", "test")
        self.assertEqual(0, store.count_metadata())

    def test_tombstone_and_crypto_erase_emit_lifecycle_and_block_open(self):
        protector = Protector()
        store = self.store(protector)
        reference = store.put_bytes(b"secret", "text/plain", "restricted", "test")
        tombstone = store.tombstone(reference.digest, "retention", "system")
        self.assertEqual("EVENT_PAYLOAD_TOMBSTONED", tombstone.event_type)
        with self.assertRaises(ArtifactProtectionError):
            store.open_verified(reference.digest)
        erased = store.crypto_erase(reference.digest, "user-request", "system")
        self.assertEqual("ARTIFACT_CRYPTO_ERASED", erased.event_type)
        self.assertTrue(protector.destroyed)
        self.assertEqual(
            ["EVENT_PAYLOAD_TOMBSTONED", "ARTIFACT_CRYPTO_ERASED"],
            [item.event_type for item in self.sink.receipts],
        )


if __name__ == "__main__":
    unittest.main()
