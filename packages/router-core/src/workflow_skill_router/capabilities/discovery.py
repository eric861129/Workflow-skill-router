from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .drift import compare_snapshots
from .models import CapabilityDrift, CapabilitySnapshot
from .providers import CapabilityProvider, DiscoveryContext, ProviderResult
from .snapshot import build_snapshot


@dataclass(frozen=True, slots=True)
class ProviderFailure:
    provider_id: str
    reason: str
    timed_out: bool


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    snapshot: CapabilitySnapshot
    drift: tuple[CapabilityDrift, ...]
    provider_failures: tuple[ProviderFailure, ...]
    used_degraded_provider: bool
    degraded: bool


class DiscoveryService:
    """以 bounded concurrency 執行 providers 並建立 deterministic snapshot。"""

    def __init__(
        self,
        providers: tuple[CapabilityProvider, ...],
        *,
        clock: Callable[[], datetime] | None = None,
        provider_timeout_seconds: float = 2.0,
        max_workers: int = 8,
    ) -> None:
        if provider_timeout_seconds <= 0:
            raise ValueError("provider_timeout_seconds 必須大於 0")
        if max_workers <= 0:
            raise ValueError("max_workers 必須大於 0")
        self._providers = tuple(providers)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._provider_timeout_seconds = provider_timeout_seconds
        self._max_workers = max_workers

    @staticmethod
    def _provider_id(provider: CapabilityProvider, index: int) -> str:
        value = getattr(provider, "provider_id", None)
        return value if isinstance(value, str) and value else f"provider-{index}"

    def discover(
        self,
        context: DiscoveryContext,
        previous: CapabilitySnapshot | None = None,
    ) -> DiscoveryResult:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock 必須回傳含 timezone 的 datetime")

        results: list[ProviderResult] = []
        failures: list[ProviderFailure] = []
        if self._providers:
            executor = ThreadPoolExecutor(
                max_workers=min(self._max_workers, len(self._providers)),
                thread_name_prefix="router-capability-provider",
            )
            future_to_identity: dict[Future[ProviderResult], tuple[int, str]] = {}
            for index, provider in enumerate(self._providers):
                future = executor.submit(provider.discover, context)
                future_to_identity[future] = (index, self._provider_id(provider, index))
            done, pending = wait(
                tuple(future_to_identity),
                timeout=self._provider_timeout_seconds,
            )
            for future in done:
                _, provider_id = future_to_identity[future]
                try:
                    result = future.result()
                    if not isinstance(result, ProviderResult):
                        raise TypeError("provider did not return ProviderResult")
                    results.append(result)
                except Exception as error:
                    failures.append(ProviderFailure(
                        provider_id=provider_id,
                        reason=f"provider-error:{error.__class__.__name__}",
                        timed_out=False,
                    ))
            for future in pending:
                _, provider_id = future_to_identity[future]
                future.cancel()
                failures.append(ProviderFailure(
                    provider_id=provider_id,
                    reason="provider-timeout",
                    timed_out=True,
                ))
            executor.shutdown(wait=False, cancel_futures=True)

        ordered_results = tuple(sorted(
            results,
            key=lambda item: (item.provider_id, item.revision),
        ))
        ordered_failures = tuple(sorted(
            failures,
            key=lambda item: (item.provider_id, item.reason, item.timed_out),
        ))
        snapshot = build_snapshot(
            ordered_results,
            context.runtime_fingerprint,
            previous,
            now,
        )
        drift = compare_snapshots(previous, snapshot) if previous else ()
        used_degraded_provider = any(
            result.degraded and result.observations
            for result in ordered_results
        )
        degraded = (
            bool(ordered_failures)
            or any(result.degraded for result in ordered_results)
            or snapshot.freshness.stale
        )
        return DiscoveryResult(
            snapshot=snapshot,
            drift=drift,
            provider_failures=ordered_failures,
            used_degraded_provider=used_degraded_provider,
            degraded=degraded,
        )
