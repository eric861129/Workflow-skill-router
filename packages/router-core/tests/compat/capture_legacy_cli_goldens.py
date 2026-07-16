from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .golden_runner import run_case
    from .legacy_cli_cases import CASES
except ImportError:  # pragma: no cover - 支援直接執行 capture script。
    from golden_runner import run_case
    from legacy_cli_cases import CASES


OUTPUT = Path(__file__).with_name("golden") / "legacy-cli-v1.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="擷取目前 V1 CLI subprocess 契約。")
    parser.add_argument("--write", action="store_true", help="明確覆寫經人工審查的 golden。")
    args = parser.parse_args()
    if not args.write:
        parser.error("必須明確提供 --write")
    document = {case.name: run_case(case) for case in sorted(CASES, key=lambda item: item.name)}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
