"""Strict, default-off contracts for Adaptive Workflow Memory."""

from pathlib import Path

from .candidates import (
    CandidateEngine,
    CandidateError,
    PatternMetrics,
    WorkflowCandidate,
    WorkflowPattern,
    decode_workflow_candidate,
)
from .analytics import (
    HistorySummary,
    HistorySummaryQuery,
    PurgeMemoryCommand,
    PurgeMemoryResult,
    RetentionResult,
)
from .feedback import (
    RecordRouteFeedbackCommand,
    RecordRouteFeedbackResult,
    RouteFeedback,
    RouteFeedbackError,
    decode_route_feedback,
)
from .migrator import (
    MemoryMigration,
    MemoryMigrationError,
    migrate_memory_store,
)
from .models import MemoryMode, MemoryPolicy, MemoryPolicyError, MemoryScope
from .policy import decode_memory_policy, decode_policy_text, memory_policy_document
from .policy_io import (
    MemoryPolicyRepository,
    PolicyLoadResult,
    PolicySource,
    default_router_data_dir,
)
from .policy_resolver import (
    EffectiveMemoryPolicy,
    resolution_steps,
    resolve_effective_policy,
)
from .profile_diff import (
    ProfileDiffError,
    SemanticDiffEntry,
    SemanticProfileDiff,
    build_profile_document,
    diff_profiles,
)
from .backtest import BacktestSummary, backtest_profile_update
from .proposals import (
    ProfileProposalError,
    ProfileUpdateProposal,
    create_profile_update_proposal,
    create_profile_update_proposal_from_document,
    decode_profile_update_proposal,
    transition_profile_update,
)
from .materializer import ProfileMaterializationError, ProfileMaterializer
from .revisions import (
    ProfileRevision,
    ProfileRevisionError,
    ProfileRevisionStore,
    ProfileTarget,
    ProfileWriteAuthority,
    create_profile_revision,
    decode_profile_revision,
)
from .safe_yaml import parse_safe_yaml
from .workflow_reader import (
    CompletedWorkflowPhase,
    CompletedWorkflowReader,
    CompletedWorkflowSnapshot,
    MemoryRequestContext,
    WorkflowReadError,
)
from .observations import (
    MatcherSeed,
    ObservationEligibility,
    RouteObservation,
    RouteObservationError,
    RouteObservationPhase,
    build_route_observation,
    decode_route_observation,
    evaluate_observation_eligibility,
)
from .service import (
    MemoryCommandConflict,
    RememberWorkflowCommand,
    RememberWorkflowResult,
    WorkflowMemoryService,
)
from .store import (
    MEMORY_DATABASE_NAME,
    MemoryPolicySnapshot,
    MemoryPolicySnapshotError,
    MemoryStore,
    MemoryStoreError,
    decode_memory_policy_snapshot,
)


def memory_database_path(data_dir: Path) -> Path:
    """Return the fixed Memory database path without touching the filesystem."""

    return Path(data_dir).expanduser() / "memory" / MEMORY_DATABASE_NAME


__all__ = [
    "CandidateEngine",
    "BacktestSummary",
    "ProfileDiffError",
    "SemanticDiffEntry",
    "SemanticProfileDiff",
    "ProfileProposalError",
    "ProfileUpdateProposal",
    "build_profile_document",
    "diff_profiles",
    "backtest_profile_update",
    "create_profile_update_proposal",
    "create_profile_update_proposal_from_document",
    "ProfileMaterializationError",
    "ProfileMaterializer",
    "ProfileRevision",
    "ProfileRevisionError",
    "ProfileRevisionStore",
    "ProfileTarget",
    "ProfileWriteAuthority",
    "create_profile_revision",
    "decode_profile_revision",
    "decode_profile_update_proposal",
    "transition_profile_update",
    "CandidateError",
    "PatternMetrics",
    "WorkflowCandidate",
    "WorkflowPattern",
    "decode_workflow_candidate",
    "CompletedWorkflowPhase",
    "decode_route_feedback",
    "RouteFeedbackError",
    "RouteFeedback",
    "RetentionResult",
    "RecordRouteFeedbackResult",
    "RecordRouteFeedbackCommand",
    "PurgeMemoryResult",
    "PurgeMemoryCommand",
    "HistorySummaryQuery",
    "HistorySummary",
    "CompletedWorkflowReader",
    "CompletedWorkflowSnapshot",
    "EffectiveMemoryPolicy",
    "MEMORY_DATABASE_NAME",
    "MemoryMigration",
    "MemoryMigrationError",
    "MatcherSeed",
    "MemoryCommandConflict",
    "MemoryMode",
    "MemoryRequestContext",
    "MemoryPolicy",
    "MemoryPolicyError",
    "MemoryPolicyRepository",
    "MemoryPolicySnapshot",
    "MemoryPolicySnapshotError",
    "MemoryScope",
    "MemoryStore",
    "MemoryStoreError",
    "ObservationEligibility",
    "PolicyLoadResult",
    "PolicySource",
    "RememberWorkflowCommand",
    "RememberWorkflowResult",
    "RouteObservation",
    "RouteObservationError",
    "RouteObservationPhase",
    "WorkflowMemoryService",
    "WorkflowReadError",
    "build_route_observation",
    "decode_memory_policy",
    "decode_memory_policy_snapshot",
    "decode_policy_text",
    "decode_route_observation",
    "default_router_data_dir",
    "memory_database_path",
    "evaluate_observation_eligibility",
    "memory_policy_document",
    "migrate_memory_store",
    "parse_safe_yaml",
    "resolution_steps",
    "resolve_effective_policy",
]
