"""以確定性規則分析任務結構訊號，不涉及任何權限或執行行為。"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from workflow_skill_router.routing.models import TaskSignals


_CLASSIFIER_REVISION = "deterministic-objective-v1"
_MAX_OBJECTIVE_LENGTH = 4096
_STRONG_TAGS = {
    "cross-repo": "cross-repository-signal",
    "resumable": "resumable-signal",
    "milestone": "milestone-signal",
    "dependency-dag": "dependency-signal",
}
_STRONG_PATTERNS = {
    "cross-repo": re.compile(r"\bcross[-\s]?repositor(?:y|ies)\b|跨(?:儲存庫|倉庫)"),
    "resumable": re.compile(r"\b(?:resumable|long[-\s]?running|resume)\b|(?:可續|持續)"),
    "milestone": re.compile(r"\bmilestones?\b|里程碑"),
    "dependency-dag": re.compile(r"\bdependency[-\s]?(?:dag|graph)\b|相依(?:性)?(?:圖|工作|dag)"),
}
_ACTION_PATTERNS = {
    "plan": re.compile(r"\b(?:plan|analyze|analyse)\b|(?:規劃|分析|盤點)"),
    "implement": re.compile(r"\b(?:implement|build|develop|code)\b|(?:實作|開發)"),
    "test": re.compile(r"\b(?:test|verify|validate)\b|(?:測試|驗證)"),
    "document": re.compile(
        r"\b(?:document|write\s+(?:documentation|docs))\b|(?:撰寫文件|文件化|更新文件)"
    ),
}
_ENGLISH_NEGATION_PREFIX = re.compile(r"\b(?:do\s+not|don't|skip)\s*$")
_COORDINATED_ENGLISH_NEGATION = re.compile(
    r"\b(?:do\s+not|don't|skip)(?:\s+[a-z-]+){1,3}\s+(?:or|and)\s*$"
)
_CHINESE_NEGATION_PREFIX = re.compile(r"(?:不要|不需要|不|勿)\s*$")
_COORDINATED_CHINESE_NEGATION = re.compile(
    r"(?:不要|不需要|不|勿)[^,，;；]{0,16}(?:或|和|及)\s*$"
)
_SEQUENCE_PATTERN = re.compile(r"\b(?:then|after\s+that|finally|next)\b|(?:先|再|接著|最後)")
_NUMBERED_STAGE_PATTERN = re.compile(r"(?:^|[;\n])\s*\d{1,2}[.)、]")


@dataclass(frozen=True, slots=True)
class TaskSignalAnalysis:
    """任務結構分析結果；僅供既有路由分析使用。"""

    signals: TaskSignals
    confidence: str
    classifier_revision: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ActionOccurrence:
    family: str
    start: int
    end: int


def analyze_task_signals(
    objective: str,
    *,
    trusted_domains: tuple[str, ...] = (),
    trusted_tags: tuple[str, ...] = (),
) -> TaskSignalAnalysis:
    """以確定性結構訊號分析任務，不檢查環境也不授與任何權限。"""
    normalized_objective = _normalize_objective(objective)
    normalized_domains = _normalize_values(trusted_domains)
    normalized_tags = _normalize_values(trusted_tags)

    reason_codes: list[str] = []
    positive_actions, ignored_negation = _find_positive_actions(normalized_objective)
    if ignored_negation:
        reason_codes.append("negated-action-ignored")

    distinct_stages, numbered_action_entries = _count_distinct_stages(
        normalized_objective,
        positive_actions,
    )
    if distinct_stages > 1:
        if numbered_action_entries > 1 or (
            _has_sequence_between_actions(normalized_objective, positive_actions)
        ):
            reason_codes.append("multi-stage-sequence")
        else:
            reason_codes.append("multi-action-family")

    domain_count = max(1, len(normalized_domains))
    if domain_count > 1:
        reason_codes.append("trusted-multi-domain")

    strong_evidence = _find_strong_evidence(normalized_objective, normalized_tags)
    for tag, reason_code in _STRONG_TAGS.items():
        if tag in strong_evidence:
            reason_codes.append(reason_code)

    managed_goal = len(strong_evidence) >= 2
    if managed_goal:
        reason_codes.append("managed-goal-evidence")

    signals = TaskSignals(
        domain_count=domain_count,
        distinct_stages=distinct_stages,
        milestone_count=2 if managed_goal and "milestone" in strong_evidence else 1,
        resumable=managed_goal and "resumable" in strong_evidence,
        cross_repo=managed_goal and "cross-repo" in strong_evidence,
        dependency_dag=managed_goal and "dependency-dag" in strong_evidence,
    )
    if not reason_codes:
        reason_codes.append("single-default")
    elif not managed_goal and distinct_stages == 1 and domain_count == 1:
        reason_codes.append("single-default")

    return TaskSignalAnalysis(
        signals=signals,
        confidence=_confidence(distinct_stages, domain_count, managed_goal),
        classifier_revision=_CLASSIFIER_REVISION,
        reason_codes=tuple(reason_codes),
    )


def _normalize_objective(objective: str) -> str:
    normalized = unicodedata.normalize("NFKC", objective).strip()
    if not normalized:
        raise ValueError("任務目標不可為空白")
    if len(normalized) > _MAX_OBJECTIVE_LENGTH:
        raise ValueError("任務目標不可超過 4096 個字元")
    return normalized.casefold()


def _normalize_values(values: tuple[str, ...]) -> frozenset[str]:
    return frozenset(
        unicodedata.normalize("NFKC", value).strip().casefold()
        for value in values
        if unicodedata.normalize("NFKC", value).strip()
    )


def _find_positive_actions(objective: str) -> tuple[tuple[_ActionOccurrence, ...], bool]:
    positive_actions: list[_ActionOccurrence] = []
    ignored_negation = False
    for family, pattern in _ACTION_PATTERNS.items():
        for match in pattern.finditer(objective):
            occurrence = _ActionOccurrence(family, match.start(), match.end())
            if _is_negated_occurrence(objective, occurrence):
                ignored_negation = True
            else:
                positive_actions.append(occurrence)
    return tuple(sorted(positive_actions, key=lambda action: action.start)), ignored_negation


def _is_negated_occurrence(objective: str, occurrence: _ActionOccurrence) -> bool:
    preceding_text = objective[max(0, occurrence.start - 48):occurrence.start]
    return bool(
        _ENGLISH_NEGATION_PREFIX.search(preceding_text)
        or _COORDINATED_ENGLISH_NEGATION.search(preceding_text)
        or _CHINESE_NEGATION_PREFIX.search(preceding_text)
        or _COORDINATED_CHINESE_NEGATION.search(preceding_text)
    )


def _count_distinct_stages(
    objective: str,
    positive_actions: tuple[_ActionOccurrence, ...],
) -> tuple[int, int]:
    action_families = {action.family for action in positive_actions}
    numbered_action_entries = _count_numbered_action_entries(objective, positive_actions)
    sequenced_occurrences = len(positive_actions) if _has_sequence_between_actions(
        objective,
        positive_actions,
    ) else 1
    return max(1, len(action_families), numbered_action_entries, sequenced_occurrences), numbered_action_entries


def _has_sequence_between_actions(
    objective: str,
    positive_actions: tuple[_ActionOccurrence, ...],
) -> bool:
    return any(
        _SEQUENCE_PATTERN.search(objective[left.end:right.start])
        for left, right in zip(positive_actions, positive_actions[1:])
    )


def _count_numbered_action_entries(
    objective: str,
    positive_actions: tuple[_ActionOccurrence, ...],
) -> int:
    markers = list(_NUMBERED_STAGE_PATTERN.finditer(objective))
    if not markers:
        return 0
    count = 0
    for index, marker in enumerate(markers):
        entry_end = markers[index + 1].start() if index + 1 < len(markers) else len(objective)
        if any(marker.end() <= action.start < entry_end for action in positive_actions):
            count += 1
    return count


def _find_strong_evidence(objective: str, tags: frozenset[str]) -> frozenset[str]:
    return frozenset(
        tag
        for tag, pattern in _STRONG_PATTERNS.items()
        if tag in tags or pattern.search(objective)
    )


def _confidence(distinct_stages: int, domain_count: int, managed_goal: bool) -> str:
    if managed_goal or distinct_stages >= 3:
        return "high"
    if distinct_stages > 1 or domain_count > 1:
        return "medium"
    return "low"
