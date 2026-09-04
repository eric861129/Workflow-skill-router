from __future__ import annotations

from contextlib import closing
from dataclasses import replace
from importlib import resources
from pathlib import Path
import sqlite3
import tempfile
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
    "route_observation_documents",
    "memory_command_results",
    "route_feedback_events",
    "memory_admin_commands",
    "workflow_patterns",
    "workflow_candidates",
    "candidate_suppressions",
    "profile_update_proposals",
    "profile_update_proposal_receipts",
    "profile_revisions",
    "profile_materialization_receipts",
    "profile_recovery_markers",
    "rollback_proposal_sources",
}


class MemoryMigratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.database = root / "memory" / "workflow-memory.sqlite3"
        self.database.parent.mkdir()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def table_names(self) -> set[str]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        return {str(row[0]) for row in rows}

    def test_public_migrator_does_not_create_a_missing_parent(self) -> None:
        root = Path(self.temporary_directory.name)
        missing_parent = root / "missing-parent"
        database = missing_parent / "workflow-memory.sqlite3"

        with self.assertRaisesRegex(
            MemoryMigrationError,
            "memory-migration-parent-unavailable",
        ):
            migrate_memory_store(database)

        self.assertFalse(missing_parent.exists())
        self.assertFalse(database.exists())

    def test_packaged_initial_migration_creates_only_the_separate_memory_schema(self) -> None:
        package = resources.files("workflow_skill_router.memory.migrations")
        names = sorted(
            item.name
            for item in package.iterdir()
            if item.is_file() and item.name.endswith(".sql")
        )
        self.assertEqual([
            "0001_observations.sql",
            "0002_route_observation_documents.sql",
            "0003_route_feedback_history.sql",
            "0004_candidates.sql",
            "0005_profile_update_proposals.sql",
            "0006_profile_revisions.sql",
        ], names)

        result = migrate_memory_store(self.database)

        self.assertIsNone(result)
        self.assertEqual(EXPECTED_TABLES, self.table_names())
        self.assertNotIn("workflow_events", self.table_names())
        migrations = _load_migrations()
        combined_sql = "\n".join(item.sql for item in migrations)
        self.assertNotIn("metadata_json", combined_sql)
        for forbidden in (
            "raw_prompt",
            "file_content",
            "tool_arguments",
            "secret_value",
        ):
            self.assertNotIn(forbidden, combined_sql.lower())

    def test_rerunning_migrations_is_idempotent(self) -> None:
        first = migrate_memory_store(self.database)
        second = migrate_memory_store(self.database)

        self.assertIsNone(first)
        self.assertIsNone(second)
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT version, name, checksum FROM memory_schema_migrations ORDER BY version"
            ).fetchall()
        self.assertEqual([
            (1, "observations"),
            (2, "route_observation_documents"),
            (3, "route_feedback_history"),
            (4, "candidates"),
            (5, "profile_update_proposals"),
            (6, "profile_revisions"),
        ], [
            (int(row[0]), str(row[1])) for row in rows
        ])
        for row in rows:
            self.assertRegex(str(row[2]), r"^[0-9a-f]{64}$")

    def test_applied_migration_checksum_drift_fails_closed(self) -> None:
        migrate_memory_store(self.database)
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
                migrate_memory_store(self.database)

        with closing(self.connect()) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM memory_schema_migrations"
            ).fetchone()[0]
        self.assertEqual(6, count)
        self.assertEqual(EXPECTED_TABLES, self.table_names())


if __name__ == "__main__":
    unittest.main()
