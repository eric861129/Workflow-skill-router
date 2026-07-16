from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

from workflow_skill_router.schemas.artifacts import canonical_json_bytes

from .contracts import EvaluationIntegrityError, ModelExecutionPayload, ModelTurnRequest


class SubprocessExecutionAdapter:
    """透過受信任的 argv 設定執行隔離的單次 JSON 請求。"""

    kind = "subprocess"

    def __init__(
        self,
        command: tuple[str, ...],
        timeout_seconds: int = 120,
        maximum_output_bytes: int = 1_048_576,
    ) -> None:
        if (
            not isinstance(command, tuple)
            or not command
            or not all(isinstance(item, str) and "\0" not in item for item in command)
            or not command[0].strip()
            or not Path(command[0]).is_absolute()
        ):
            raise ValueError("subprocess_command_requires_absolute_executable_tuple")
        if timeout_seconds <= 0:
            raise ValueError("subprocess_timeout_must_be_positive")
        if maximum_output_bytes <= 0:
            raise ValueError("subprocess_output_limit_must_be_positive")
        self._command = command
        self._timeout_seconds = timeout_seconds
        self._maximum_output_bytes = maximum_output_bytes
        self._context_ids: set[str] = set()
        self._active: tuple[str, str] | None = None

    def start_attempt(self, payload: ModelExecutionPayload, attempt_nonce: str) -> str:
        if not attempt_nonce:
            raise EvaluationIntegrityError("attempt_nonce_missing")
        response = self._invoke({
            "type": "start_attempt",
            "opaque_run_case_id": payload.opaque_run_case_id,
            "prompt": payload.prompt,
            "profile": payload.profile.value,
            "allowed_tools": list(payload.allowed_tools),
            "attempt_nonce": attempt_nonce,
        })
        self._verify_nonce(response, attempt_nonce)
        context_id = response.get("context_id")
        if not isinstance(context_id, str) or not context_id:
            raise EvaluationIntegrityError("subprocess_context_invalid")
        if context_id in self._context_ids:
            raise EvaluationIntegrityError("subprocess_context_not_fresh")
        self._context_ids.add(context_id)
        self._active = (context_id, attempt_nonce)
        return context_id

    def execute_turn(self, request: ModelTurnRequest) -> Mapping[str, Any]:
        if self._active is None or request.attempt_nonce != self._active[1]:
            raise EvaluationIntegrityError("attempt_context_mismatch")
        context_id, attempt_nonce = self._active
        response = self._invoke({
            "type": "execute_turn",
            "context_id": context_id,
            "attempt_nonce": attempt_nonce,
            "turn_index": request.turn_index,
            "prompt": request.prompt,
            "allowed_tools": list(request.allowed_tools),
        })
        self._verify_nonce(response, attempt_nonce)
        if response.get("context_id") != context_id:
            raise EvaluationIntegrityError("attempt_context_mismatch")
        return response

    def _invoke(self, message: Mapping[str, object]) -> Mapping[str, Any]:
        try:
            completed = subprocess.run(
                self._command,
                shell=False,
                input=canonical_json_bytes(message),
                capture_output=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise EvaluationIntegrityError("subprocess_timeout") from error
        except OSError as error:
            raise EvaluationIntegrityError("subprocess_start_failed") from error

        output_size = len(completed.stdout) + len(completed.stderr)
        if output_size > self._maximum_output_bytes:
            raise EvaluationIntegrityError("subprocess_output_too_large")
        if completed.returncode != 0:
            raise EvaluationIntegrityError("subprocess_failed")
        try:
            response = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise EvaluationIntegrityError("subprocess_response_not_json") from error
        if not isinstance(response, dict):
            raise EvaluationIntegrityError("subprocess_response_not_object")
        return response

    @staticmethod
    def _verify_nonce(response: Mapping[str, Any], attempt_nonce: str) -> None:
        if response.get("attempt_nonce") != attempt_nonce:
            raise EvaluationIntegrityError("attempt_context_mismatch")
