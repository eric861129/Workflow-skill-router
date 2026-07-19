from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys
import zipfile


PLUGIN = Path(__file__).resolve().parents[1]
ROOT = PLUGIN.parents[1]
SOURCE = ROOT / "packages" / "router-core" / "src"
OUTPUT = PLUGIN / "runtime" / "workflow_skill_router.pyz"
ENTRYPOINT = b"from workflow_skill_router.cli import main\nraise SystemExit(main())\n"


def eligible_files() -> list[Path]:
    result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", "packages/router-core/src/workflow_skill_router"],
                            cwd=ROOT, text=True, capture_output=True, check=True)
    files = []
    for name in result.stdout.splitlines():
        path = ROOT / name
        if not path.is_file(): continue
        relative = path.relative_to(SOURCE)
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}: continue
        if path.suffix not in {".py", ".json", ".sql"}: raise SystemExit(f"unexpected runtime extension: {relative}")
        if path.is_symlink(): raise SystemExit(f"runtime symlink forbidden: {relative}")
        files.append(path)
    return sorted(files, key=lambda path: path.relative_to(SOURCE).as_posix())


def build_bytes() -> bytes:
    import io
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        members = [("__main__.py", ENTRYPOINT)] + [
            (path.relative_to(SOURCE).as_posix(), path.read_bytes()) for path in eligible_files()
        ]
        for name, data in members:
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3; info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    data = build_bytes()
    if args.check:
        actual = args.output.read_bytes() if args.output.is_file() else None
        if actual == data:
            return 0
        expected_digest = sha256(data).hexdigest()
        actual_digest = sha256(actual).hexdigest() if actual is not None else "missing"
        print(
            "runtime archive mismatch: "
            f"expected sha256:{expected_digest}, actual sha256:{actual_digest}",
            file=sys.stderr,
        )
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + ".tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(data); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, args.output)
    finally:
        if temporary.exists(): temporary.unlink()
    print(f"{args.output} sha256:{sha256(data).hexdigest()}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
