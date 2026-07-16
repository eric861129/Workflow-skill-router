from dataclasses import FrozenInstanceError
from datetime import timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.capabilities.drift import compare_snapshots
from workflow_skill_router.capabilities.models import DriftKind
from workflow_skill_router.capabilities.snapshot import build_snapshot, rebuild_snapshot_id

try:
    from .test_merge import NOW, provider
except ImportError:
    from test_merge import NOW, provider


HOST = provider(authority="native-host")
FILESYSTEM = provider(authority="filesystem")


class SnapshotTests(unittest.TestCase):
    def test_all_providers_failed_builds_typed_stale_empty_snapshot(self) -> None:
        snapshot = build_snapshot((), "runtime-a", None, NOW)
        self.assertEqual((), snapshot.capabilities)
        self.assertTrue(snapshot.freshness.stale)
        self.assertEqual(NOW, snapshot.freshness.expires_at)

    def test_provider_completion_order_does_not_change_snapshot_id(self) -> None:
        first = build_snapshot((HOST, FILESYSTEM), "runtime-a", None, NOW)
        second = build_snapshot((FILESYSTEM, HOST), "runtime-a", None, NOW)
        self.assertEqual(first.snapshot_id, second.snapshot_id)

    def test_snapshot_time_or_previous_identity_changes_snapshot_id(self) -> None:
        first = build_snapshot((HOST,), "runtime-a", None, NOW)
        later = build_snapshot((HOST,), "runtime-a", first, NOW + timedelta(seconds=1))
        self.assertNotEqual(first.snapshot_id, later.snapshot_id)

    def test_snapshot_is_frozen(self) -> None:
        snapshot = build_snapshot((HOST, FILESYSTEM), "runtime-a", None, NOW)
        with self.assertRaises(FrozenInstanceError):
            snapshot.runtime_fingerprint = "changed"

    def test_nested_provenance_is_frozen_and_snapshot_hash_cannot_drift(self) -> None:
        snapshot = build_snapshot((HOST,), "runtime-a", None, NOW)
        before = snapshot.snapshot_id
        with self.assertRaises(FrozenInstanceError):
            snapshot.capabilities[0].provenance[0].provider_id = "forged"
        self.assertEqual(before, snapshot.snapshot_id)
        self.assertEqual(before, rebuild_snapshot_id(snapshot))

    def test_semantic_fingerprint_change_is_typed_drift(self) -> None:
        before = build_snapshot(
            (provider(authority="plugin-handshake", fingerprint="one"),),
            "runtime-a",
            None,
            NOW,
        )
        after = build_snapshot(
            (provider(authority="plugin-handshake", fingerprint="two"),),
            "runtime-a",
            before,
            NOW,
        )
        self.assertEqual(
            (DriftKind.SEMANTIC_METADATA,),
            tuple(item.kind for item in compare_snapshots(before, after)),
        )

    def test_trusted_installer_content_digest_change_is_typed_drift(self) -> None:
        before = build_snapshot(
            (
                provider(
                    authority="plugin-handshake",
                    installer_content_digest="sha256:" + "1" * 64,
                    installer_reason="verified-plugin-manifest",
                ),
            ),
            "runtime-a",
            None,
            NOW,
        )
        after = build_snapshot(
            (
                provider(
                    authority="plugin-handshake",
                    installer_content_digest="sha256:" + "2" * 64,
                    installer_reason="verified-plugin-manifest",
                ),
            ),
            "runtime-a",
            before,
            NOW,
        )
        self.assertEqual(
            (DriftKind.INSTRUCTION_CONTENT,),
            tuple(item.kind for item in compare_snapshots(before, after)),
        )


if __name__ == "__main__":
    unittest.main()
