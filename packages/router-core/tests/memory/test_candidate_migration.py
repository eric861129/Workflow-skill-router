from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from workflow_skill_router.memory import MemoryPolicyRepository, MemoryStore, resolve_effective_policy
from memory.m1c_fixture import write_feedback_policy


class CandidateMigrationTests(unittest.TestCase):
    def test_candidate_tables_exist_after_memory_store_migration(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_feedback_policy(root)
            repository = MemoryPolicyRepository(root)
            policy = resolve_effective_policy(personal=repository.inspect_personal(), workspace=None)
            store = MemoryStore.open_if_enabled(root, policy)
            assert store is not None
            database = store.database_path
            store.close()
            with closing(sqlite3.connect(database)) as connection:
                tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertIn("workflow_patterns", tables)
                self.assertIn("workflow_candidates", tables)
                self.assertIn("candidate_suppressions", tables)
                versions = [row[0] for row in connection.execute("SELECT version FROM memory_schema_migrations ORDER BY version")]
                self.assertEqual([1, 2, 3, 4, 5], versions)


if __name__ == "__main__":
    unittest.main()
