from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from importlib.resources import files
from pathlib import Path
import sqlite3
from contextlib import closing


def iter_complete_statements(sql: str):
    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            buffer = ""
            if statement:
                yield statement
    if buffer.strip():
        raise RuntimeError("migration 含有不完整 SQL statement")


def migrate(database: Path) -> None:
    database.parent.mkdir(parents=True, exist_ok=True)
    scripts = sorted(
        files("workflow_skill_router.persistence.migrations").iterdir(),
        key=lambda item: item.name,
    )
    with closing(sqlite3.connect(database, timeout=30.0)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("BEGIN IMMEDIATE")
        try:
            for script in scripts:
                if not script.name.endswith(".sql"):
                    continue
                version = script.name.split("_", 1)[0]
                sql = script.read_text(encoding="utf-8")
                checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
                exists = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
                ).fetchone()
                applied = None if not exists else connection.execute(
                    "SELECT checksum FROM schema_migrations WHERE version=?",
                    (version,),
                ).fetchone()
                if applied is not None:
                    if applied[0] != checksum:
                        raise RuntimeError(f"Migration {version} checksum 不一致")
                    continue
                for statement in iter_complete_statements(sql):
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO schema_migrations(version, checksum, applied_at) VALUES (?, ?, ?)",
                    (version, checksum, datetime.now(UTC).isoformat()),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
