from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
from typing import Mapping


ROOT = Path(__file__).resolve().parents[3]
CORE_SOURCE = ROOT / "packages" / "router-core" / "src"
if str(CORE_SOURCE) not in sys.path:
    sys.path.insert(0, str(CORE_SOURCE))

from workflow_skill_router.evaluation.contracts import EvaluationIntegrityError
from workflow_skill_router.evaluation.local_evidence import (
    EvidenceProtectionError,
    LocalEvidenceProtector,
)


_CONTEXT_ID = re.compile(r"^[a-f0-9]{32}$")
_SENSITIVE_FRAGMENT = re.compile(
    r"(?i)(bearer\s+\S+|(?:api[_-]?key|token|secret|password|authorization)[^\r\n]{0,200})",
)
_WINDOWS_PATH = re.compile(r"[A-Za-z]:\\[^\s\"']+")
_UNIX_PATH = re.compile(r"(?<!:)\/(?:home|Users|tmp|var)\/[^\s\"']+")
_ENV_ALLOWLIST = (
    "CODEX_HOME",
    "APPDATA",
    "HOME",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "OPENAI_API_KEY",
    "PATH",
    "LOCALAPPDATA",
    "SSL_CERT_FILE",
    "SystemRoot",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "WINDIR",
)
_ROUTE_KEYS = {
    "envelope",
    "selection_mode",
    "primary_skill",
    "support_skills",
    "consent_action",
    "goal_relation",
    "rationale",
}


class CodexCliDriver:
    """Execute each turn in a fresh, user-config-free Codex CLI process."""

    def __init__(
        self,
        codex_executable: Path,
        output_schema: Path,
        attempt_root: Path,
        *,
        timeout_seconds: int = 120,
        auth_source: Path | None = None,
        model: str | None = None,
    ) -> None:
        self._codex_executable = codex_executable.resolve()
        self._output_schema = output_schema.resolve()
        self._attempt_root = attempt_root.resolve()
        self._timeout_seconds = timeout_seconds
        self._auth_source = (auth_source or self._default_auth_source()).resolve()
        self._model = model
        self._evidence_protector = LocalEvidenceProtector()
        if not self._codex_executable.is_absolute() or not self._output_schema.is_absolute():
            raise ValueError("codex_driver_paths_must_be_absolute")
        if timeout_seconds <= 0:
            raise ValueError("codex_driver_timeout_must_be_positive")
        if not self._auth_source.is_file():
            raise ValueError("codex_driver_auth_source_missing")
        self._attempt_root.mkdir(parents=True, exist_ok=True)
        try:
            self._evidence_protector.protect_directory(self._attempt_root)
        except EvidenceProtectionError as error:
            raise EvaluationIntegrityError("codex_attempt_root_unprotected") from error

    def handle(self, request: Mapping[str, object]) -> dict[str, object]:
        message_type = request.get("type")
        if message_type == "start_attempt":
            return self._start(request)
        if message_type == "execute_turn":
            return self._execute(request)
        raise EvaluationIntegrityError("codex_driver_message_type_invalid")

    def _start(self, request: Mapping[str, object]) -> dict[str, object]:
        nonce = request.get("attempt_nonce")
        if not isinstance(nonce, str) or not nonce:
            raise EvaluationIntegrityError("attempt_nonce_missing")
        while True:
            context_id = secrets.token_hex(16)
            directory = self._attempt_root / context_id
            try:
                directory.mkdir()
                self._evidence_protector.protect_directory(directory)
                break
            except FileExistsError:
                continue
            except EvidenceProtectionError as error:
                raise EvaluationIntegrityError("codex_attempt_directory_unprotected") from error
        transcript = directory / "transcript.json"
        for name in ("workspace", "runtime-home", "codex-home"):
            private_directory = directory / name
            private_directory.mkdir()
            try:
                self._evidence_protector.protect_directory(private_directory)
            except EvidenceProtectionError as error:
                raise EvaluationIntegrityError("codex_attempt_directory_unprotected") from error
        self._write_transcript(transcript, {
            "attempt_nonce": nonce,
            "opaque_run_case_id": request.get("opaque_run_case_id"),
            "turns": [],
        })
        return {"attempt_nonce": nonce, "context_id": context_id}

    def _execute(self, request: Mapping[str, object]) -> dict[str, object]:
        context_id = request.get("context_id")
        nonce = request.get("attempt_nonce")
        if not isinstance(context_id, str) or not _CONTEXT_ID.fullmatch(context_id):
            raise EvaluationIntegrityError("codex_context_invalid")
        directory = (self._attempt_root / context_id).resolve()
        if directory.parent != self._attempt_root or not directory.is_dir():
            raise EvaluationIntegrityError("codex_context_missing")
        transcript_path = directory / "transcript.json"
        if (
            not self._evidence_protector.verify_directory(directory)
            or not self._evidence_protector.verify_file(transcript_path)
        ):
            raise EvaluationIntegrityError("codex_context_unprotected")
        transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
        if nonce != transcript.get("attempt_nonce"):
            raise EvaluationIntegrityError("attempt_context_mismatch")
        turns = transcript.get("turns")
        if not isinstance(turns, list) or request.get("turn_index") != len(turns):
            raise EvaluationIntegrityError("codex_turn_order_invalid")

        prompt = self._render_prompt(turns, request)
        command = [
            str(self._codex_executable),
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--strict-config",
            "--disable",
            "plugins",
            "-c",
            "skills.bundled.enabled=false",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--cd",
            str(directory / "workspace"),
            "--output-schema",
            str(self._output_schema),
            "--json",
            "-",
        ]
        if self._model:
            command[command.index("--output-schema"):command.index("--output-schema")] = [
                "--model", self._model,
            ]
        environment = {name: os.environ[name] for name in _ENV_ALLOWLIST if name in os.environ}
        environment.update({
            "CODEX_HOME": str(directory / "codex-home"),
            "HOME": str(directory / "runtime-home"),
            "USERPROFILE": str(directory / "runtime-home"),
        })
        isolated_auth = directory / "codex-home" / "auth.json"
        try:
            try:
                shutil.copyfile(self._auth_source, isolated_auth)
                self._evidence_protector.protect_file(isolated_auth)
                completed = subprocess.run(
                    command,
                    shell=False,
                    cwd=directory / "workspace",
                    input=prompt,
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    timeout=self._timeout_seconds,
                    check=False,
                    env=environment,
                )
            finally:
                isolated_auth.unlink(missing_ok=True)
        except subprocess.TimeoutExpired as error:
            raise EvaluationIntegrityError("codex_cli_timeout") from error
        except EvidenceProtectionError as error:
            raise EvaluationIntegrityError("codex_auth_unprotected") from error
        except OSError as error:
            raise EvaluationIntegrityError("codex_cli_start_failed") from error
        if completed.returncode != 0:
            self._write_failure_diagnostic(directory / "failure.json", completed)
            raise EvaluationIntegrityError("codex_cli_failed")
        route = self._extract_route(completed.stdout)
        self._validate_route(route)
        turns.append({"user": request.get("prompt"), "assistant": route})
        self._write_transcript(transcript_path, transcript)
        return {
            "attempt_nonce": nonce,
            "context_id": context_id,
            "route": route,
            "text": json.dumps(route, ensure_ascii=False, sort_keys=True),
        }

    @staticmethod
    def _render_prompt(turns: list[object], request: Mapping[str, object]) -> str:
        lines = [
            "Return one routing decision as JSON that conforms to the supplied output schema.",
            "Do not execute the task. Use only the capability names present in this conversation.",
            "Allowed tools: " + json.dumps(request.get("allowed_tools", []), ensure_ascii=False),
            "Conversation so far:",
        ]
        for turn in turns:
            if isinstance(turn, dict):
                lines.append("User: " + str(turn.get("user", "")))
                lines.append("Assistant: " + json.dumps(turn.get("assistant"), ensure_ascii=False, sort_keys=True))
        lines.append("Current user message: " + str(request.get("prompt", "")))
        return "\n".join(lines)

    @staticmethod
    def _extract_route(stdout: str) -> dict[str, object]:
        candidates: list[object] = []
        agent_candidates: list[object] = []
        for line in stdout.splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                item = event.get("item")
                if event.get("type") == "item.completed" and isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        try:
                            parsed = json.loads(text)
                            candidates.append(parsed)
                            agent_candidates.append(parsed)
                        except json.JSONDecodeError:
                            pass
                candidates.append(event)
        for candidate in reversed(candidates):
            if isinstance(candidate, dict) and _ROUTE_KEYS.issubset(candidate):
                return candidate
        if agent_candidates and isinstance(agent_candidates[-1], dict):
            return agent_candidates[-1]
        raise EvaluationIntegrityError("codex_route_output_missing")

    @staticmethod
    def _validate_route(route: Mapping[str, object]) -> None:
        valid = (
            set(route) == _ROUTE_KEYS
            and route.get("envelope") in {"single", "phased", "managed-goal"}
            and route.get("selection_mode") in {"auto", "explicit-locked"}
            and isinstance(route.get("primary_skill"), str)
            and bool(route.get("primary_skill"))
            and isinstance(route.get("support_skills"), list)
            and all(isinstance(item, str) for item in route.get("support_skills", []))
            and route.get("consent_action") in {
                "not-required", "proposal-required", "approved", "rejected",
            }
            and route.get("goal_relation") in {
                "none", "progress", "status", "steer", "side-question",
            }
            and isinstance(route.get("rationale"), str)
            and bool(route.get("rationale"))
        )
        if not valid:
            raise EvaluationIntegrityError("codex_route_schema_invalid")

    def _write_transcript(self, path: Path, payload: Mapping[str, object]) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        self._evidence_protector.protect_file(path)

    def _write_failure_diagnostic(
        self,
        path: Path,
        completed: subprocess.CompletedProcess[str],
    ) -> None:
        def sanitize(value: str) -> str:
            bounded = value[-16_384:]
            bounded = _SENSITIVE_FRAGMENT.sub("[REDACTED]", bounded)
            return _UNIX_PATH.sub("[LOCAL_PATH]", _WINDOWS_PATH.sub("[LOCAL_PATH]", bounded))

        path.write_text(json.dumps({
            "returncode": completed.returncode,
            "stderr": sanitize(completed.stderr or ""),
            "stdout": sanitize(completed.stdout or ""),
        }, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        self._evidence_protector.protect_file(path)

    @staticmethod
    def _default_auth_source() -> Path:
        codex_home = os.environ.get("CODEX_HOME")
        return Path(codex_home) / "auth.json" if codex_home else Path.home() / ".codex" / "auth.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Workflow Skill Router Codex CLI evaluation driver")
    parser.add_argument("--codex-executable", required=True, type=Path)
    parser.add_argument(
        "--output-schema",
        type=Path,
        default=ROOT / "evaluation" / "v2" / "schemas" / "codex-route-output.schema.json",
    )
    parser.add_argument(
        "--attempt-root",
        type=Path,
        default=ROOT / "dist" / "evaluation" / "v2" / "codex-attempts",
    )
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--auth-source", type=Path)
    parser.add_argument("--model")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    driver = CodexCliDriver(
        args.codex_executable,
        args.output_schema.resolve(),
        args.attempt_root.resolve(),
        timeout_seconds=args.timeout_seconds,
        auth_source=args.auth_source.resolve() if args.auth_source else None,
        model=args.model,
    )
    response = json.dumps(driver.handle(request), ensure_ascii=False, sort_keys=True).encode("utf-8")
    sys.stdout.buffer.write(response + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
