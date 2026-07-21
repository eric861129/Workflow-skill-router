from __future__ import annotations

from hashlib import sha256
import json
import re
import sys


def _public_task(prompt: str) -> str:
    marker = "\n\nUser task:\n"
    return prompt.rsplit(marker, 1)[-1] if marker in prompt else prompt


def _evaluation_evidence(lowered: str) -> dict[str, object]:
    common: dict[str, object] = {
        "authority": {"mode": "router-local", "native_goal_mutated": False},
        "profile_explain": {"status": "not-requested", "reason_codes": []},
        "activation_status": "unverified",
        "semantic_candidate_persisted": False,
    }
    if "troubleshooting note" in lowered:
        return {
            **common,
            "classification": {
                "source": "builtin-fallback",
                "reason_codes": ["single-default"],
            },
        }
    if "review one endpoint response contract" in lowered:
        return {
            **common,
            "classification": {
                "source": "builtin-fallback",
                "reason_codes": ["single-default", "explicit-skill-lock"],
            },
        }
    if "first plan the diagnosis" in lowered:
        return {
            **common,
            "classification": {
                "source": "deterministic-analyzer",
                "reason_codes": ["multi-stage-sequence"],
            },
        }
    if "phase transition has entered browser verification" in lowered:
        return {
            **common,
            "classification": {
                "source": "deterministic-analyzer",
                "reason_codes": ["phase-transition-signal"],
            },
        }
    if (
        "api contract design and contract-test planning" in lowered
        or "approve the proposed contract-testing support" in lowered
        or "do not use the proposed supporting skill" in lowered
    ):
        return {
            **common,
            "classification": {
                "source": "caller-work-mode-hint",
                "reason_codes": ["explicit-phased-signal", "explicit-skill-lock"],
            },
        }
    if (
        "resumable cross-repository migration" in lowered
        and "dependency graph" in lowered
    ):
        return {
            **common,
            "classification": {
                "source": "deterministic-analyzer",
                "reason_codes": [
                    "cross-repository-signal",
                    "resumable-signal",
                    "dependency-signal",
                    "managed-goal-evidence",
                ],
            },
        }
    if "report current progress and the next incomplete work item" in lowered:
        return {
            **common,
            "classification": {
                "source": "native-goal-binding",
                "reason_codes": ["goal-status-query"],
            },
        }
    if "steer the active migration goal" in lowered:
        return {
            **common,
            "classification": {
                "source": "native-goal-binding",
                "reason_codes": ["goal-steer-request"],
            },
        }
    if "answer this side question only" in lowered:
        return {
            **common,
            "classification": {
                "source": "native-goal-binding",
                "reason_codes": ["goal-side-question"],
            },
        }
    if "exact canonical capability identified by the verified snapshot" in lowered:
        return {
            **common,
            "classification": {
                "source": "builtin-fallback",
                "reason_codes": ["single-default", "capability-unavailable"],
            },
        }
    if "runtime capability snapshot changed after planning" in lowered:
        return {
            **common,
            "classification": {
                "source": "caller-work-mode-hint",
                "reason_codes": ["explicit-phased-signal", "runtime-drift-revalidation"],
            },
        }
    if "against the supplied routing profile" in lowered:
        return {
            **common,
            "classification": {
                "source": "builtin-fallback",
                "reason_codes": ["single-default"],
            },
            "profile_explain": {
                "status": "miss",
                "reason_codes": ["objective-keyword-miss"],
            },
        }
    return {
        **common,
        "classification": {
            "source": "builtin-fallback",
            "reason_codes": ["single-default"],
        },
    }


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
            "evaluation_evidence": _evaluation_evidence(lowered),
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
            "evaluation_evidence": _evaluation_evidence(lowered),
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
            "evaluation_evidence": _evaluation_evidence(lowered),
        }
    skills = re.findall(r"skill:[a-z0-9-]+", lowered)
    explicit = "use skill:" in lowered
    if (
        "managed goal" in lowered
        or "active migration goal" in lowered
        or (
            "resumable cross-repository migration" in lowered
            and "dependency graph" in lowered
        )
    ):
        envelope = "managed-goal"
    elif "design and verify" in lowered or any(
        term in lowered
        for term in (
            "each phase", "implement", "revalidate", "diagnose", "diagnosis",
            "phased frontend repair", "contract-test planning",
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
    elif "managed goal" in lowered or "resumable cross-repository migration" in lowered:
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
    route = {
        "envelope": envelope,
        "selection_mode": "explicit-locked" if explicit else "auto",
        "primary_skill": primary,
        "support_skills": support,
        "consent_action": consent,
        "goal_relation": relation,
        "rationale": "Deterministic protocol demonstration; this is not model evidence.",
    }
    route["evaluation_evidence"] = _evaluation_evidence(lowered)
    return route


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
