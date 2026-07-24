"""Safely synchronize a generated Plugin distribution into its target checkout."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
OWNERSHIP_FILENAME = ".workflow-skill-router-distribution.json"
OWNERSHIP_PATH = PurePosixPath(OWNERSHIP_FILENAME)
REMOTE_IDENTITY_PATTERN = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?/"
    r"[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?$"
)
REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def _load_release_path_safety():
    helper_path = SCRIPT_DIRECTORY / "release_path_safety.py"
    specification = importlib.util.spec_from_file_location(
        "workflow_skill_router_plugin_sync_path_safety",
        helper_path,
    )
    if specification is None or specification.loader is None:
        raise ImportError(f"cannot load release path safety helper: {helper_path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    parser = getattr(module, "parse_safe_relative_posix_path", None)
    if not callable(parser):
        raise ImportError(
            f"release path safety helper is missing its parser: {helper_path}"
        )
    return parser


parse_safe_relative_posix_path = _load_release_path_safety()


def _parse_distribution_path(value: str) -> PurePosixPath:
    relative = parse_safe_relative_posix_path(value)
    if relative.parts[0].casefold() == ".git":
        raise ValueError(f"reserved Git metadata path is unsafe: {value!r}")
    if (
        len(relative.parts) == 1
        and relative.parts[0].casefold() == OWNERSHIP_FILENAME.casefold()
    ):
        raise ValueError(f"reserved synchronizer path is unsafe: {value!r}")
    return relative


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _is_link_like(path: Path) -> bool:
    if path.is_symlink():
        return True
    if os.name != "nt":
        return False
    try:
        attributes = path.lstat().st_file_attributes
    except FileNotFoundError:
        return False
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _run_git(target_root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=target_root,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(
            f"target checkout git command failed: git {' '.join(arguments)}"
            + (f": {detail}" if detail else "")
        )
    return completed


def _decode_git_output(value: bytes, description: str) -> str:
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"target checkout has non-UTF-8 {description}") from error


def _expected_repository_url(expected_remote: str) -> str:
    if not REMOTE_IDENTITY_PATTERN.fullmatch(expected_remote):
        raise ValueError(
            "expected remote must be an exact GitHub owner/repository identity"
        )
    return f"https://github.com/{expected_remote}"


def _normalized_origin_url(origin: str) -> str:
    candidate = origin.strip()
    while candidate.endswith("/"):
        candidate = candidate[:-1]
    if candidate.endswith(".git"):
        candidate = candidate[:-4]
    while candidate.endswith("/"):
        candidate = candidate[:-1]

    parsed = urlsplit(candidate)
    if (
        parsed.scheme != "https"
        or parsed.netloc.casefold() != "github.com"
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
    ):
        raise ValueError(f"invalid target identity origin URL: {origin!r}")
    parts = parsed.path.split("/")
    if len(parts) != 3 or not parts[1] or not parts[2]:
        raise ValueError(f"invalid target identity origin URL: {origin!r}")
    identity = f"{parts[1]}/{parts[2]}"
    if not REMOTE_IDENTITY_PATTERN.fullmatch(identity):
        raise ValueError(f"invalid target identity origin URL: {origin!r}")
    return f"https://github.com/{identity}"


def _verify_target_checkout(target_root: Path, expected_remote: str) -> Path:
    target_root = Path(target_root)
    if _is_link_like(target_root) or not target_root.is_dir():
        raise ValueError("target checkout must be a regular directory")
    resolved_target = target_root.resolve()

    top_level = _decode_git_output(
        _run_git(resolved_target, "rev-parse", "--show-toplevel").stdout,
        "repository root",
    ).strip()
    try:
        resolved_top_level = Path(top_level).resolve(strict=True)
    except OSError as error:
        raise ValueError("target checkout repository root is invalid") from error
    if resolved_top_level != resolved_target:
        raise ValueError("target root must be the target checkout repository root")

    expected_url = _expected_repository_url(expected_remote)
    origin = _decode_git_output(
        _run_git(resolved_target, "remote", "get-url", "origin").stdout,
        "origin URL",
    ).strip()
    normalized_origin = _normalized_origin_url(origin)
    if normalized_origin != expected_url:
        raise ValueError(
            "target identity mismatch: "
            f"expected {expected_url}, found {normalized_origin}"
        )

    status = _decode_git_output(
        _run_git(resolved_target, "status", "--porcelain=v1").stdout,
        "status",
    )
    if status:
        raise ValueError("target checkout must be clean before synchronization")
    return resolved_target


def _read_json_object(content: bytes, description: str) -> dict[str, object]:
    try:
        value = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {description}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{description} must be a JSON object")
    return value


def _read_generated_tree(
    generated_root: Path,
) -> tuple[dict[PurePosixPath, bytes], str, str]:
    generated_root = Path(generated_root)
    if _is_link_like(generated_root) or not generated_root.is_dir():
        raise ValueError("generated root must be a regular directory")
    resolved_root = generated_root.resolve()
    files: dict[PurePosixPath, bytes] = {}

    for current_root, directory_names, file_names in os.walk(
        resolved_root,
        topdown=True,
        followlinks=False,
    ):
        current = Path(current_root)
        for name in sorted(directory_names):
            directory = current / name
            relative_name = directory.relative_to(resolved_root).as_posix()
            _parse_distribution_path(relative_name)
            if _is_link_like(directory):
                raise ValueError(
                    f"symlink or junction forbidden in generated tree: {relative_name}"
                )
            if not directory.is_dir():
                raise ValueError(
                    f"generated tree entry is not a regular directory: {relative_name}"
                )
        for name in sorted(file_names):
            source = current / name
            relative_name = source.relative_to(resolved_root).as_posix()
            relative = _parse_distribution_path(relative_name)
            if _is_link_like(source):
                raise ValueError(
                    f"symlink or junction forbidden in generated tree: {relative_name}"
                )
            if not source.is_file():
                raise ValueError(
                    f"generated tree entry is not a regular file: {relative_name}"
                )
            try:
                source.resolve(strict=True).relative_to(resolved_root)
            except (OSError, ValueError) as error:
                raise ValueError(
                    f"unsafe generated tree path: {relative_name}"
                ) from error
            files[relative] = source.read_bytes()

    if OWNERSHIP_PATH in files:
        raise ValueError(
            f"generated tree contains reserved synchronizer path: {OWNERSHIP_FILENAME}"
        )
    release_content = files.get(PurePosixPath("release.json"))
    if release_content is None:
        raise ValueError("generated tree is missing release.json")
    release = _read_json_object(release_content, "generated release metadata")
    version = release.get("version")
    source_revision = release.get("source_revision")
    if not isinstance(version, str) or not version:
        raise ValueError("generated release metadata version is missing")
    if (
        not isinstance(source_revision, str)
        or REVISION_PATTERN.fullmatch(source_revision) is None
    ):
        raise ValueError(
            "generated release metadata source revision must be a lowercase "
            "40-character hexadecimal SHA"
        )
    return dict(sorted(files.items())), version, source_revision


def _load_previous_ownership(target_root: Path) -> set[PurePosixPath]:
    record_path = target_root / OWNERSHIP_FILENAME
    if not record_path.exists() and not _is_link_like(record_path):
        return set()
    if _is_link_like(record_path) or not record_path.is_file():
        raise ValueError("ownership record must be a regular file")
    record = _read_json_object(record_path.read_bytes(), "ownership record")
    if record.get("schema_version") != "1.0":
        raise ValueError("unsupported ownership record schema")
    raw_files = record.get("managed_files")
    if not isinstance(raw_files, list) or not all(
        isinstance(value, str) for value in raw_files
    ):
        raise ValueError("ownership record managed_files must be strings")
    if raw_files != sorted(set(raw_files)):
        raise ValueError("ownership record managed_files must be sorted and unique")
    managed_files = {
        _parse_distribution_path(value) for value in raw_files
    }
    if OWNERSHIP_PATH in managed_files:
        raise ValueError("ownership record cannot manage its own reserved path")
    version = record.get("version")
    source_revision = record.get("source_revision")
    if not isinstance(version, str) or not version:
        raise ValueError("ownership record version is missing")
    if (
        not isinstance(source_revision, str)
        or REVISION_PATTERN.fullmatch(source_revision) is None
    ):
        raise ValueError("ownership record source revision is invalid")
    return managed_files


def _tracked_files(target_root: Path) -> set[PurePosixPath]:
    output = _run_git(target_root, "ls-files", "-z").stdout
    result: set[PurePosixPath] = set()
    for raw_name in output.split(b"\0"):
        if not raw_name:
            continue
        name = _decode_git_output(raw_name, "tracked path")
        if name == OWNERSHIP_FILENAME:
            result.add(OWNERSHIP_PATH)
        else:
            result.add(_parse_distribution_path(name))
    return result


def _validate_target_path(
    target_root: Path,
    relative: PurePosixPath,
    *,
    removable_files: set[PurePosixPath],
) -> Path:
    current = target_root
    current_relative = PurePosixPath()
    for index, part in enumerate(relative.parts):
        current = current / part
        current_relative = current_relative / part
        is_target = index == len(relative.parts) - 1
        if _is_link_like(current):
            raise ValueError(
                f"symlink or junction forbidden in target path: {relative}"
            )
        if not current.exists():
            continue
        if is_target:
            if not current.is_file():
                raise ValueError(
                    f"target path is not a regular file: {relative}"
                )
        elif current.is_file() and current_relative not in removable_files:
            raise ValueError(
                f"target parent is not a regular directory: {current_relative}"
            )
        elif not current.is_file() and not current.is_dir():
            raise ValueError(
                f"target parent is not a regular directory: {current_relative}"
            )
    try:
        current.resolve(strict=False).relative_to(target_root)
    except ValueError as error:
        raise ValueError(f"unsafe target path: {relative}") from error
    return current


def _preflight(
    target_root: Path,
    new_files: set[PurePosixPath],
    previous_files: set[PurePosixPath],
) -> tuple[list[tuple[PurePosixPath, Path]], dict[PurePosixPath, Path]]:
    tracked_files = _tracked_files(target_root)
    if (
        (target_root / OWNERSHIP_FILENAME).exists()
        and OWNERSHIP_PATH not in tracked_files
    ):
        raise ValueError("existing ownership record must be a tracked file")
    unmanaged = sorted(
        tracked_files - previous_files - new_files - {OWNERSHIP_PATH}
    )
    if unmanaged:
        names = ", ".join(path.as_posix() for path in unmanaged[:8])
        raise ValueError(f"unmanaged tracked file: {names}")

    removable_names = previous_files - new_files
    removals: list[tuple[PurePosixPath, Path]] = []
    for relative in sorted(removable_names):
        target = _validate_target_path(
            target_root,
            relative,
            removable_files=removable_names,
        )
        if not target.exists() or _is_link_like(target) or not target.is_file():
            raise ValueError(
                "managed removal requires an existing regular file: "
                f"{relative.as_posix()}"
            )
        removals.append((relative, target))

    write_targets: dict[PurePosixPath, Path] = {}
    for relative in sorted(new_files):
        write_targets[relative] = _validate_target_path(
            target_root,
            relative,
            removable_files=removable_names,
        )
    write_targets[OWNERSHIP_PATH] = _validate_target_path(
        target_root,
        OWNERSHIP_PATH,
        removable_files=removable_names,
    )
    return removals, write_targets


def _atomic_write(target: Path, content: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def synchronize(
    generated_root: Path,
    target_root: Path,
    expected_remote: str,
) -> int:
    resolved_target = _verify_target_checkout(target_root, expected_remote)
    generated_files, version, source_revision = _read_generated_tree(generated_root)
    previous_files = _load_previous_ownership(resolved_target)
    removals, write_targets = _preflight(
        resolved_target,
        set(generated_files),
        previous_files,
    )

    for _, target in removals:
        target.unlink()
    for relative, content in generated_files.items():
        _atomic_write(write_targets[relative], content)
    ownership = canonical_json(
        {
            "managed_files": [
                relative.as_posix() for relative in sorted(generated_files)
            ],
            "schema_version": "1.0",
            "source_revision": source_revision,
            "version": version,
        }
    )
    _atomic_write(write_targets[OWNERSHIP_PATH], ownership)
    return len(generated_files)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generated-root", type=Path, required=True)
    parser.add_argument("--target-root", type=Path, required=True)
    parser.add_argument("--expected-remote", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        synchronized_count = synchronize(
            args.generated_root,
            args.target_root,
            args.expected_remote,
        )
    except (
        ImportError,
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
        UnicodeError,
        ValueError,
    ) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"synchronized {synchronized_count} managed files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
