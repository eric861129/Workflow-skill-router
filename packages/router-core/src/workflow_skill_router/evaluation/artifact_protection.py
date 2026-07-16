from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from workflow_skill_router.persistence.artifacts import ProtectedArtifact


class PermissionVerifier(Protocol):
    def directory_is_private(self, path: Path) -> bool: ...
    def file_is_private(self, path: Path) -> bool: ...


class OsPermissionArtifactProtector:
    """以 host 可驗證的 OS ACL 保護 raw trace；無法驗證時 fail closed。"""

    def __init__(self, verifier: PermissionVerifier) -> None:
        self._verifier = verifier

    def protect(self, plaintext: bytes, digest: str) -> ProtectedArtifact:
        return ProtectedArtifact(plaintext, "os-permission", "acl:" + digest)

    def open_verified(self, path: Path, protection_ref: str) -> bytes:
        if not protection_ref.startswith("acl:") or not self.verify_effective_permissions(path):
            raise PermissionError("restricted_artifact_permission_invalid")
        return path.read_bytes()

    def verify_private_directory(self, root: Path) -> bool:
        return self._verifier.directory_is_private(root)

    def verify_effective_permissions(self, path: Path) -> bool:
        return self._verifier.file_is_private(path)

    def destroy_key(self, protection_ref: str) -> None:
        raise RuntimeError("os-permission artifact 不支援 crypto erase")


class EncryptionProvider(Protocol):
    def encrypt(self, plaintext: bytes, associated_digest: str) -> tuple[bytes, str]: ...
    def decrypt(self, ciphertext: bytes, receipt: str) -> bytes: ...
    def destroy_key(self, receipt: str) -> None: ...


class EncryptionAtRestArtifactProtector:
    def __init__(self, provider: EncryptionProvider, verifier: PermissionVerifier) -> None:
        self._provider = provider
        self._verifier = verifier

    def protect(self, plaintext: bytes, digest: str) -> ProtectedArtifact:
        ciphertext, receipt = self._provider.encrypt(plaintext, digest)
        if not receipt or ciphertext == plaintext:
            raise RuntimeError("encryption_protection_unverified")
        return ProtectedArtifact(ciphertext, "encrypted", receipt)

    def open_verified(self, path: Path, protection_ref: str) -> bytes:
        return self._provider.decrypt(path.read_bytes(), protection_ref)

    def verify_private_directory(self, root: Path) -> bool:
        return self._verifier.directory_is_private(root)

    def verify_effective_permissions(self, path: Path) -> bool:
        return self._verifier.file_is_private(path)

    def destroy_key(self, protection_ref: str) -> None:
        self._provider.destroy_key(protection_ref)
