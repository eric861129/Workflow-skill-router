from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ContractSuite:
    case_count: int
    tier: str
    evidence_class: str


def load_legacy_v1_contract(path: Path) -> ContractSuite:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return ContractSuite(len(rows), "T0", "contract-only")
