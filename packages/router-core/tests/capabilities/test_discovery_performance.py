from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.capabilities.discovery import DiscoveryService
from workflow_skill_router.capabilities.providers import DiscoveryContext, ProviderResult

try:
    from .test_merge import NOW, provider
except ImportError:
    from test_merge import NOW, provider


class StaticProvider:
    provider_id = "filesystem"

    def __init__(self, count: int) -> None:
        observations = tuple(
            provider(
                authority="filesystem",
                canonical_id=f"skill:filesystem/demo-{index:04d}",
                display_name=f"Demo {index}",
                fingerprint=f"sha256:metadata-{index:04d}",
            ).observations[0]
            for index in range(count)
        )
        self._result = ProviderResult(
            provider_id=self.provider_id,
            revision=f"static@{count}",
            observed_at=NOW,
            observations=observations,
            degraded=False,
            reasons=(),
        )

    def discover(self, context: DiscoveryContext) -> ProviderResult:
        del context
        return self._result


class FailingProvider:
    provider_id = "failing"

    def discover(self, context: DiscoveryContext) -> ProviderResult:
        del context
        raise RuntimeError("provider unavailable")


class SlowProvider:
    provider_id = "slow"

    def discover(self, context: DiscoveryContext) -> ProviderResult:
        del context
        time.sleep(0.05)
        return replace(StaticProvider(1)._result, provider_id=self.provider_id)


class DiscoveryPerformanceTests(unittest.TestCase):
    def test_warm_discovery_of_one_thousand_capabilities_is_under_two_seconds(self) -> None:
        service = DiscoveryService(
            (StaticProvider(1000),),
            clock=lambda: NOW,
            provider_timeout_seconds=1.0,
        )
        start = time.perf_counter()
        result = service.discover(DiscoveryContext("runtime-a", "R1"))
        elapsed = time.perf_counter() - start
        self.assertEqual(1000, len(result.snapshot.capabilities))
        self.assertLess(elapsed, 2.0)

    def test_all_provider_failures_return_explicit_stale_empty_snapshot(self) -> None:
        result = DiscoveryService((FailingProvider(),), clock=lambda: NOW).discover(
            DiscoveryContext("runtime-a", "R1")
        )
        self.assertEqual((), result.snapshot.capabilities)
        self.assertTrue(result.snapshot.freshness.stale)
        self.assertTrue(result.degraded)
        self.assertEqual("failing", result.provider_failures[0].provider_id)

    def test_provider_timeout_is_explicit_and_not_silently_omitted(self) -> None:
        result = DiscoveryService(
            (SlowProvider(),),
            clock=lambda: NOW,
            provider_timeout_seconds=0.005,
        ).discover(DiscoveryContext("runtime-a", "R1"))
        self.assertEqual((), result.snapshot.capabilities)
        self.assertTrue(result.provider_failures[0].timed_out)


if __name__ == "__main__":
    unittest.main()
