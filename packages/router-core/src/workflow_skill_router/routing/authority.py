from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .scope import ScopeIndex


class SelectionOrigin(StrEnum):
    USER_EXPLICIT = "user-explicit"
    DEVELOPER_REQUIRED = "developer-required"
    SYSTEM_REQUIRED = "system-required"
    SAFETY_RUNTIME_REQUIRED = "safety-runtime-required"
    ROUTER_RECOMMENDED = "router-recommended"


FORCED_ORIGINS = frozenset({
    SelectionOrigin.DEVELOPER_REQUIRED,
    SelectionOrigin.SYSTEM_REQUIRED,
    SelectionOrigin.SAFETY_RUNTIME_REQUIRED,
})


@dataclass(frozen=True, slots=True)
class AuthenticatedContext:
    actor: str
    session_id: str


@dataclass(frozen=True, slots=True)
class RuntimePolicyRule:
    authority_ref: str
    origin: SelectionOrigin
    capability_id: str
    purpose: str
    scope_anchor_id: str
    policy_snapshot_id: str
    actor: str | None = None
    session_id: str | None = None

    def matches(
        self,
        *,
        capability_id: str,
        purpose: str,
        policy_snapshot_id: str,
        actor: str,
        session_id: str,
    ) -> bool:
        return (
            self.capability_id == capability_id
            and self.purpose == purpose
            and self.policy_snapshot_id == policy_snapshot_id
            and (self.actor is None or self.actor == actor)
            and (self.session_id is None or self.session_id == session_id)
        )


@dataclass(frozen=True, slots=True)
class RuntimePolicySnapshot:
    snapshot_id: str
    policy_digest: str
    rules: tuple[RuntimePolicyRule, ...]


@dataclass(frozen=True, slots=True)
class VerifiedDirectiveEvent:
    event_id: str
    capability_id: str
    purpose: str
    scope_anchor_id: str
    policy_snapshot_id: str
    actor: str
    session_id: str
    directive_digest: str

    def binds(
        self,
        *,
        capability_id: str,
        purpose: str,
        policy_snapshot_id: str,
        actor: str,
        session_id: str,
    ) -> bool:
        return (
            self.capability_id == capability_id
            and self.purpose == purpose
            and self.policy_snapshot_id == policy_snapshot_id
            and self.actor == actor
            and self.session_id == session_id
            and self.directive_digest.startswith("sha256:")
        )


@dataclass(frozen=True, slots=True)
class SelectionAuthority:
    selection_origin: SelectionOrigin
    authority_ref: str
    policy_snapshot_id: str
    policy_digest: str
    derived_by: str
    requires_consent: bool
    reason_code: str


class AuthorityResolver:
    def __init__(
        self,
        runtime_policy_snapshot: RuntimePolicySnapshot,
        directive_events: tuple[VerifiedDirectiveEvent, ...],
        authenticated_context: AuthenticatedContext,
        scope_index: ScopeIndex,
    ) -> None:
        self._policy = runtime_policy_snapshot
        self._rules = {item.authority_ref: item for item in runtime_policy_snapshot.rules}
        self._directives = {item.event_id: item for item in directive_events}
        self._context = authenticated_context
        self._scopes = scope_index

    def _resolved(
        self,
        origin: SelectionOrigin,
        authority_ref: str,
    ) -> SelectionAuthority:
        return SelectionAuthority(
            origin,
            authority_ref,
            self._policy.snapshot_id,
            self._policy.policy_digest,
            "router-core",
            False,
            "authority-verified",
        )

    def _downgraded(self) -> SelectionAuthority:
        return SelectionAuthority(
            SelectionOrigin.ROUTER_RECOMMENDED,
            "router-derived",
            self._policy.snapshot_id,
            self._policy.policy_digest,
            "router-core",
            True,
            "authority-binding-mismatch",
        )

    def resolve(
        self,
        requested_origin: SelectionOrigin,
        authority_ref: str,
        *,
        capability_id: str,
        purpose: str,
        scope_anchor_id: str,
        directive_event: VerifiedDirectiveEvent | None = None,
    ) -> SelectionAuthority:
        if requested_origin in FORCED_ORIGINS:
            rule = self._rules.get(authority_ref)
            if (
                rule is not None
                and rule.origin is requested_origin
                and self._scopes.is_same_or_descendant(
                    candidate_id=scope_anchor_id,
                    ancestor_id=rule.scope_anchor_id,
                )
                and rule.matches(
                    capability_id=capability_id,
                    purpose=purpose,
                    policy_snapshot_id=self._policy.snapshot_id,
                    actor=self._context.actor,
                    session_id=self._context.session_id,
                )
            ):
                return self._resolved(requested_origin, authority_ref)
        elif requested_origin is SelectionOrigin.USER_EXPLICIT:
            verified = self._directives.get(authority_ref)
            if (
                verified is not None
                and verified == directive_event
                and self._scopes.is_same_or_descendant(
                    candidate_id=scope_anchor_id,
                    ancestor_id=verified.scope_anchor_id,
                )
                and verified.binds(
                    capability_id=capability_id,
                    purpose=purpose,
                    policy_snapshot_id=self._policy.snapshot_id,
                    actor=self._context.actor,
                    session_id=self._context.session_id,
                )
            ):
                return self._resolved(requested_origin, authority_ref)
        return self._downgraded()

