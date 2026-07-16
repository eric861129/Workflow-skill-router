from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from contextlib import closing
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Protocol

from workflow_skill_router.runtime import Clock


_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class ArtifactProtectionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProtectedArtifact:
    stored_bytes: bytes
    protection_kind: str
    protection_ref: str


class ArtifactProtector(Protocol):
    def protect(self, plaintext: bytes, digest: str) -> ProtectedArtifact: ...
    def open_verified(self, path: Path, protection_ref: str) -> bytes: ...
    def verify_private_directory(self, root: Path) -> bool: ...
    def verify_effective_permissions(self, path: Path) -> bool: ...
    def destroy_key(self, protection_ref: str) -> None: ...


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    digest: str
    media_type: str
    sensitivity: str
    protection_kind: str
    protection_ref: str | None


@dataclass(frozen=True, slots=True)
class ArtifactMetadata:
    digest: str
    size_bytes: int
    media_type: str
    sensitivity: str
    producer: str
    relative_path: str
    protection_kind: str
    protection_ref: str | None
    created_at: str
    status: str
    payload_present: bool


@dataclass(frozen=True, slots=True)
class ArtifactLifecycleReceipt:
    event_type: str
    digest: str
    reason: str
    actor: str
    occurred_at: str


class ArtifactLifecycleEventSink(Protocol):
    def append(self, receipt: ArtifactLifecycleReceipt) -> None: ...


class ContentAddressedArtifactStore:
    def __init__(
        self,
        root: Path,
        database: Path,
        *,
        clock: Clock,
        protector: ArtifactProtector | None = None,
        restricted_root: Path | None = None,
        lifecycle_sink: ArtifactLifecycleEventSink | None = None,
    ) -> None:
        self._root = root.resolve(strict=False)
        self._database = database
        self._clock = clock
        self._protector = protector
        self._restricted_root = (
            restricted_root.resolve(strict=False) if restricted_root is not None else None
        )
        self._lifecycle_sink = lifecycle_sink
        self._root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_digest(digest: str) -> None:
        if not _DIGEST.fullmatch(digest):
            raise ValueError("artifact digest 必須是 lowercase sha256")

    @classmethod
    def _relative_path(cls, digest: str) -> Path:
        cls._validate_digest(digest)
        value = digest.removeprefix("sha256:")
        return Path("objects") / value[:2] / value[2:]

    def _path(self, metadata: ArtifactMetadata) -> Path:
        root = self._restricted_root if metadata.sensitivity == "restricted" else self._root
        if root is None:
            raise ArtifactProtectionError("restricted root 未設定")
        relative = Path(metadata.relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ArtifactProtectionError("artifact metadata path 不安全")
        path = (root / relative).resolve(strict=False)
        if not path.is_relative_to(root):
            raise ArtifactProtectionError("artifact path 超出受信任 root")
        return path

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary_path = Path(stream.name)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, path)
            temporary_path = None
            try:
                descriptor = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            except OSError:
                pass
        finally:
            if temporary_path is not None and temporary_path.exists():
                os.unlink(temporary_path)

    def put_bytes(
        self,
        data: bytes,
        media_type: str,
        sensitivity: str,
        producer: str,
    ) -> ArtifactRef:
        if not isinstance(data, bytes):
            raise TypeError("artifact data 必須是 bytes")
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        try:
            existing = self.metadata(digest)
        except LookupError:
            existing = None
        if existing is not None:
            self.open_verified(digest)
            return ArtifactRef(
                existing.digest, existing.media_type, existing.sensitivity,
                existing.protection_kind, existing.protection_ref,
            )

        relative = self._relative_path(digest)
        stored = data
        protection_kind = "none"
        protection_ref = None
        root = self._root
        if sensitivity == "restricted":
            if self._protector is None or self._restricted_root is None:
                raise ArtifactProtectionError("restricted artifact 需要 protector 與 private root")
            self._restricted_root.mkdir(parents=True, exist_ok=True)
            if not self._protector.verify_private_directory(self._restricted_root):
                raise ArtifactProtectionError("private directory 驗證失敗")
            protected = self._protector.protect(data, digest)
            if not protected.protection_ref or not protected.protection_kind:
                raise ArtifactProtectionError("protector receipt 不完整")
            stored = protected.stored_bytes
            protection_kind = protected.protection_kind
            protection_ref = protected.protection_ref
            root = self._restricted_root

        path = root / relative
        self._atomic_write(path, stored)
        if sensitivity == "restricted" and not self._protector.verify_effective_permissions(path):
            if path.exists():
                os.unlink(path)
            raise ArtifactProtectionError("restricted artifact 權限驗證失敗")

        created = self._clock.now_utc()
        if created.tzinfo is None or created.utcoffset() is None:
            raise ValueError("Clock 必須回傳 timezone-aware datetime")
        try:
            with closing(sqlite3.connect(self._database)) as connection:
                connection.execute(
                    "INSERT INTO artifact_metadata("
                    "digest,size_bytes,media_type,sensitivity,producer,relative_path,"
                    "protection_kind,protection_ref,created_at,tombstoned_at,erased_at,payload_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, '{}')",
                    (
                        digest, len(data), media_type, sensitivity, producer,
                        relative.as_posix(), protection_kind, protection_ref,
                        created.astimezone(timezone.utc).isoformat(),
                    ),
                )
                connection.commit()
        except Exception:
            if path.exists():
                os.unlink(path)
            raise
        return ArtifactRef(digest, media_type, sensitivity, protection_kind, protection_ref)

    def metadata(self, digest: str) -> ArtifactMetadata:
        self._validate_digest(digest)
        with closing(sqlite3.connect(self._database)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM artifact_metadata WHERE digest=?", (digest,)
            ).fetchone()
        if row is None:
            raise LookupError(digest)
        status = "erased" if row["erased_at"] else "tombstoned" if row["tombstoned_at"] else "active"
        return ArtifactMetadata(
            row["digest"], int(row["size_bytes"]), row["media_type"],
            row["sensitivity"], row["producer"], row["relative_path"],
            row["protection_kind"], row["protection_ref"], row["created_at"],
            status, status == "active",
        )

    def open_verified(self, digest: str) -> bytes:
        metadata = self.metadata(digest)
        if not metadata.payload_present:
            raise ArtifactProtectionError("artifact payload 已不可用")
        path = self._path(metadata)
        if not path.is_file():
            raise ArtifactProtectionError("artifact object 遺失")
        if metadata.sensitivity == "restricted":
            if self._protector is None or metadata.protection_ref is None:
                raise ArtifactProtectionError("restricted protector 不可用")
            if not self._protector.verify_effective_permissions(path):
                raise ArtifactProtectionError("restricted artifact 權限失效")
            plaintext = self._protector.open_verified(path, metadata.protection_ref)
        else:
            plaintext = path.read_bytes()
        actual = "sha256:" + hashlib.sha256(plaintext).hexdigest()
        if actual != digest:
            raise ArtifactProtectionError("artifact digest 驗證失敗")
        return plaintext

    def count_metadata(self) -> int:
        with closing(sqlite3.connect(self._database)) as connection:
            return int(connection.execute("SELECT COUNT(*) FROM artifact_metadata").fetchone()[0])

    def _receipt(self, event_type: str, digest: str, reason: str, actor: str) -> ArtifactLifecycleReceipt:
        if self._lifecycle_sink is None:
            raise ArtifactProtectionError("artifact lifecycle sink 未設定")
        occurred = self._clock.now_utc().astimezone(timezone.utc).isoformat()
        receipt = ArtifactLifecycleReceipt(event_type, digest, reason, actor, occurred)
        self._lifecycle_sink.append(receipt)
        return receipt

    def tombstone(self, digest: str, reason: str, actor: str) -> ArtifactLifecycleReceipt:
        self.metadata(digest)
        receipt = self._receipt("EVENT_PAYLOAD_TOMBSTONED", digest, reason, actor)
        with closing(sqlite3.connect(self._database)) as connection:
            connection.execute(
                "UPDATE artifact_metadata SET tombstoned_at=? WHERE digest=?",
                (receipt.occurred_at, digest),
            )
            connection.commit()
        return receipt

    def crypto_erase(self, digest: str, reason: str, actor: str) -> ArtifactLifecycleReceipt:
        metadata = self.metadata(digest)
        if (
            metadata.sensitivity != "restricted"
            or self._protector is None
            or metadata.protection_ref is None
        ):
            raise ArtifactProtectionError("只有受保護的 restricted artifact 可 crypto erase")
        self._protector.destroy_key(metadata.protection_ref)
        receipt = self._receipt("ARTIFACT_CRYPTO_ERASED", digest, reason, actor)
        with closing(sqlite3.connect(self._database)) as connection:
            connection.execute(
                "UPDATE artifact_metadata SET erased_at=? WHERE digest=?",
                (receipt.occurred_at, digest),
            )
            connection.commit()
        return receipt
