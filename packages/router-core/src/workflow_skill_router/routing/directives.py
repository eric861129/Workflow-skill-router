from __future__ import annotations

from .models import (
    DirectiveInput,
    ExplicitSemantics,
    RoutingEnvelope,
    SupportPolicy,
    UserDirective,
)


class DirectiveAmbiguityError(ValueError):
    pass


_WORK_MODE_ALIASES = {
    "single": RoutingEnvelope.SINGLE,
    "small": RoutingEnvelope.SINGLE,
    "phased": RoutingEnvelope.PHASED,
    "medium": RoutingEnvelope.PHASED,
    "goal": RoutingEnvelope.MANAGED_GOAL,
    "managed-goal": RoutingEnvelope.MANAGED_GOAL,
}
_SEMANTICS = {
    "use": (ExplicitSemantics.PREFERRED_PRIMARY, SupportPolicy.ASK),
    "only": (ExplicitSemantics.ALLOWED_SET, SupportPolicy.FORBID),
    "all": (ExplicitSemantics.REQUIRED_ALL, SupportPolicy.ASK),
}


def _work_mode(value: DirectiveInput) -> RoutingEnvelope | None:
    if value.requested_work_mode_hint is not None:
        try:
            return _WORK_MODE_ALIASES[value.requested_work_mode_hint.strip().lower()]
        except KeyError as error:
            raise DirectiveAmbiguityError("無法辨識 requested work mode") from error
    text = value.text.casefold()
    if "分階段" in text:
        return RoutingEnvelope.PHASED
    if "goal 模式" in text or "goal mode" in text:
        return RoutingEnvelope.MANAGED_GOAL
    if "單一任務" in text or "single mode" in text:
        return RoutingEnvelope.SINGLE
    return None


def resolve_directive(value: DirectiveInput) -> UserDirective:
    skills = tuple(dict.fromkeys(item.strip() for item in value.explicit_skill_ids if item.strip()))
    if not skills:
        return UserDirective(_work_mode(value), (), None, SupportPolicy.ASK, value.text)

    hint = value.skill_semantics_hint.strip().lower() if value.skill_semantics_hint else None
    if hint is None:
        if len(skills) > 1:
            raise DirectiveAmbiguityError("多個指定 SKILL 必須明確說明 use、only 或 all")
        hint = "use"
    try:
        semantics, support_policy = _SEMANTICS[hint]
    except KeyError as error:
        raise DirectiveAmbiguityError("無法辨識 explicit SKILL 語意") from error
    return UserDirective(
        requested_work_mode=_work_mode(value),
        explicit_skills=skills,
        explicit_semantics=semantics,
        support_policy=support_policy,
        source_text=value.text,
    )

