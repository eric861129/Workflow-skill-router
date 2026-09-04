from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib import resources
import os
from pathlib import Path
import re
import sqlite3
import stat
from typing import Iterable


_MIGRATION_FILE = re.compile(r"^(?P<version>[0-9]{4})_(?P<name>[a-z][a-z0-9_]*)\.sql$")
_TRANSACTION_SQL = re.compile(r"\b(BEGIN|COMMIT|ROLLBACK|SAVEPOINT|RELEASE)\b", re.IGNORECASE)


class MemoryMigrationError(RuntimeError):
    """Raised when the optional Memory Store schema cannot be trusted."""


@dataclass(frozen=True, slots=True)
class MemoryMigration:
    version: int
    name: str
    checksum: str
    sql: str


def _load_migrations() -> tuple[MemoryMigration, ...]:
    package = resources.files("workflow_skill_router.memory.migrations")
    migrations: list[MemoryMigration] = []
    for item in package.iterdir():
        match = _MIGRATION_FILE.fullmatch(item.name)
        if match is None or not item.is_file():
            continue
        try:
            sql = item.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise MemoryMigrationError("memory-migration-resource-unavailable") from error
        if not sql.strip():
            raise MemoryMigrationError("memory-migration-empty")
        if _TRANSACTION_SQL.search(sql):
            raise MemoryMigrationError("memory-migration-transaction-forbidden")
        migrations.append(
            MemoryMigration(
                version=int(match.group("version")),
                name=match.group("name"),
                checksum=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
                sql=sql,
            )
        )

    migrations.sort(key=lambda item: item.version)
    if not migrations:
        raise MemoryMigrationError("memory-migration-resource-missing")
    versions = [item.version for item in migrations]
    names = [item.name for item in migrations]
    if len(set(versions)) != len(versions):
        raise MemoryMigrationError("memory-migration-version-duplicate")
    if len(set(names)) != len(names):
        raise MemoryMigrationError("memory-migration-name-duplicate")
    if versions != list(range(1, len(versions) + 1)):
        raise MemoryMigrationError("memory-migration-version-gap")
    return tuple(migrations)


def _statements(script: str) -> Iterable[str]:
    buffer = ""
    for line in script.splitlines(keepends=True):
        buffer += line
        if not sqlite3.complete_statement(buffer):
            continue
        statement = buffer.strip()
        buffer = ""
        if statement:
            yield statement
    if buffer.strip():
        raise MemoryMigrationError("memory-migration-incomplete-sql")


def _rollback(connection: sqlite3.Connection) -> None:
    if not connection.in_transaction:
        return
    try:
        connection.execute("ROLLBACK")
    except sqlite3.Error:
        pass


def _is_link_or_reparse(metadata: os.stat_result) -> bool:
    if stat.S_ISLNK(metadata.st_mode):
        return True
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return bool(attributes & flag)


def _validated_database_path(database: Path) -> Path:
    path = Path(database).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.absolute()

    try:
        parent_metadata = path.parent.lstat()
    except OSError as error:
        raise MemoryMigrationError("memory-migration-parent-unavailable") from error
    if _is_link_or_reparse(parent_metadata):
        raise MemoryMigrationError("memory-migration-parent-link-forbidden")
    if not stat.S_ISDIR(parent_metadata.st_mode):
        raise MemoryMigrationError("memory-migration-parent-not-directory")

    try:
        file_metadata = path.lstat()
    except FileNotFoundError:
        return path
    except OSError as error:
        raise MemoryMigrationError("memory-migration-file-unavailable") from error
    if _is_link_or_reparse(file_metadata):
        raise MemoryMigrationError("memory-migration-file-link-forbidden")
    if not stat.S_ISREG(file_metadata.st_mode):
        raise MemoryMigrationError("memory-migration-file-not-regular")
    return path


def _migrate_memory_connection(connection: sqlite3.Connection) -> tuple[int, ...]:
    """Apply checksum-protected Memory migrations to an owned connection."""

    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("connection must be sqlite3.Connection")
    if connection.in_transaction:
        raise MemoryMigrationError("memory-migration-active-transaction")

    migrations = _load_migrations()
    known = {item.version: item for item in migrations}
    applied_now: list[int] = []
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                checksum TEXT NOT NULL
                    CHECK(length(checksum) = 64)
                    CHECK(checksum NOT GLOB '*[^0-9a-f]*'),
                applied_at TEXT NOT NULL
            )
            """
        )

        rows = connection.execute(
            "SELECT version, name, checksum "
            "FROM memory_schema_migrations ORDER BY version"
        ).fetchall()
        for raw_version, raw_name, raw_checksum in rows:
            version = int(raw_version)
            migration = known.get(version)
            if migration is None:
                raise MemoryMigrationError(
                    "memory-migration-unknown-applied-version"
                )
            if str(raw_name) != migration.name:
                raise MemoryMigrationError("memory-migration-name-mismatch")
            if str(raw_checksum) != migration.checksum:
                raise MemoryMigrationError(
                    "memory-migration-checksum-mismatch"
                )

        applied_versions = {int(row[0]) for row in rows}
        for migration in migrations:
            if migration.version in applied_versions:
                continue
            duplicate_name = connection.execute(
                "SELECT version FROM memory_schema_migrations WHERE name = ?",
                (migration.name,),
            ).fetchone()
            if duplicate_name is not None:
                raise MemoryMigrationError("memory-migration-name-mismatch")
            for statement in _statements(migration.sql):
                connection.execute(statement)
            connection.execute(
                """
                INSERT INTO memory_schema_migrations(
                    version,
                    name,
                    checksum,
                    applied_at
                )
                VALUES (
                    ?,
                    ?,
                    ?,
                    strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                )
                """,
                (
                    migration.version,
                    migration.name,
                    migration.checksum,
                ),
            )
            applied_now.append(migration.version)
        connection.execute("COMMIT")
    except MemoryMigrationError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise MemoryMigrationError("memory-migration-apply-failed") from error
    except Exception:
        _rollback(connection)
        raise
    return tuple(applied_now)


def migrate_memory_store(database: Path) -> None:
    """Open, migrate, and close one fixed Memory database path."""

    # MemoryStore owns a long-lived connection while recording the current
    # policy snapshot. Keep that existing internal call path bounded while the
    # public contract remains Path-in/None-out.
    if isinstance(database, sqlite3.Connection):
        _migrate_memory_connection(database)
        return

    database_path = _validated_database_path(database)
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(
            database_path,
            isolation_level=None,
            timeout=5.0,
        )
        _validated_database_path(database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        _migrate_memory_connection(connection)
    except MemoryMigrationError:
        raise
    except sqlite3.Error as error:
        raise MemoryMigrationError("memory-migration-open-failed") from error
    finally:
        if connection is not None:
            connection.close()


__all__ = [
    "MemoryMigration",
    "MemoryMigrationError",
    "migrate_memory_store",
]
