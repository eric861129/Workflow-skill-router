"""Strict, default-off contracts for Adaptive Workflow Memory."""

from pathlib import Path

from .migrator import (
    MemoryMigration,
    MemoryMigrationError,
    migrate_memory_store,
)
from .models import MemoryMode, MemoryPolicy, MemoryPolicyError, MemoryScope
from .policy import decode_memory_policy, decode_policy_text, memory_policy_document
from .policy_io import (
    MemoryPolicyRepository,
    PolicyLoadResult,
    PolicySource,
    default_router_data_dir,
)
from .policy_resolver import (
    EffectiveMemoryPolicy,
    resolution_steps,
    resolve_effective_policy,
)
from .safe_yaml import parse_safe_yaml
from .store import (
    MEMORY_DATABASE_NAME,
    MemoryPolicySnapshot,
    MemoryPolicySnapshotError,
    MemoryStore,
    MemoryStoreError,
    decode_memory_policy_snapshot,
)


def memory_database_path(data_dir: Path) -> Path:
    """Return the fixed Memory database path without touching the filesystem."""

    return Path(data_dir).expanduser() / "memory" / MEMORY_DATABASE_NAME


__all__ = [
    "EffectiveMemoryPolicy",
    "MEMORY_DATABASE_NAME",
    "MemoryMigration",
    "MemoryMigrationError",
    "MemoryMode",
    "MemoryPolicy",
    "MemoryPolicyError",
    "MemoryPolicyRepository",
    "MemoryPolicySnapshot",
    "MemoryPolicySnapshotError",
    "MemoryScope",
    "MemoryStore",
    "MemoryStoreError",
    "PolicyLoadResult",
    "PolicySource",
    "decode_memory_policy",
    "decode_memory_policy_snapshot",
    "decode_policy_text",
    "default_router_data_dir",
    "memory_database_path",
    "memory_policy_document",
    "migrate_memory_store",
    "parse_safe_yaml",
    "resolution_steps",
    "resolve_effective_policy",
]
