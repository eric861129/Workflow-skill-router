from __future__ import annotations

from datetime import datetime, timezone
import hashlib

from workflow_skill_router.schemas.artifacts import canonical_json

from .models import (
    ConsentDecision,
    ConsentGrant,
    ConsentRejection,
    ScopeAnchor,
    SupportPolicy,
    SupportProposal,
)
from .scope import ScopeIndex


class ConsentPolicyError(ValueError):
    pass


def material_context_fingerprint(
    capability_fingerprint: str,
    purpose_class: str,
    scope_anchor_id: str,
    goal_revision: int | None,
    semantic_context_digest: str,
) -> str:
    document = {
        "capability_fingerprint": capability_fingerprint,
        "purpose_class": purpose_class,
        "scope_anchor_id": scope_anchor_id,
        "goal_revision": goal_revision,
        "semantic_context_digest": semantic_context_digest,
    }
    return "sha256:" + hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()


def propose_support(
    anchor: ScopeAnchor,
    proposals: tuple[SupportProposal, ...],
) -> tuple[SupportProposal, ...]:
    distinct = {item.capability_id for item in proposals}
    if len(distinct) > 3:
        raise ConsentPolicyError("每個 scope 最多三個不同的輔助 SKILL")
    if len(distinct) != len(proposals):
        raise ConsentPolicyError("同一 capability 不可重複提案")
    if any(item.scope_anchor_id != anchor.scope_anchor_id for item in proposals):
        raise ConsentPolicyError("support proposal scope 不一致")
    return tuple(sorted(proposals, key=lambda item: item.capability_id))


def match_grant(
    grant: ConsentGrant,
    request: SupportProposal,
    scope_index: ScopeIndex,
    now: datetime | None = None,
) -> bool:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now 必須是 timezone-aware datetime")
    return (
        grant.capability_id == request.capability_id
        and grant.capability_fingerprint == request.capability_fingerprint
        and grant.purpose == request.purpose
        and grant.role == request.role
        and scope_index.is_same_or_descendant(
            candidate_id=request.scope_anchor_id,
            ancestor_id=grant.scope_anchor_id,
        )
        and grant.context_fingerprint == request.context_fingerprint
        and grant.goal_binding_id == request.goal_binding_id
        and grant.goal_revision == request.goal_revision
        and grant.expires_at > current
    )


def may_reask_after_rejection(
    rejection: ConsentRejection,
    request: SupportProposal,
) -> bool:
    same_key = (
        rejection.capability_id == request.capability_id
        and rejection.purpose == request.purpose
        and rejection.role == request.role
        and rejection.scope_anchor_id == request.scope_anchor_id
        and rejection.goal_binding_id == request.goal_binding_id
        and rejection.goal_revision == request.goal_revision
    )
    return not same_key or rejection.context_fingerprint != request.context_fingerprint


def validate_support_selection(
    request: SupportProposal,
    support_policy: SupportPolicy,
    grants: tuple[ConsentGrant, ...],
    rejections: tuple[ConsentRejection, ...],
    scope_index: ScopeIndex,
    now: datetime | None = None,
) -> ConsentDecision:
    if support_policy is SupportPolicy.AUTO:
        return ConsentDecision(True, "support-auto-selected", None, False)
    if support_policy is SupportPolicy.FORBID:
        return ConsentDecision(False, "support-forbidden", None, False)
    for grant in grants:
        if match_grant(grant, request, scope_index, now):
            return ConsentDecision(True, "support-consent-granted", grant.grant_id, False)
    for rejection in rejections:
        if not may_reask_after_rejection(rejection, request):
            return ConsentDecision(False, "support-consent-rejected", None, False)
    return ConsentDecision(False, "support-consent-required", None, True)
