from __future__ import annotations

from .contracts import EvalRunAuthorization, EvaluationIntegrityError, ExecutionAdapter
from .subprocess_adapter import SubprocessExecutionAdapter


class AdapterRegistry:
    """保存由 host 啟動設定建立、不可由模型參數改寫的 adapter。"""

    def __init__(self, *registrations: tuple[str, ExecutionAdapter]) -> None:
        self._adapters: dict[str, ExecutionAdapter] = {}
        for adapter_id, adapter in registrations:
            if adapter_id in self._adapters:
                raise ValueError("duplicate_adapter_id")
            self._adapters[adapter_id] = adapter

    @classmethod
    def from_subprocess_command(
        cls,
        command: tuple[str, ...],
        *,
        timeout_seconds: int = 120,
        maximum_output_bytes: int = 1_048_576,
    ) -> "AdapterRegistry":
        adapter = SubprocessExecutionAdapter(
            command,
            timeout_seconds=timeout_seconds,
            maximum_output_bytes=maximum_output_bytes,
        )
        return cls((adapter.kind, adapter))

    def require(
        self,
        adapter_id: str,
        *,
        authorization: EvalRunAuthorization,
    ) -> ExecutionAdapter:
        if authorization.adapter_kind != adapter_id:
            raise EvaluationIntegrityError("adapter_authorization_mismatch")
        adapter = self._adapters.get(adapter_id)
        if adapter is None:
            raise EvaluationIntegrityError("adapter_not_configured")
        if adapter.kind != authorization.adapter_kind:
            raise EvaluationIntegrityError("adapter_authorization_mismatch")
        return adapter
