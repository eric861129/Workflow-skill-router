from __future__ import annotations

from workflow_skill_router.profiles.contract import is_canonical_skill_id

from .models import (
    DirectiveInput,
    ExplicitSemantics,
    RoutingEnvelope,
    SupportPolicy,
    UserDirective,
)


class DirectiveAmbiguityError(ValueError):
    """使用者指令無法在不猜測的情況下解析；`reason` 是可公開的原因碼。"""

    reason = "directive-ambiguous"

    def __init__(self, message: str, *, reason: str | None = None) -> None:
        super().__init__(message)
        if reason is not None:
            self.reason = reason


def canonical_explicit_skill_id(value: str) -> str:
    """把使用者指定的 SKILL 識別碼正規化為 `skill:<name>`。

    Host 裡的使用者會直接寫 Skill 名稱（例如 `python-test-writer`），而 Router
    內部、Profile 與持久化欄位只接受 canonical 形式。沒有前綴的名稱在這裡補上
    `skill:`；其他形式一律在邊界拒絕，不能等到讀回時才當成資料損毀。
    """

    if is_canonical_skill_id(value):
        return value
    # A value that already claims the skill: namespace but fails the contract is wrong, not bare.
    if not value.startswith("skill:") and is_canonical_skill_id(f"skill:{value}"):
        return f"skill:{value}"
    raise DirectiveAmbiguityError(
        "explicit SKILL 識別碼必須是 skill:<name> 或可補上前綴的 Skill 名稱",
        reason="explicit-skill-id-not-canonical",
    )


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
    skills = tuple(dict.fromkeys(
        canonical_explicit_skill_id(item.strip()) for item in value.explicit_skill_ids if item.strip()
    ))
    if not skills:
        return UserDirective(_work_mode(value), (), None, SupportPolicy.AUTO, value.text)

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
