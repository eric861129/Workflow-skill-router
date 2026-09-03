from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from workflow_skill_router.memory import (
    MemoryScope,
    decode_memory_policy,
    resolve_effective_policy,
)
from workflow_skill_router.memory.policy_io import PolicyLoadResult, PolicySource
from workflow_skill_router.memory.store import MemoryStore, MemoryStoreError


def effective_policy(mode: str):
    policy = decode_memory_policy(
        {
            "schema_id": "workflow-skill-router/memory-policy",
            "schema_version": "1.0.0",
            "artifact_kind": "memory-policy",
            "policy_id": "personal:store-test",
            "scope": "personal",
            "mode": mode,
        }
    )
    personal = PolicyLoadResult(
        status="valid",
        source=PolicySource(
            scope=MemoryScope.PERSONAL,
            format="json",
            source_class="personal-policy",
            policy=policy,
        ),
        reason_codes=(),
    )
    return resolve_effective_policy(personal=personal, workspace=None)


def disabled_policy():
    return resolve_effective_policy(
        personal=PolicyLoadResult(
            status="missing",
            source=None,
            reason_codes=("personal-policy-missing",),
        ),
        workspace=None,
    )


class ExplodingPath:
    def __fspath__(self) -> str:
        raise AssertionError("disabled Memory must not inspect the filesystem")


class MemoryStoreTests(unittest.TestCase):
    def test_disabled_policy_returns_none_before_any_filesystem_access(self) -> None:
        store = MemoryStore.open_if_enabled(ExplodingPath(), disabled_policy())  # type: ignore[arg-type]

        self.assertIsNone(store)

    def test_enabled_policy_lazily_creates_a_separate_store_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "router-data"
            expected = data_dir / "memory" / "workflow-memory.sqlite3"

            store = MemoryStore.open_if_enabled(data_dir, effective_policy("observe"))
            self.assertIsNotNone(store)
            assert store is not None
            try:
                self.assertEqual(expected, store.database_path)
                self.assertTrue(expected.is_file())
                self.assertFalse(hasattr(store, "connection"))
                self.assertEqual(1, store.policy_snapshot_count())

                with sqlite3.connect(expected) as connection:
                    tables = {
                        str(row[0])
                        for row in connection.execute(
                            "SELECT name FROM sqlite_master WHERE type = 'table'"
                        )
                    }
                self.assertIn("memory_policy_snapshots", tables)
                self.assertNotIn("workflow_events", tables)
                self.assertFalse((data_dir / "workflow-state.sqlite3").exists())
            finally:
                store.close()

    def test_context_manager_closes_the_store_and_reopen_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "router-data"
            first = MemoryStore.open_if_enabled(data_dir, effective_policy("reviewed"))
            self.assertIsNotNone(first)
            assert first is not None
            snapshot_id = first.current_policy_snapshot.snapshot_id
            first.close()
            self.assertTrue(first.closed)

            with MemoryStore.open_if_enabled(
                data_dir,
                effective_policy("reviewed"),
            ) as reopened:
                self.assertEqual(snapshot_id, reopened.current_policy_snapshot.snapshot_id)
                self.assertEqual(1, reopened.policy_snapshot_count())
            self.assertTrue(reopened.closed)

    def test_store_rejects_linked_data_root_parent_and_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            linked_root = root / "linked-root"
            try:
                linked_root.symlink_to(target, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symbolic links are unavailable: {error}")

            with self.assertRaisesRegex(
                MemoryStoreError,
                "memory-data-root-link-forbidden",
            ):
                MemoryStore.open_if_enabled(
                    linked_root,
                    effective_policy("observe"),
                )

            data_dir = root / "router-data"
            data_dir.mkdir()
            outside = root / "outside"
            outside.mkdir()
            (data_dir / "memory").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(
                MemoryStoreError,
                "memory-store-parent-link-forbidden",
            ):
                MemoryStore.open_if_enabled(
                    data_dir,
                    effective_policy("observe"),
                )

            os.unlink(data_dir / "memory")
            (data_dir / "memory").mkdir()
            outside_file = outside / "external.sqlite3"
            outside_file.write_bytes(b"")
            database = data_dir / "memory" / "workflow-memory.sqlite3"
            database.symlink_to(outside_file)
            with self.assertRaisesRegex(
                MemoryStoreError,
                "memory-store-file-link-forbidden",
            ):
                MemoryStore.open_if_enabled(
                    data_dir,
                    effective_policy("observe"),
                )

    def test_purge_history_removes_memory_rows_but_preserves_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = MemoryStore.open_if_enabled(
                Path(directory) / "router-data",
                effective_policy("automatic"),
            )
            self.assertIsNotNone(store)
            assert store is not None
            try:
                self.assertEqual(1, store.policy_snapshot_count())
                removed = store.purge_history()
                self.assertEqual(
                    {
                        "memory_command_receipts": 0,
                        "route_feedback": 0,
                        "route_observations": 0,
                        "memory_policy_snapshots": 1,
                    },
                    removed,
                )
                self.assertEqual(0, store.policy_snapshot_count())
                self.assertEqual((1,), store.applied_migration_versions())
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
