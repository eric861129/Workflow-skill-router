from __future__ import annotations

from pathlib import Path
import shutil


PLUGIN = Path(__file__).resolve().parents[1]
ROOT = PLUGIN.parents[1]
SOURCE = ROOT / "starter" / "v2" / "workflow-skill-router"
TARGET = PLUGIN / "skills" / "workflow-skill-router"
ALLOWED = (
    Path("SKILL.md"),
    Path("references/routing-protocol.md"),
    Path("references/goal-protocol.md"),
    Path("references/evaluation-boundary.md"),
)


def main() -> int:
    actual = tuple(sorted(path.relative_to(SOURCE) for path in SOURCE.rglob("*") if path.is_file()))
    if actual != tuple(sorted(ALLOWED)):
        raise SystemExit(f"unexpected canonical skill files: {actual!r}")
    for relative in ALLOWED:
        destination = TARGET / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / relative, destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
