from __future__ import annotations

import hashlib

from workflow_skill_router.schemas.artifacts import canonical_json

from .models import ScopeAnchor, ScopeKind, SelectionMode, SkillSelectionPolicy


class ScopePolicyError(ValueError):
    pass


def create_scope_anchor(
    kind: ScopeKind,
    aggregate_id: str,
    parent_scope_anchor_id: str | None,
    semantic_scope_digest: str,
    created_revision: int,
    lineage_root_id: str | None = None,
    stable_scope_key: str | None = None,
) -> ScopeAnchor:
    if not aggregate_id or not semantic_scope_digest:
        raise ValueError("aggregate_id 與 semantic_scope_digest 不可為空")
    if created_revision < 1:
        raise ValueError("created_revision 必須大於等於 1")
    lineage = lineage_root_id or aggregate_id
    stable_key = stable_scope_key or aggregate_id
    identity = canonical_json({
        "anchor_kind": kind.value,
        "lineage_root_id": lineage,
        "stable_scope_key": stable_key,
        "parent_scope_anchor_id": parent_scope_anchor_id,
        "semantic_scope_digest": semantic_scope_digest,
    })
    anchor_id = "scope:sha256:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return ScopeAnchor(
        anchor_id,
        kind,
        aggregate_id,
        parent_scope_anchor_id,
        semantic_scope_digest,
        lineage,
        stable_key,
        created_revision,
    )


def descendant_anchor(
    parent: ScopeAnchor,
    kind: ScopeKind,
    aggregate_id: str,
    semantic_scope_digest: str,
    created_revision: int,
) -> ScopeAnchor:
    return create_scope_anchor(
        kind,
        aggregate_id,
        parent.scope_anchor_id,
        semantic_scope_digest,
        created_revision,
        lineage_root_id=parent.lineage_root_id,
        stable_scope_key=aggregate_id,
    )


def replacement_anchor(
    previous: ScopeAnchor,
    replacement_aggregate_id: str,
    created_revision: int,
) -> ScopeAnchor:
    if created_revision <= previous.created_revision:
        raise ScopePolicyError("replacement revision 必須前進")
    return create_scope_anchor(
        previous.kind,
        replacement_aggregate_id,
        previous.parent_scope_anchor_id,
        previous.semantic_scope_digest,
        created_revision,
        lineage_root_id=previous.lineage_root_id,
        stable_scope_key=previous.stable_scope_key,
    )


class ScopeIndex:
    def __init__(self, anchors: tuple[ScopeAnchor, ...]) -> None:
        indexed: dict[str, ScopeAnchor] = {}
        for anchor in anchors:
            current = indexed.get(anchor.scope_anchor_id)
            if current is not None and (
                current.kind != anchor.kind
                or current.parent_scope_anchor_id != anchor.parent_scope_anchor_id
                or current.semantic_scope_digest != anchor.semantic_scope_digest
                or current.lineage_root_id != anchor.lineage_root_id
                or current.stable_scope_key != anchor.stable_scope_key
            ):
                raise ScopePolicyError("scope anchor identity 衝突")
            indexed[anchor.scope_anchor_id] = anchor
        self._anchors = indexed

    def is_same_or_descendant(self, *, candidate_id: str, ancestor_id: str) -> bool:
        if candidate_id not in self._anchors or ancestor_id not in self._anchors:
            return False
        current_id: str | None = candidate_id
        visited: set[str] = set()
        found = False
        while current_id is not None:
            if current_id in visited:
                return False
            visited.add(current_id)
            anchor = self._anchors.get(current_id)
            if anchor is None:
                return False
            if current_id == ancestor_id:
                found = True
            current_id = anchor.parent_scope_anchor_id
        return found


def inherit_explicit_policy(
    policy: SkillSelectionPolicy,
    anchor: ScopeAnchor,
    scope_index: ScopeIndex,
) -> SkillSelectionPolicy:
    if policy.mode is SelectionMode.AUTO:
        return policy
    if not scope_index.is_same_or_descendant(
        candidate_id=anchor.scope_anchor_id,
        ancestor_id=policy.scope_anchor_id,
    ):
        raise ScopePolicyError("目標 scope 不在 explicit lock 的 descendant 範圍")
    return policy

