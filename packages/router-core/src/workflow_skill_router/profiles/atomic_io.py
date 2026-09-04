from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any

from workflow_skill_router.schemas.artifacts import canonical_json


MAX_JSON_BYTES = 256 * 1024
_DIGEST_PREFIX = "sha256:"


class ProfileIOError(RuntimeError):
    """Raised when fixed-root Profile I/O cannot be completed safely."""


def _is_link_or_reparse(metadata: os.stat_result) -> bool:
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)


def _absolute(path: Path) -> Path:
    expanded = Path(path).expanduser()
    return expanded if expanded.is_absolute() else Path.cwd() / expanded


def _inside_root(path: Path, root: Path) -> tuple[Path, Path]:
    absolute_root = _absolute(root).absolute()
    absolute_path = _absolute(path).absolute()
    try:
        absolute_path.relative_to(absolute_root)
    except ValueError as error:
        raise ProfileIOError("profile-path-escaped-root") from error
    return absolute_path, absolute_root


def _check_directory(path: Path, *, create: bool) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        if not create:
            raise ProfileIOError("profile-directory-missing")
        try:
            path.mkdir()
            metadata = path.lstat()
        except OSError as error:
            raise ProfileIOError("profile-directory-create-failed") from error
    except OSError as error:
        raise ProfileIOError("profile-directory-unavailable") from error
    if _is_link_or_reparse(metadata):
        raise ProfileIOError("profile-directory-link-forbidden")
    if not stat.S_ISDIR(metadata.st_mode):
        raise ProfileIOError("profile-directory-not-directory")


def _prepare_parent(path: Path, root: Path) -> None:
    # The user-owned root is the first authority boundary. Create it if absent,
    # then create every descendant one component at a time without following a
    # link or reparse point.
    if not root.exists():
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise ProfileIOError("profile-directory-create-failed") from error
    _check_directory(root, create=False)
    relative_parent = path.parent.relative_to(root)
    current = root
    for part in relative_parent.parts:
        current = current / part
        _check_directory(current, create=True)


def _check_existing_components(path: Path, root: Path) -> None:
    if not root.exists():
        raise ProfileIOError("profile-directory-missing")
    _check_directory(root, create=False)
    relative = path.relative_to(root)
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            raise ProfileIOError("profile-directory-missing")
        except OSError as error:
            raise ProfileIOError("profile-directory-unavailable") from error
        if _is_link_or_reparse(metadata):
            raise ProfileIOError("profile-directory-link-forbidden")
        if not stat.S_ISDIR(metadata.st_mode):
            raise ProfileIOError("profile-directory-not-directory")


def _decode_object(text: str) -> Mapping[str, Any]:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ProfileIOError("profile-json-duplicate-key")
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=object_pairs)
    except ProfileIOError:
        raise
    except json.JSONDecodeError as error:
        raise ProfileIOError("profile-json-invalid") from error
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ProfileIOError("profile-json-root-not-object")
    return value


def _document_digest(document: Mapping[str, object]) -> str:
    return _DIGEST_PREFIX + hashlib.sha256(
        canonical_json(document).encode("utf-8")
    ).hexdigest()


def secure_read_json(
    path: Path,
    root: Path,
    max_bytes: int = MAX_JSON_BYTES,
) -> Mapping[str, Any] | None:
    """Read one UTF-8 JSON object below a fixed root without following links."""

    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise ProfileIOError("profile-max-bytes-invalid")
    target, fixed_root = _inside_root(path, root)
    if not fixed_root.exists():
        return None
    _check_existing_components(target, fixed_root)
    try:
        metadata = target.lstat()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise ProfileIOError("profile-path-unavailable") from error
    if _is_link_or_reparse(metadata):
        raise ProfileIOError("profile-path-link-forbidden")
    if not stat.S_ISREG(metadata.st_mode):
        raise ProfileIOError("profile-path-not-regular")
    if metadata.st_size > max_bytes:
        raise ProfileIOError("profile-json-too-large")
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ProfileIOError("profile-json-not-utf8") from error
    except OSError as error:
        raise ProfileIOError("profile-path-unavailable") from error
    return _decode_object(text)


def current_json_digest(
    path: Path,
    root: Path,
    max_bytes: int = MAX_JSON_BYTES,
) -> str:
    document = secure_read_json(path, root, max_bytes)
    return "missing" if document is None else _document_digest(document)


def atomic_write_canonical_json(
    path: Path,
    root: Path,
    document: Mapping[str, object],
    expected_digest: str,
    max_bytes: int = MAX_JSON_BYTES,
) -> str:
    """CAS-write canonical JSON through a same-directory atomic replacement."""

    if not isinstance(document, Mapping) or any(not isinstance(key, str) for key in document):
        raise ProfileIOError("profile-json-root-not-object")
    if expected_digest != "missing" and not (
        isinstance(expected_digest, str)
        and expected_digest.startswith(_DIGEST_PREFIX)
        and len(expected_digest) == len(_DIGEST_PREFIX) + 64
        and all(char in "0123456789abcdef" for char in expected_digest[len(_DIGEST_PREFIX):])
    ):
        raise ProfileIOError("profile-expected-digest-invalid")
    target, fixed_root = _inside_root(path, root)
    _prepare_parent(target, fixed_root)
    if current_json_digest(target, fixed_root, max_bytes) != expected_digest:
        raise ProfileIOError("profile-drift")

    serialized = canonical_json(document) + "\n"
    if len(serialized.encode("utf-8")) > max_bytes:
        raise ProfileIOError("profile-json-too-large")
    result_digest = _document_digest(document)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        if current_json_digest(target, fixed_root, max_bytes) != expected_digest:
            raise ProfileIOError("profile-drift")
        os.replace(temporary, target)
        temporary = None
        try:
            directory_fd = os.open(target.parent, os.O_RDONLY)
        except (AttributeError, OSError):
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            except OSError:
                # Directory fsync is not portable; the file fsync and atomic
                # replace remain the cross-platform durability boundary.
                pass
            finally:
                os.close(directory_fd)
        stored = secure_read_json(target, fixed_root, max_bytes)
        if stored is None or canonical_json(stored) != canonical_json(document):
            raise ProfileIOError("profile-post-write-validation-failed")
        if _document_digest(stored) != result_digest:
            raise ProfileIOError("profile-post-write-digest-mismatch")
        return result_digest
    except ProfileIOError:
        raise
    except OSError as error:
        raise ProfileIOError("profile-atomic-write-failed") from error
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


__all__ = [
    "MAX_JSON_BYTES",
    "ProfileIOError",
    "atomic_write_canonical_json",
    "current_json_digest",
    "secure_read_json",
]
