from __future__ import annotations

from datetime import timezone

from workflow_skill_router.capabilities.availability import derive_availability
from workflow_skill_router.capabilities.models import Capability, CapabilityKind, RiskLevel

from .authority import FORCED_ORIGINS, SelectionOrigin
from .leases import issue_execution_lease
from .models import (
    ActivationBindingKind,
    CapabilitySelection,
    LeaseActivationBinding,
    LeaseCapability,
    Route,
    RouteValidationRequest,
    RouteValidationResult,
    RouteViolation,
    RuntimeMode,
    SelectionMode,
    SkillSelectionPolicy,
    SupportPolicy,
    ValidationContext,
)


def _violation(code: str, capability_id: str | None = None, detail: str = "") -> RouteViolation:
    return RouteViolation(code, capability_id, detail or code)


def _timestamp(value) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _authority_violations(
    selection: CapabilitySelection,
    context: ValidationContext,
    *,
    is_support: bool,
) -> list[RouteViolation]:
    violations = []
    if selection.policy_digest != context.runtime_policy_digest:
        violations.append(_violation("policy-digest-mismatch", selection.capability_id))
    if selection.selection_origin in FORCED_ORIGINS or selection.selection_origin is SelectionOrigin.USER_EXPLICIT:
        if selection.authority_ref not in context.verified_authority_refs:
            violations.append(_violation("selection-authority-unverified", selection.capability_id))
    if is_support and selection.selection_origin is SelectionOrigin.ROUTER_RECOMMENDED:
        if (
            selection.consent_grant_ref is None
            or selection.consent_grant_ref not in context.consent_grant_refs
        ):
            violations.append(_violation("support-consent-missing", selection.capability_id))
    return violations


def _binding(
    capability: Capability,
    context: ValidationContext,
) -> tuple[LeaseActivationBinding | None, RouteViolation | None]:
    if capability.kind is CapabilityKind.SKILL:
        expected = dict(context.instruction_content_bindings).get(capability.canonical_id)
        trusted = capability.installer_content_digest.value
        if expected is None or trusted == "unknown" or expected != trusted:
            return None, _violation("content-preflight-unavailable", capability.canonical_id)
        return LeaseActivationBinding(ActivationBindingKind.INSTRUCTION_CONTENT.value, trusted), None

    runtime = {
        capability_id: (kind, digest)
        for capability_id, kind, digest in context.runtime_contract_bindings
    }.get(capability.canonical_id)
    if runtime is None:
        return None, _violation("runtime-contract-preflight-unavailable", capability.canonical_id)
    kind, digest = runtime
    expected_kind = (
        ActivationBindingKind.TOOL_SCHEMA.value
        if capability.kind is CapabilityKind.MCP_TOOL
        else ActivationBindingKind.RUNTIME_CONTRACT.value
    )
    if kind != expected_kind or digest != capability.capability_fingerprint:
        return None, _violation("runtime-contract-preflight-unavailable", capability.canonical_id)
    return LeaseActivationBinding(kind, digest), None


class RouteValidator:
    def validate(
        self,
        request: RouteValidationRequest,
        snapshot,
        policy: SkillSelectionPolicy,
        context: ValidationContext,
    ) -> RouteValidationResult:
        violations: list[RouteViolation] = []
        if request.capability_snapshot_id != snapshot.snapshot_id:
            violations.append(_violation("snapshot-identity-mismatch"))
        if request.action_digest == "" or not request.action_digest.startswith("sha256:"):
            violations.append(_violation("action-digest-required"))
        if request.state_version < 1:
            violations.append(_violation("state-version-invalid"))

        if request.risk in (RiskLevel.R2, RiskLevel.R3):
            if snapshot.freshness.stale or snapshot.freshness.expires_at <= context.now:
                violations.append(_violation("snapshot-stale"))
            approval = context.runtime_approval
            if (
                approval is None
                or approval.action_digest != request.action_digest
                or approval.expires_at <= context.now
            ):
                violations.append(_violation("runtime-approval-required"))

        selected = (request.primary_selection, *request.support_selections)
        capabilities = {item.canonical_id: item for item in snapshot.capabilities}
        bound: list[LeaseCapability] = []
        for index, selection in enumerate(selected):
            capability = capabilities.get(selection.capability_id)
            if capability is None:
                violations.append(_violation("capability-not-in-snapshot", selection.capability_id))
                continue
            availability = derive_availability(capability, request.risk, context.now)
            if availability.primary not in context.allowed_availability:
                violations.append(_violation("capability-unavailable", selection.capability_id))
            if capability.capability_fingerprint != selection.capability_fingerprint:
                violations.append(_violation("capability-fingerprint-mismatch", selection.capability_id))
            violations.extend(_authority_violations(selection, context, is_support=index > 0))
            activation_binding = None
            binding_violation = None
            if context.runtime_mode is RuntimeMode.HYBRID:
                activation_binding, binding_violation = _binding(capability, context)
            elif capability.kind is not CapabilityKind.SKILL:
                binding_violation = _violation(
                    "runtime-contract-preflight-unavailable",
                    capability.canonical_id,
                )
            if binding_violation is not None:
                violations.append(binding_violation)
            elif activation_binding is not None:
                bound.append(LeaseCapability(
                    selection.capability_id,
                    capability.kind,
                    selection.capability_fingerprint,
                    selection.selection_origin,
                    selection.authority_ref,
                    selection.policy_digest,
                    selection.purpose,
                    selection.consent_grant_ref,
                    activation_binding,
                ))

        if policy.mode is SelectionMode.EXPLICIT_LOCKED:
            explicit = set(policy.explicit_skill_ids)
            if request.primary_selection.capability_id not in explicit:
                violations.append(_violation("explicit-primary-mismatch", request.primary_selection.capability_id))
            scoped_dispositions = tuple(
                item for item in request.explicit_skill_dispositions
                if item.scope_anchor_id == request.scope_anchor_id
            )
            dispositions = {item.skill_id for item in scoped_dispositions}
            for skill_id in sorted(explicit - dispositions):
                violations.append(_violation("explicit-disposition-missing", skill_id))
            for item in request.explicit_skill_dispositions:
                if item.scope_anchor_id != request.scope_anchor_id:
                    violations.append(_violation("explicit-disposition-scope-mismatch", item.skill_id))
            if policy.support_policy is SupportPolicy.FORBID:
                for support in request.support_selections:
                    if support.capability_id not in explicit:
                        violations.append(_violation("support-forbidden", support.capability_id))
            if policy.explicit_semantics is not None and request.explicit_skill_coverage_ref is None:
                violations.append(_violation("explicit-coverage-missing"))

        known_grants = set(request.consent_grant_refs)
        if any(
            selection.consent_grant_ref is not None
            and selection.consent_grant_ref not in known_grants
            for selection in request.support_selections
        ):
            violations.append(_violation("consent-grant-not-bound"))

        deduplicated = tuple(dict.fromkeys(violations))
        if deduplicated:
            return RouteValidationResult(
                False,
                deduplicated,
                any(item.code == "runtime-approval-required" for item in deduplicated),
                None,
                None,
                request.outcome_mode,
                request.exit_gate,
            )

        route = Route(
            request.route_id,
            request.workflow_run_id,
            request.work_item_id,
            request.phase_id,
            request.envelope,
            request.capability_snapshot_id,
            request.primary_selection,
            request.support_selections,
            policy.plan_revision,
            request.explicit_skill_dispositions,
            request.explicit_skill_coverage_ref,
            request.consent_grant_refs,
            request.risk,
            sum(capabilities[item.capability_id].context_cost for item in selected),
            "valid",
            (),
            _timestamp(context.now),
        )
        lease = None
        if context.runtime_mode is RuntimeMode.HYBRID:
            lease = issue_execution_lease(route, request, policy, context, tuple(bound))
        return RouteValidationResult(
            True,
            (),
            False,
            route,
            lease,
            request.outcome_mode,
            request.exit_gate,
        )
