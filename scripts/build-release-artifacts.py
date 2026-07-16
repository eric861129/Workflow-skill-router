from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release"
PLUGIN_ROOT = ROOT / "plugins" / "workflow-skill-router"
SKILL_ROOT = ROOT / "starter" / "v2" / "workflow-skill-router"
DEFAULT_OUTPUT = ROOT / "dist" / "release"
FIXED_TIME = (1980, 1, 1, 0, 0, 0)
REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class BuildProvenance:
    """Describe whether generated release evidence is publishable."""

    mode: str
    source_revision: str | None
    source_tree: str | None

    @property
    def publishable(self) -> bool:
        return self.mode == "release"


def canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def zip_bytes(entries: list[tuple[str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, content in sorted(entries):
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts:
                raise ValueError(f"unsafe archive path: {name}")
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    return buffer.getvalue()


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    ).stdout.strip()


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path.relative_to(ROOT)}")
    return value


def safe_allowlist_entries(
    source_root: Path,
    archive_root: str,
    allowlist_path: Path,
    *,
    require_all: bool,
) -> list[tuple[str, bytes]]:
    allowlist = load_json(allowlist_path)
    raw_files = allowlist.get("files")
    if not isinstance(raw_files, list) or not all(
        isinstance(value, str) for value in raw_files
    ):
        raise ValueError(f"invalid file allowlist: {allowlist_path.relative_to(ROOT)}")
    if raw_files != sorted(set(raw_files)):
        raise ValueError(f"allowlist must be sorted and unique: {allowlist_path.relative_to(ROOT)}")

    entries: list[tuple[str, bytes]] = []
    for relative_name in raw_files:
        relative = PurePosixPath(relative_name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe allowlist path: {relative_name}")
        path = source_root.joinpath(*relative.parts)
        if not path.is_file():
            if require_all:
                raise FileNotFoundError(path)
            continue
        if path.is_symlink():
            raise ValueError(f"symlink forbidden: {path.relative_to(ROOT)}")
        entries.append((f"{archive_root}/{relative.as_posix()}", path.read_bytes()))
    return entries


def build_sbom(version: str) -> bytes:
    package = load_json(PLUGIN_ROOT / "package.json")
    dependencies = package["dependencies"]
    development = package["devDependencies"]
    packages = [
        {
            "SPDXID": "SPDXRef-Package-WorkflowSkillRouter",
            "downloadLocation": "NOASSERTION",
            "licenseConcluded": "MIT",
            "name": "workflow-skill-router",
            "primaryPackagePurpose": "APPLICATION",
            "versionInfo": version,
        },
        {
            "SPDXID": "SPDXRef-Package-ModelContextProtocolSDK",
            "downloadLocation": "NOASSERTION",
            "licenseConcluded": "NOASSERTION",
            "name": "@modelcontextprotocol/sdk",
            "primaryPackagePurpose": "LIBRARY",
            "versionInfo": dependencies["@modelcontextprotocol/sdk"],
        },
        {
            "SPDXID": "SPDXRef-Package-Zod",
            "downloadLocation": "NOASSERTION",
            "licenseConcluded": "MIT",
            "name": "zod",
            "primaryPackagePurpose": "LIBRARY",
            "versionInfo": dependencies["zod"],
        },
        {
            "SPDXID": "SPDXRef-Package-Esbuild",
            "comment": "Build-only dependency; not shipped as a Plugin runtime file.",
            "downloadLocation": "NOASSERTION",
            "licenseConcluded": "MIT",
            "name": "esbuild",
            "primaryPackagePurpose": "BUILD_TOOL",
            "versionInfo": development["esbuild"],
        },
    ]
    return canonical(
        {
            "SPDXID": "SPDXRef-DOCUMENT",
            "creationInfo": {
                "creators": ["Tool: workflow-skill-router-v2-release-builder"],
                "created": "1980-01-01T00:00:00Z",
            },
            "dataLicense": "CC0-1.0",
            "documentNamespace": (
                "https://github.com/eric861129/Workflow-skill-router/"
                f"releases/v{version}/sbom"
            ),
            "name": f"workflow-skill-router-{version}",
            "packages": packages,
            "spdxVersion": "SPDX-2.3",
        }
    )


def artifacts(
    output_dir: Path,
    provenance: BuildProvenance,
) -> dict[Path, bytes]:
    """Build deterministic V2 release files under an explicit output directory."""

    version_metadata = load_json(RELEASE / "version.json")
    version = str(version_metadata["v2_version"])
    plugin = zip_bytes(
        safe_allowlist_entries(
            PLUGIN_ROOT,
            "workflow-skill-router",
            RELEASE / "allowlists" / "plugin-runtime-files.json",
            require_all=False,
        )
    )
    skill = zip_bytes(
        safe_allowlist_entries(
            SKILL_ROOT,
            "workflow-skill-router",
            RELEASE / "allowlists" / "skill-package.json",
            require_all=True,
        )
    )

    plugin_name = f"workflow-skill-router-plugin-v{version}.zip"
    skill_name = f"workflow-skill-router-skill-v{version}.zip"
    files: dict[Path, bytes] = {
        output_dir / plugin_name: plugin,
        output_dir / skill_name: skill,
        output_dir / "channels" / "latest.json": canonical(
            {
                "asset": "workflow-skill-router-skill-v1.3.1.zip",
                "channel": "latest",
                "schema_version": "1.0",
                "version": str(version_metadata["v1_pinned_version"]),
            }
        ),
        output_dir / "channels" / "latest-v1.json": canonical(
            {
                "asset": "workflow-skill-router-skill-v1.3.1.zip",
                "channel": "latest-v1",
                "schema_version": "1.0",
                "version": str(version_metadata["v1_pinned_version"]),
            }
        ),
        output_dir / "channels" / "latest-v2.json": canonical(
            {
                "asset": plugin_name,
                "channel": "latest-v2",
                "schema_version": "1.0",
                "version": version,
            }
        ),
        output_dir / "sbom" / f"workflow-skill-router-v{version}.spdx.json": (
            build_sbom(version)
        ),
    }

    release_assets = [
        {
            "name": plugin_name,
            "sha256": sha256(plugin).hexdigest(),
            "size": len(plugin),
        },
        {
            "name": skill_name,
            "sha256": sha256(skill).hexdigest(),
            "size": len(skill),
        },
    ]
    files[output_dir / f"release-manifest-v{version}.json"] = canonical(
        {
            "assets": release_assets,
            "channel": "latest-v2",
            "schema_version": "2.0",
            "version": version,
        }
    )

    artifact_hashes = {
        path.relative_to(output_dir).as_posix(): sha256(data).hexdigest()
        for path, data in sorted(files.items(), key=lambda pair: pair[0].as_posix())
    }
    files[
        output_dir / "provenance" / f"workflow-skill-router-v{version}.json"
    ] = canonical(
        {
            "artifact_sha256": artifact_hashes,
            "builder": "workflow-skill-router-v2-release-builder",
            "publishable": provenance.publishable,
            "schema_version": "1.0",
            "source_revision": provenance.source_revision,
            "source_tree": provenance.source_tree,
            "version": version,
        }
    )

    checksums = "".join(
        f"{sha256(data).hexdigest()}  {path.relative_to(output_dir).as_posix()}\n"
        for path, data in sorted(files.items(), key=lambda pair: pair[0].as_posix())
    )
    files[output_dir / "checksums.sha256"] = checksums.encode("utf-8")
    return files


def resolve_provenance(
    mode: str,
    source_revision: str | None,
    require_clean: bool,
) -> BuildProvenance:
    if mode == "test":
        if source_revision is not None or require_clean:
            raise ValueError(
                "test provenance cannot accept --source-revision or --require-clean"
            )
        return BuildProvenance("test", None, None)

    if source_revision is None or not REVISION_PATTERN.fullmatch(source_revision):
        raise ValueError("release provenance requires a full 40-character revision")
    if not require_clean:
        raise ValueError("release provenance requires --require-clean")
    head = git("rev-parse", "HEAD")
    if source_revision != head:
        raise ValueError("--source-revision does not match HEAD")
    dirty = git("status", "--porcelain=v1", "--untracked-files=no")
    if dirty:
        raise ValueError("release provenance requires a clean tracked worktree and index")
    return BuildProvenance("release", head, git("rev-parse", "HEAD^{tree}"))


def assert_deterministic(
    output_dir: Path,
    provenance: BuildProvenance,
    generated: dict[Path, bytes],
) -> None:
    repeated = artifacts(output_dir, provenance)
    first = {
        path.relative_to(output_dir).as_posix(): data
        for path, data in generated.items()
    }
    second = {
        path.relative_to(output_dir).as_posix(): data
        for path, data in repeated.items()
    }
    if first != second:
        raise RuntimeError("release artifact build is not deterministic")


def validate_output_directory(output_dir: Path) -> None:
    downloads = (ROOT / "downloads").resolve()
    if output_dir == downloads or downloads in output_dir.parents:
        raise ValueError(
            "release output cannot target the tracked downloads directory"
        )


def write_artifacts(generated: dict[Path, bytes]) -> None:
    for path, data in sorted(generated.items(), key=lambda pair: pair[0].as_posix()):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        try:
            with temporary.open("wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--provenance-mode",
        choices=("test", "release"),
        default="test",
    )
    parser.add_argument("--source-revision")
    parser.add_argument("--require-clean", action="store_true")
    parser.add_argument("--check-determinism", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        provenance = resolve_provenance(
            args.provenance_mode,
            args.source_revision,
            args.require_clean,
        )
        output_dir = args.output_dir.resolve()
        validate_output_directory(output_dir)
        generated = artifacts(output_dir, provenance)
        if args.check_determinism:
            assert_deterministic(output_dir, provenance, generated)
        write_artifacts(generated)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
