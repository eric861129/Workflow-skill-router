from __future__ import annotations

from hashlib import sha256
import json
import re
import sys


def _public_task(prompt: str) -> str:
    marker = "\n\nUser task:\n"
    return prompt.rsplit(marker, 1)[-1] if marker in prompt else prompt


def _route(prompt: str) -> dict[str, object]:
    lowered = _public_task(prompt).lower()
    if "phase transition has entered browser verification" in lowered:
        return {
            "envelope": "phased",
            "selection_mode": "auto",
            "primary_skill": "skill:playwright",
            "support_skills": [],
            "consent_action": "not-required",
            "goal_relation": "none",
            "rationale": "Deterministic protocol demonstration; this is not model evidence.",
        }
    if "i approve the proposed contract-testing support" in lowered:
        return {
            "envelope": "phased",
            "selection_mode": "explicit-locked",
            "primary_skill": "skill:api-designer",
            "support_skills": ["skill:qa-test-planner"],
            "consent_action": "approved",
            "goal_relation": "none",
            "rationale": "Deterministic protocol demonstration; this is not model evidence.",
        }
    if "do not use the proposed supporting skill" in lowered:
        return {
            "envelope": "phased",
            "selection_mode": "explicit-locked",
            "primary_skill": "skill:api-designer",
            "support_skills": [],
            "consent_action": "rejected",
            "goal_relation": "none",
            "rationale": "Deterministic protocol demonstration; this is not model evidence.",
        }
    skills = re.findall(r"skill:[a-z0-9-]+", lowered)
    explicit = "use skill:" in lowered
    if "managed goal" in lowered or "active migration goal" in lowered:
        envelope = "managed-goal"
    elif "design and verify" in lowered or any(
        term in lowered
        for term in (
            "each phase", "implement", "revalidate", "diagnose", "diagnosis",
            "phased frontend repair",
        )
    ):
        envelope = "phased"
    else:
        envelope = "single"
    if explicit and skills:
        primary = skills[0]
    elif "troubleshooting note" in lowered:
        primary = "skill:code-documenter"
    elif "frontend regression" in lowered or "phased frontend repair" in lowered:
        primary = "skill:systematic-debugging"
    elif "managed goal" in lowered:
        primary = "skill:architecture-designer"
    elif "browser runtime" in lowered or "exact canonical capability" in lowered:
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
    support = (
        ["skill:qa-test-planner"]
        if explicit
        and (
            "propose any genuinely necessary" in lowered
            or "ask before adding support" in lowered
        )
        else []
    )
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
