from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LegacyV1ContractAdapter:
    tier: str = "T0"
    evidence_class: str = "contract-only"

    def adapt(self, artifact: object) -> dict[str, object]:
        return {"artifact": artifact, "tier": self.tier, "evidence_class": self.evidence_class}
