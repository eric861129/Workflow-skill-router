from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

try:
    from .legacy_cli_cases import LegacyCliCase
except ImportError:  # pragma: no cover - 支援直接執行 compat 目錄內腳本。
    from legacy_cli_cases import LegacyCliCase


REPO_ROOT = Path(__file__).resolve().parents[4]
CONTROLLED_ENV = (
    "WORKFLOW_SKILL_ROUTER_SKILLS_ROOT",
    "WORKFLOW_SKILL_ROUTER_EXCLUDE_NAMES",
    "WORKFLOW_SKILL_ROUTER_EXCLUDE_PREFIXES",
    "WORKFLOW_SKILL_ROUTER_PRIVATE_MARKERS",
    "WORKFLOW_SKILL_ROUTER_PUBLIC_FORBIDDEN_MARKERS",
)


def _normalize_text(
    value: str,
    tmp: Path,
    exact_replacements: tuple[tuple[str, str], ...] = (),
) -> str:
    normalized = value.replace("\r\n", "\n")
    path_replacements = (
        (str(REPO_ROOT), "{repo}"),
        (REPO_ROOT.as_posix(), "{repo}"),
        (str(REPO_ROOT.resolve()), "{repo}"),
        (REPO_ROOT.resolve().as_posix(), "{repo}"),
        (str(tmp), "{tmp}"),
        (tmp.as_posix(), "{tmp}"),
        (str(tmp.resolve()), "{tmp}"),
        (tmp.resolve().as_posix(), "{tmp}"),
    )
    for source, replacement in (*path_replacements, *exact_replacements):
        normalized = normalized.replace(source, replacement)
    return normalized


def _artifact(path: Path, tmp: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    result: dict[str, Any] = {
        "path": path.relative_to(tmp).as_posix(),
        "size": len(raw),
    }
    if path.suffix in {".json", ".jsonl", ".md", ".txt"}:
        text = _normalize_text(raw.decode("utf-8"), tmp)
        result["sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        result["text"] = text
        if path.suffix == ".json":
            document = json.loads(text)
            result["json_top_level"] = type(document).__name__
            result["json_keys"] = sorted(document) if isinstance(document, dict) else []
    else:
        result["sha256"] = hashlib.sha256(raw).hexdigest()
    return result


def run_case(case: LegacyCliCase) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="router-v1-golden-") as raw_tmp:
        tmp = Path(raw_tmp)
        for relative, content in sorted(case.input_files.items()):
            destination = tmp / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
        argv = [part.replace("{tmp}", str(tmp)) for part in case.argv]
        env = os.environ.copy()
        for name in CONTROLLED_ENV:
            env.pop(name, None)
        env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", **case.env})
        process = subprocess.Popen(
            [sys.executable, *argv],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="strict",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = process.communicate()
        exact_replacements = ((f"run-{process.pid}", "{run-id}"),)
        return {
            "argv": list(case.argv),
            "env_overrides": {name: case.env[name] for name in sorted(case.env)},
            "exit_code": process.returncode,
            "stdout": _normalize_text(stdout, tmp, exact_replacements),
            "stderr": _normalize_text(stderr, tmp, exact_replacements),
            "artifacts": [_artifact(tmp / name, tmp) for name in case.artifact_paths],
        }
