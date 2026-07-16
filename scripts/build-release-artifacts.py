from __future__ import annotations

import argparse
from hashlib import sha256
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = ROOT / "downloads"
RELEASE = ROOT / "release"
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def zip_bytes(entries: list[tuple[str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, content in sorted(entries):
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts: raise ValueError("unsafe archive path")
            info = zipfile.ZipInfo(name, FIXED_TIME); info.create_system = 3; info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    return buffer.getvalue()


def tree_entries(root: Path, archive_root: str, excluded_dirs=(), excluded_files=()) -> list[tuple[str, bytes]]:
    entries = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in excluded_files or any(part in excluded_dirs for part in path.relative_to(root).parts): continue
        if path.is_symlink(): raise ValueError(f"symlink forbidden: {path}")
        entries.append((f"{archive_root}/{path.relative_to(root).as_posix()}", path.read_bytes()))
    return entries


def git(*arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=ROOT, text=True, encoding="utf-8",
                          capture_output=True, check=True).stdout.strip()


def import_v1() -> tuple[bytes, dict[str, object]]:
    tag = "v1.3.1"; prefix = "starter/workflow-skill-router/"
    names = git("ls-tree", "-r", "--name-only", tag, prefix).splitlines()
    entries, blobs = [], []
    for name in sorted(names):
        content = subprocess.run(["git", "show", f"{tag}:{name}"], cwd=ROOT, capture_output=True, check=True).stdout
        archive_name = "workflow-skill-router/" + name.removeprefix(prefix)
        entries.append((archive_name, content))
        blobs.append({"path": name, "blob": git("rev-parse", f"{tag}:{name}"), "sha256": sha256(content).hexdigest()})
    archive = zip_bytes(entries)
    provenance = {
        "schema_version": "1.0", "version": "1.3.1", "source_tag": tag,
        "tag_object": git("rev-parse", tag), "peeled_commit": git("rev-parse", f"{tag}^{{commit}}"),
        "source_tree": git("rev-parse", f"{tag}^{{tree}}"), "files": blobs,
        "archive_sha256": sha256(archive).hexdigest(), "archive_size": len(archive),
        "builder": "workflow-skill-router-v2-release-builder", "license": "MIT",
    }
    return archive, provenance


def artifacts() -> dict[Path, bytes]:
    version = json.loads((RELEASE / "version.json").read_text(encoding="utf-8"))
    v2 = version["v2_version"]
    skill = zip_bytes(tree_entries(ROOT / "starter/v2/workflow-skill-router", "workflow-skill-router"))
    plugin = zip_bytes(tree_entries(ROOT / "plugins/workflow-skill-router", "workflow-skill-router",
                                    ("node_modules", ".test-build"), (".gitignore",)))
    v1_archive, provenance = import_v1()
    files: dict[Path, bytes] = {
        DOWNLOADS / "archive/workflow-skill-router-skill-v1.3.1.zip": v1_archive,
        RELEASE / "provenance/v1.3.1.json": canonical(provenance),
        DOWNLOADS / f"workflow-skill-router-skill-v{v2}.zip": skill,
        DOWNLOADS / f"workflow-skill-router-plugin-v{v2}.zip": plugin,
    }
    asset_rows = []
    for path, data in sorted(files.items(), key=lambda pair: pair[0].as_posix()):
        if path.suffix == ".zip": asset_rows.append({"name": path.name, "sha256": sha256(data).hexdigest(), "size": len(data)})
    release_manifest = {"schema_version": "2.0", "version": v2, "channel": "latest-v2", "assets": asset_rows}
    files[DOWNLOADS / f"release-manifest-v{v2}.json"] = canonical(release_manifest)
    for channel, target_version, asset in (
        ("latest", "1.3.1", "workflow-skill-router-skill-v1.3.1.zip"),
        ("latest-v1", "1.3.1", "workflow-skill-router-skill-v1.3.1.zip"),
        ("latest-v2", v2, f"workflow-skill-router-plugin-v{v2}.zip"),
    ):
        files[DOWNLOADS / f"channels/{channel}.json"] = canonical({
            "schema_version": "1.0", "channel": channel, "version": target_version, "asset": asset,
        })
    sbom = {"spdxVersion": "SPDX-2.3", "dataLicense": "CC0-1.0", "SPDXID": "SPDXRef-DOCUMENT",
            "name": f"workflow-skill-router-{v2}", "documentNamespace": f"https://example.invalid/workflow-skill-router/{v2}",
            "packages": [{"name": "workflow-skill-router", "SPDXID": "SPDXRef-Package", "versionInfo": v2,
                          "licenseConcluded": "MIT", "downloadLocation": "NOASSERTION"}]}
    files[DOWNLOADS / f"sbom/workflow-skill-router-v{v2}.spdx.json"] = canonical(sbom)
    checksums = "".join(f"{sha256(data).hexdigest()}  {path.relative_to(DOWNLOADS).as_posix()}\n"
                        for path, data in sorted(files.items(), key=lambda pair: pair[0].as_posix()) if path.is_relative_to(DOWNLOADS))
    files[DOWNLOADS / "checksums.sha256"] = checksums.encode()
    return files


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--check", action="store_true"); args = parser.parse_args()
    generated = artifacts()
    if args.check:
        stale = [str(path.relative_to(ROOT)) for path, data in generated.items() if not path.is_file() or path.read_bytes() != data]
        if stale: print("stale release artifacts: " + ", ".join(stale)); return 1
        return 0
    for path, data in generated.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        try:
            with temporary.open("wb") as handle: handle.write(data); handle.flush(); os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists(): temporary.unlink()
    return 0


if __name__ == "__main__": raise SystemExit(main())
