"""Build the standalone Workflow Skill Router Plugin repository."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
DEFAULT_REPOSITORY_ROOT = SCRIPT_DIRECTORY.parent
DEFAULT_DISTRIBUTION_CONFIG = (
    DEFAULT_REPOSITORY_ROOT / "release" / "plugin-distribution.json"
)
DEFAULT_OUTPUT = DEFAULT_REPOSITORY_ROOT / "dist" / "plugin-repository"
CANONICAL_REPOSITORY = "https://github.com/eric861129/Workflow-skill-router"
TARGET_REPOSITORY = "https://github.com/eric861129/workflow-skill-router-plugin"
GA_VERSION_PATTERN = re.compile(
    r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$"
)
REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_SOURCE_ROOT = PurePosixPath("plugins/workflow-skill-router")
EXPECTED_PACKAGING_TARGETS = frozenset(
    {
        PurePosixPath(".codexignore"),
        PurePosixPath(".github/dependabot.yml"),
        PurePosixPath(".github/workflows/hol-plugin-scanner.yml"),
        PurePosixPath(".gitignore"),
        PurePosixPath("PRIVACY.md"),
        PurePosixPath("README.md"),
        PurePosixPath("SECURITY.md"),
        PurePosixPath("TERMS.md"),
        PurePosixPath("UPSTREAM.md"),
        PurePosixPath("assets/icon.svg"),
    }
)


def _load_release_path_safety():
    helper_path = SCRIPT_DIRECTORY / "release_path_safety.py"
    specification = importlib.util.spec_from_file_location(
        "workflow_skill_router_plugin_distribution_path_safety",
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


@dataclass(frozen=True)
class DistributionTree:
    """An immutable description of one standalone Plugin distribution."""

    files: dict[PurePosixPath, bytes]
    version: str
    source_revision: str


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


def load_json_object(path: Path, description: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {description}: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{description} must be a JSON object: {path}")
    return value


def _validate_release_identity(version: str, source_revision: str) -> None:
    if not GA_VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"GA version must use x.y.z without prerelease data: {version!r}")
    if not REVISION_PATTERN.fullmatch(source_revision):
        raise ValueError(
            "source revision must be a lowercase 40-character hexadecimal SHA"
        )


def _safe_repository_path(
    repository_root: Path,
    relative_name: str,
    *,
    description: str,
) -> tuple[PurePosixPath, Path]:
    relative = parse_safe_relative_posix_path(relative_name)
    resolved_root = repository_root.resolve()
    candidate = repository_root.joinpath(*relative.parts)

    current = repository_root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"symlink forbidden in {description}: {relative_name}")

    try:
        resolved_candidate = candidate.resolve(strict=True)
        resolved_candidate.relative_to(resolved_root)
    except (OSError, ValueError) as error:
        raise ValueError(
            f"unsafe or missing {description}: {relative_name!r}"
        ) from error
    if not resolved_candidate.is_file():
        raise ValueError(
            f"{description} is not a regular file: {relative_name!r}"
        )
    return relative, resolved_candidate


def _load_distribution_config(
    repository_root: Path,
    config_path: Path,
) -> dict[str, object]:
    config = load_json_object(config_path, "plugin distribution config")
    if config.get("schema_version") != "1.0":
        raise ValueError("unsupported plugin distribution config schema")

    source_root = config.get("source_root")
    if not isinstance(source_root, str):
        raise ValueError("plugin distribution source_root must be a string")
    parsed_source_root = parse_safe_relative_posix_path(source_root)
    if parsed_source_root != EXPECTED_SOURCE_ROOT:
        raise ValueError(
            "plugin distribution source_root must be "
            "plugins/workflow-skill-router"
        )
    source_path = repository_root.joinpath(*parsed_source_root.parts)
    resolved_repository = repository_root.resolve()
    try:
        resolved_source = source_path.resolve(strict=True)
        resolved_source.relative_to(resolved_repository)
    except (OSError, ValueError) as error:
        raise ValueError("unsafe or missing plugin distribution source root") from error
    if source_path.is_symlink() or not resolved_source.is_dir():
        raise ValueError("plugin distribution source root must be a regular directory")
    return config


def _load_allowlist(
    path: Path,
) -> list[str]:
    allowlist = load_json_object(path, "plugin distribution allowlist")
    raw_files = allowlist.get("files")
    if not isinstance(raw_files, list) or not all(
        isinstance(value, str) for value in raw_files
    ):
        raise ValueError("plugin distribution allowlist files must be strings")
    if raw_files != sorted(set(raw_files)):
        raise ValueError("plugin distribution allowlist must be sorted and unique")
    for value in raw_files:
        parse_safe_relative_posix_path(value)
    return raw_files


def _transform_plugin_manifest(content: bytes, version: str) -> bytes:
    manifest = json.loads(content)
    if not isinstance(manifest, dict):
        raise ValueError("Plugin manifest must be a JSON object")
    if manifest.get("version") != version:
        raise ValueError("Plugin manifest version does not match distribution version")
    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        raise ValueError("Plugin manifest interface must be a JSON object")
    manifest["repository"] = TARGET_REPOSITORY
    interface["composerIcon"] = "./assets/icon.svg"
    interface["logo"] = "./assets/icon.svg"
    return canonical_json(manifest)


def _transform_package(content: bytes, version: str) -> bytes:
    package = json.loads(content)
    if not isinstance(package, dict):
        raise ValueError("package.json must be a JSON object")
    if package.get("version") != version:
        raise ValueError("package.json version does not match distribution version")
    package["name"] = "workflow-skill-router-plugin"
    package["repository"] = {
        "type": "git",
        "url": f"{TARGET_REPOSITORY}.git",
    }
    package["bugs"] = {"url": f"{TARGET_REPOSITORY}/issues"}
    return canonical_json(package)


def _transform_package_lock(content: bytes, version: str) -> bytes:
    package_lock = json.loads(content)
    if not isinstance(package_lock, dict):
        raise ValueError("package-lock.json must be a JSON object")
    packages = package_lock.get("packages")
    if not isinstance(packages, dict) or not isinstance(packages.get(""), dict):
        raise ValueError("package-lock.json is missing its root package")
    root_package = packages[""]
    if (
        package_lock.get("version") != version
        or root_package.get("version") != version
    ):
        raise ValueError("package-lock.json version does not match distribution version")
    package_lock["name"] = "workflow-skill-router-plugin"
    root_package["name"] = "workflow-skill-router-plugin"
    return canonical_json(package_lock)


def _transform_source_file(
    relative: PurePosixPath,
    content: bytes,
    version: str,
) -> bytes:
    if relative == PurePosixPath(".codex-plugin/plugin.json"):
        return _transform_plugin_manifest(content, version)
    if relative == PurePosixPath("package.json"):
        return _transform_package(content, version)
    if relative == PurePosixPath("package-lock.json"):
        return _transform_package_lock(content, version)
    return content


def _render_template(
    content: bytes,
    *,
    version: str,
    source_revision: str,
    source_name: str,
) -> bytes:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"distribution template must be UTF-8: {source_name}") from error
    required_tokens = ("{{VERSION}}", "{{SOURCE_REVISION}}")
    if any(token not in text for token in required_tokens):
        raise ValueError(
            f"distribution template must contain both supported tokens: {source_name}"
        )
    rendered = text.replace("{{VERSION}}", version).replace(
        "{{SOURCE_REVISION}}",
        source_revision,
    )
    if "{{" in rendered or "}}" in rendered:
        raise ValueError(f"unresolved distribution template token: {source_name}")
    return rendered.encode("utf-8")


def _packaging_entries(
    repository_root: Path,
    config: dict[str, object],
    *,
    version: str,
    source_revision: str,
) -> dict[PurePosixPath, bytes]:
    raw_entries = config.get("packaging_files")
    if not isinstance(raw_entries, list):
        raise ValueError("plugin distribution packaging_files must be a list")

    targets: list[PurePosixPath] = []
    result: dict[PurePosixPath, bytes] = {}
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            raise ValueError("plugin distribution packaging entry must be an object")
        source_name = raw_entry.get("source")
        target_name = raw_entry.get("target")
        is_template = raw_entry.get("template")
        if (
            not isinstance(source_name, str)
            or not isinstance(target_name, str)
            or not isinstance(is_template, bool)
        ):
            raise ValueError("invalid plugin distribution packaging entry")
        target = parse_safe_relative_posix_path(target_name)
        _, source = _safe_repository_path(
            repository_root,
            source_name,
            description="packaging source",
        )
        content = source.read_bytes()
        if is_template:
            content = _render_template(
                content,
                version=version,
                source_revision=source_revision,
                source_name=source_name,
            )
        targets.append(target)
        if target in result:
            raise ValueError(f"duplicate packaging output: {target}")
        result[target] = content

    if targets != sorted(set(targets)):
        raise ValueError("plugin distribution packaging targets must be sorted and unique")
    if set(targets) != EXPECTED_PACKAGING_TARGETS:
        raise ValueError("plugin distribution packaging targets do not match the contract")
    _validate_scanner_workflow(
        result[PurePosixPath(".github/workflows/hol-plugin-scanner.yml")]
    )
    return result


def _validate_scanner_workflow(content: bytes) -> None:
    text = content.decode("utf-8")
    uses_values = re.findall(r"^\s*uses:\s*([^#\s]+)", text, flags=re.MULTILINE)
    if not uses_values or any(
        re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", value) is None
        for value in uses_values
    ):
        raise ValueError("HOL Scanner workflow actions must remain SHA-pinned")
    if "min_score: 80" not in text or "fail_on_severity: high" not in text:
        raise ValueError("HOL Scanner workflow must enforce score 80 and high severity")


def _config_relative_file(
    repository_root: Path,
    config: dict[str, object],
    key: str,
) -> Path:
    value = config.get(key)
    if not isinstance(value, str):
        raise ValueError(f"plugin distribution {key} must be a string")
    _, path = _safe_repository_path(
        repository_root,
        value,
        description=key,
    )
    return path


def configured_version(
    repository_root: Path,
    config: dict[str, object],
) -> str:
    version_file = _config_relative_file(repository_root, config, "version_file")
    version_metadata = load_json_object(version_file, "release version metadata")
    version_key = config.get("version_key")
    if not isinstance(version_key, str):
        raise ValueError("plugin distribution version_key must be a string")
    version = version_metadata.get(version_key)
    if not isinstance(version, str):
        raise ValueError("configured plugin distribution version is missing")
    return version


def build_distribution_tree(
    repository_root: Path,
    *,
    version: str,
    source_revision: str,
    allowlist_path: Path | None = None,
) -> DistributionTree:
    """Build a deterministic in-memory standalone Plugin repository."""

    _validate_release_identity(version, source_revision)
    repository_root = Path(repository_root).resolve()
    config_path = repository_root / "release" / "plugin-distribution.json"
    config = _load_distribution_config(repository_root, config_path)

    source_root_name = str(config["source_root"])
    source_root_relative = parse_safe_relative_posix_path(source_root_name)
    source_root = repository_root.joinpath(*source_root_relative.parts)
    selected_allowlist = (
        Path(allowlist_path)
        if allowlist_path is not None
        else _config_relative_file(repository_root, config, "source_allowlist")
    )
    source_files = _load_allowlist(selected_allowlist)

    files: dict[PurePosixPath, bytes] = {}
    for relative_name in source_files:
        relative, source = _safe_repository_path(
            source_root,
            relative_name,
            description="source allowlist file",
        )
        files[relative] = _transform_source_file(
            relative,
            source.read_bytes(),
            version,
        )

    packaging = _packaging_entries(
        repository_root,
        config,
        version=version,
        source_revision=source_revision,
    )
    collisions = set(files).intersection(packaging)
    if collisions:
        names = ", ".join(path.as_posix() for path in sorted(collisions))
        raise ValueError(f"packaging output collides with source allowlist: {names}")
    files.update(packaging)
    release_path = PurePosixPath("release.json")
    if release_path in files:
        raise ValueError("release.json output must be generated, not copied")
    files[release_path] = canonical_json(
        {
            "canonical_repository": CANONICAL_REPOSITORY,
            "channel": "latest",
            "source_revision": source_revision,
            "target_repository": TARGET_REPOSITORY,
            "version": version,
        }
    )

    ordered_files = dict(sorted(files.items(), key=lambda item: item[0].as_posix()))
    return DistributionTree(
        files=ordered_files,
        version=version,
        source_revision=source_revision,
    )


def _expected_directories(tree: DistributionTree) -> set[PurePosixPath]:
    directories = {PurePosixPath(".")}
    for relative in tree.files:
        parent = relative.parent
        while parent != PurePosixPath("."):
            directories.add(parent)
            parent = parent.parent
    return directories


def _validate_existing_output(tree: DistributionTree, output_dir: Path) -> None:
    if not output_dir.exists():
        return
    if output_dir.is_symlink() or not output_dir.is_dir():
        raise ValueError("distribution output must be a regular directory")

    expected_files = set(tree.files)
    expected_directories = _expected_directories(tree)
    unexpected: list[str] = []
    for path in output_dir.rglob("*"):
        relative = PurePosixPath(path.relative_to(output_dir).as_posix())
        valid_file = (
            relative in expected_files and path.is_file() and not path.is_symlink()
        )
        valid_directory = (
            relative in expected_directories
            and path.is_dir()
            and not path.is_symlink()
        )
        if not valid_file and not valid_directory:
            unexpected.append(relative.as_posix())
    if unexpected:
        raise ValueError(
            "unexpected existing distribution output: "
            + ", ".join(sorted(unexpected)[:8])
        )


def write_distribution_tree(tree: DistributionTree, output_dir: Path) -> None:
    """Materialize a tree without deleting or accepting unexpected output."""

    output_dir = Path(output_dir)
    _validate_existing_output(tree, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if output_dir.is_symlink():
        raise ValueError("distribution output symlink is forbidden")
    resolved_output = output_dir.resolve()

    for relative, content in tree.files.items():
        safe_relative = parse_safe_relative_posix_path(relative.as_posix())
        target = output_dir.joinpath(*safe_relative.parts)
        try:
            target.resolve(strict=False).relative_to(resolved_output)
        except ValueError as error:
            raise ValueError(f"unsafe distribution output path: {relative}") from error
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        try:
            with temporary.open("wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--version")
    parser.add_argument("--check-determinism", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repository_root = DEFAULT_REPOSITORY_ROOT.resolve()
        config = _load_distribution_config(
            repository_root,
            DEFAULT_DISTRIBUTION_CONFIG,
        )
        version = args.version or configured_version(repository_root, config)
        tree = build_distribution_tree(
            repository_root,
            version=version,
            source_revision=args.source_revision,
        )
        if args.check_determinism:
            repeated = build_distribution_tree(
                repository_root,
                version=version,
                source_revision=args.source_revision,
            )
            if tree != repeated:
                raise RuntimeError("plugin distribution build is not deterministic")
        write_distribution_tree(tree, args.output_dir)
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
