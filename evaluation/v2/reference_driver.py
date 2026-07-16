from __future__ import annotations

from hashlib import sha256
import json
import re
import sys


def _route(prompt: str) -> dict[str, object]:
    lowered = prompt.lower()
    skills = re.findall(r"skill:[a-z0-9-]+", lowered)
    explicit = "use skill:" in lowered
    if "managed goal" in lowered or "active migration goal" in lowered:
        envelope = "managed-goal"
    elif any(term in lowered for term in ("each phase", "implement", "revalidate", "diagnose")):
        envelope = "phased"
    else:
        envelope = "single"
    if explicit and skills:
        primary = skills[0]
    elif "troubleshooting note" in lowered:
        primary = "skill:code-documenter"
    elif "frontend regression" in lowered:
        primary = "skill:systematic-debugging"
    elif "managed goal" in lowered:
        primary = "skill:architecture-designer"
    elif "browser runtime" in lowered:
        primary = "skill:playwright"
    else:
        primary = "skill:workflow-skill-router"
    if "consent approved" in lowered or "i approve" in lowered:
        consent = "approved"
    elif "do not use the proposed" in lowered:
        consent = "rejected"
    elif "propose any genuinely necessary" in lowered or "ask before adding" in lowered:
        consent = "proposal-required"
    else:
        consent = "not-required"
    if "report current progress" in lowered:
        relation = "status"
    elif "steer the active" in lowered:
        relation = "steer"
    elif "side question" in lowered:
        relation = "side-question"
    elif envelope == "managed-goal":
        relation = "progress"
    else:
        relation = "none"
    support = ["skill:playwright"] if "browser coverage" in lowered else []
    return {
        "envelope": envelope,
        "selection_mode": "explicit-locked" if explicit else "auto",
        "primary_skill": primary,
        "support_skills": support,
        "consent_action": consent,
        "goal_relation": relation,
        "rationale": "Deterministic protocol demonstration; this is not model evidence.",
    }


def handle(request: dict[str, object]) -> dict[str, object]:
    nonce = str(request["attempt_nonce"])
    if request["type"] == "start_attempt":
        context = "reference:" + sha256(nonce.encode("utf-8")).hexdigest()[:32]
        return {"attempt_nonce": nonce, "context_id": context}
    context = str(request["context_id"])
    route = _route(str(request["prompt"]))
    return {
        "attempt_nonce": nonce,
        "context_id": context,
        "route": route,
        "text": json.dumps(route, ensure_ascii=False, sort_keys=True),
    }


def main() -> int:
    request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    response = json.dumps(handle(request), ensure_ascii=False, sort_keys=True).encode("utf-8")
    sys.stdout.buffer.write(response + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
