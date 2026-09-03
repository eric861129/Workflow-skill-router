from __future__ import annotations

from dataclasses import replace
from importlib import resources
import sqlite3
import unittest
from unittest.mock import patch

from workflow_skill_router.memory.migrator import (
    MemoryMigrationError,
    _load_migrations,
    migrate_memory_store,
)


EXPECTED_TABLES = {
    "memory_schema_migrations",
    "route_observations",
    "route_feedback",
    "memory_policy_snapshots",
    "memory_command_receipts",
}


class MemoryMigratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:", isolation_level=None)
        self.connection.execute("PRAGMA foreign_keys = ON")

    def tearDown(self) -> None:
        self.connection.close()

    def table_names(self) -> set[str]:
        rows = self.connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return {str(row[0]) for row in rows}

    def test_packaged_initial_migration_creates_only_the_separate_memory_schema(self) -> None:
        package = resources.files("workflow_skill_router.memory.migrations")
        names = sorted(
            item.name
            for item in package.iterdir()
            if item.is_file() and item.name.endswith(".sql")
        )
        self.assertEqual(["0001_observations.sql"], names)

        applied = migrate_memory_store(self.connection)

        self.assertEqual((1,), applied)
        self.assertEqual(EXPECTED_TABLES, self.table_names())
        self.assertNotIn("workflow_events", self.table_names())
        migration = _load_migrations()[0]
        self.assertNotIn("metadata_json", migration.sql)
        for forbidden in (
            "raw_prompt",
            "file_content",
            "tool_arguments",
            "secret_value",
        ):
            self.assertNotIn(forbidden, migration.sql.lower())

    def test_rerunning_migrations_is_idempotent(self) -> None:
        first = migrate_memory_store(self.connection)
        second = migrate_memory_store(self.connection)

        self.assertEqual((1,), first)
        self.assertEqual((), second)
        row = self.connection.execute(
            "SELECT version, name, checksum FROM memory_schema_migrations"
        ).fetchone()
        self.assertEqual(1, row[0])
        self.assertEqual("observations", row[1])
        self.assertRegex(str(row[2]), r"^[0-9a-f]{64}$")

    def test_applied_migration_checksum_drift_fails_closed(self) -> None:
        migrate_memory_store(self.connection)
        original = _load_migrations()[0]
        drifted = replace(original, checksum="0" * 64)

        with patch(
            "workflow_skill_router.memory.migrator._load_migrations",
            return_value=(drifted,),
        ):
            with self.assertRaisesRegex(
                MemoryMigrationError,
                "memory-migration-checksum-mismatch",
            ):
                migrate_memory_store(self.connection)

        self.assertEqual(
            1,
            self.connection.execute(
                "SELECT COUNT(*) FROM memory_schema_migrations"
            ).fetchone()[0],
        )
        self.assertEqual(EXPECTED_TABLES, self.table_names())


if __name__ == "__main__":
    unittest.main()
