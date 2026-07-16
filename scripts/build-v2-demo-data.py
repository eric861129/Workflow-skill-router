from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/router-core/src"))
from workflow_skill_router.demo_export import build_demo_artifact


def build_demo_data(root: Path) -> dict[str, object]:
    source = json.loads((root / "demo/v2-scenarios/inputs.json").read_text("utf-8"))
    forbidden = {"request_decision","route","active_selections","policy_result","events"}
    if any(forbidden.intersection(item) for item in source["presets"]): raise ValueError("demo input contains policy output")
    evaluation = json.loads((root / "evaluation/artifacts/public/v2-demo-evaluation.json").read_text("utf-8"))
    output = build_demo_artifact(source, evaluation)
    encoded = json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if re.search(r"[A-Za-z]:\\Users\\|/Users/|/home/|sk-[A-Za-z0-9]", encoded): raise ValueError("demo output is not public safe")
    return output


def main() -> int:
    parser=argparse.ArgumentParser();parser.add_argument("--check",action="store_true");args=parser.parse_args()
    target=ROOT / "site/src/data/router-demo-v2.generated.json"
    data=(json.dumps(build_demo_data(ROOT),ensure_ascii=False,sort_keys=True,separators=(",", ":"))+"\n").encode()
    if args.check: return 0 if target.is_file() and target.read_bytes()==data else 1
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);return 0


if __name__=="__main__":raise SystemExit(main())
