from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Mapping


ROOT = Path(__file__).resolve().parents[3]
# 以 -I 隔離模式啟動時，腳本所在目錄不在 sys.path；明確載入同目錄的 Codex driver，
# 讓兩個 driver 共用完全相同的路由驗證、證據檢查與同意狀態機。
_CODEX_DRIVER_PATH = Path(__file__).resolve().with_name("codex_cli_driver.py")
_SPEC = importlib.util.spec_from_file_location("codex_cli_driver", _CODEX_DRIVER_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("codex_cli_driver_unavailable")
_CODEX_DRIVER = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("codex_cli_driver", _CODEX_DRIVER)
_SPEC.loader.exec_module(_CODEX_DRIVER)

CodexCliDriver = _CODEX_DRIVER.CodexCliDriver
EvaluationIntegrityError = _CODEX_DRIVER.EvaluationIntegrityError
EvidenceProtectionError = _CODEX_DRIVER.EvidenceProtectionError
LocalEvidenceProtector = _CODEX_DRIVER.LocalEvidenceProtector

# Claude Code 只接受明確設定的授權；桌面 App 或使用者設定目錄裡的登入狀態一律不讀。
AUTH_ENVIRONMENT = ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")
_ENV_ALLOWLIST = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "PATH",
    "SSL_CERT_FILE",
    "SystemRoot",
    "WINDIR",
    *AUTH_ENVIRONMENT,
)
_EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")


class ClaudeCodeDriver(CodexCliDriver):
    """Execute each turn in a fresh, user-config-free Claude Code process."""

    _PRIVATE_DIRECTORIES = ("workspace", "runtime-home", "runtime-tmp", "claude-config")

    def __init__(
        self,
        claude_executable: Path,
        output_schema: Path,
        attempt_root: Path,
        *,
        timeout_seconds: int = 120,
        model: str | None = None,
        reasoning_effort: str | None = None,
    ) -> None:
        self._claude_executable = claude_executable.resolve()
        self._output_schema = output_schema.resolve()
        self._attempt_root = attempt_root.resolve()
        self._timeout_seconds = timeout_seconds
        self._model = model
        if reasoning_effort not in {None, *_EFFORT_LEVELS}:
            raise ValueError("claude_driver_reasoning_effort_invalid")
        self._reasoning_effort = reasoning_effort
        self._evidence_protector = LocalEvidenceProtector()
        if not self._claude_executable.is_absolute() or not self._output_schema.is_absolute():
            raise ValueError("claude_driver_paths_must_be_absolute")
        if timeout_seconds <= 0:
            raise ValueError("claude_driver_timeout_must_be_positive")
        if not any(os.environ.get(name) for name in AUTH_ENVIRONMENT):
            raise ValueError("claude_driver_auth_missing")
        self._attempt_root.mkdir(parents=True, exist_ok=True)
        try:
            self._evidence_protector.protect_directory(self._attempt_root)
        except EvidenceProtectionError as error:
            raise EvaluationIntegrityError("claude_attempt_root_unprotected") from error

    def _invoke(
        self,
        directory: Path,
        prompt: str,
        output_schema: Path,
    ) -> tuple[subprocess.CompletedProcess[str], float]:
        """Run one isolated Claude Code print-mode turn without tools or user state."""
        try:
            loaded = json.loads(output_schema.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise EvaluationIntegrityError("claude_output_schema_unreadable") from error
        if not isinstance(loaded, dict):
            raise EvaluationIntegrityError("claude_output_schema_unreadable")
        # Claude CLI 的 --json-schema 驗證器不認得 draft 2020-12 的 $schema 宣告；
        # 共用的 schema 只用到 draft-07 也有的關鍵字，拿掉宣告不改變驗證內容。
        loaded.pop("$schema", None)
        schema = json.dumps(loaded, ensure_ascii=False, separators=(",", ":"))
        command = [
            str(self._claude_executable),
            "--print",
            "--output-format",
            "json",
            "--json-schema",
            schema,
            "--tools",
            "",
            "--strict-mcp-config",
            "--disable-slash-commands",
            "--no-session-persistence",
        ]
        if self._model:
            command += ["--model", self._model]
        if self._reasoning_effort:
            command += ["--effort", self._reasoning_effort]
        home = directory / "runtime-home"
        temporary = directory / "runtime-tmp"
        environment = {name: os.environ[name] for name in _ENV_ALLOWLIST if name in os.environ}
        environment.update({
            "CLAUDE_CONFIG_DIR": str(directory / "claude-config"),
            "HOME": str(home),
            "USERPROFILE": str(home),
            "APPDATA": str(home),
            "LOCALAPPDATA": str(home),
            "TEMP": str(temporary),
            "TMP": str(temporary),
            "TMPDIR": str(temporary),
            "DISABLE_AUTOUPDATER": "1",
            "DISABLE_TELEMETRY": "1",
            "DISABLE_ERROR_REPORTING": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        })
        try:
            started = time.perf_counter()
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
            elapsed_ms = (time.perf_counter() - started) * 1000
        except subprocess.TimeoutExpired as error:
            raise EvaluationIntegrityError("claude_cli_timeout") from error
        except OSError as error:
            raise EvaluationIntegrityError("claude_cli_start_failed") from error
        if completed.returncode != 0:
            self._write_failure_diagnostic(directory / "failure.json", completed)
            raise EvaluationIntegrityError("claude_cli_failed")
        return completed, elapsed_ms

    @staticmethod
    def _result_event(stdout: str) -> dict[str, object] | None:
        try:
            event = json.loads(stdout)
        except json.JSONDecodeError:
            return None
        if not isinstance(event, dict) or event.get("type") != "result":
            return None
        return event

    @staticmethod
    def _extract_object(
        stdout: str,
        required_keys: set[str],
    ) -> dict[str, object]:
        event = ClaudeCodeDriver._result_event(stdout)
        if event is None or event.get("is_error") is True or event.get("subtype") != "success":
            raise EvaluationIntegrityError("claude_route_output_missing")
        structured = event.get("structured_output")
        if isinstance(structured, dict):
            return structured
        result = event.get("result")
        if isinstance(result, str):
            try:
                parsed = json.loads(result)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                return parsed
        raise EvaluationIntegrityError("claude_route_output_missing")

    @staticmethod
    def _extract_usage(stdout: str) -> dict[str, int] | None:
        """把 Claude 的快取分項換算成與 Codex 相同的三個欄位；缺漏時回傳 None。"""
        event = ClaudeCodeDriver._result_event(stdout)
        usage = event.get("usage") if event is not None else None
        if not isinstance(usage, dict):
            return None
        fields = (
            "input_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
            "output_tokens",
        )
        if not all(type(usage.get(key)) is int and usage[key] >= 0 for key in fields):
            return None
        return {
            "input_tokens": (
                usage["input_tokens"]
                + usage["cache_creation_input_tokens"]
                + usage["cache_read_input_tokens"]
            ),
            "cached_input_tokens": usage["cache_read_input_tokens"],
            "output_tokens": usage["output_tokens"],
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Workflow Skill Router Claude Code evaluation driver", allow_abbrev=False,
    )
    parser.add_argument("--claude-executable", required=True, type=Path)
    parser.add_argument(
        "--output-schema",
        type=Path,
        default=ROOT / "evaluation" / "v2" / "schemas" / "codex-route-output.schema.json",
    )
    parser.add_argument(
        "--attempt-root",
        type=Path,
        default=ROOT / "dist" / "evaluation" / "v2" / "claude-attempts",
    )
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--model")
    parser.add_argument("--reasoning-effort", choices=_EFFORT_LEVELS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    driver = ClaudeCodeDriver(
        args.claude_executable,
        args.output_schema.resolve(),
        args.attempt_root.resolve(),
        timeout_seconds=args.timeout_seconds,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
    )
    response = json.dumps(driver.handle(request), ensure_ascii=False, sort_keys=True).encode("utf-8")
    sys.stdout.buffer.write(response + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
