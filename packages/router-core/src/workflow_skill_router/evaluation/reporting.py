from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
from hashlib import sha256
import re
from typing import Any, Mapping

from workflow_skill_router.schemas.artifacts import canonical_json_bytes


_SECRET = re.compile(r"(?i)(token|secret|password|authorization|api[_-]?key)")
_WINDOWS_PATH = re.compile(r"[A-Za-z]:\\[^\s\"']+")
_UNIX_PATH = re.compile(r"(?<!:)\/(?:home|Users|tmp|var)\/[^\s\"']+")


@dataclass(frozen=True, slots=True)
class ExportArtifact:
    schema_version: str
    status: str
    evidence_class: str
    summary: Mapping[str, Any]
    review_subject_digest: str
    review_authority: str | None = None
    reviewed_at: str | None = None
    artifact_digest: str | None = None


def _sanitize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): "[REDACTED]" if _SECRET.search(str(key)) else _sanitize(item)
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)): return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return _UNIX_PATH.sub("[LOCAL_PATH]", _WINDOWS_PATH.sub("[LOCAL_PATH]", value))
    return value


def calculate_review_subject_digest(artifact: ExportArtifact) -> str:
    document = {"schema_version": artifact.schema_version, "status": "review-draft",
                "evidence_class": artifact.evidence_class, "summary": artifact.summary}
    return "sha256:" + sha256(canonical_json_bytes(document)).hexdigest()


def calculate_artifact_digest(artifact: ExportArtifact) -> str:
    document = asdict(replace(artifact, artifact_digest=None))
    return "sha256:" + sha256(canonical_json_bytes(document)).hexdigest()


def build_review_draft(summary: Mapping[str, Any], evidence_class: str) -> ExportArtifact:
    draft = ExportArtifact("2.0", "review-draft", evidence_class, _sanitize(summary), "")
    return replace(draft, review_subject_digest=calculate_review_subject_digest(draft))


def build_benchmark_review_report(
    summary: Mapping[str, Any],
    evidence_class: str,
    *,
    evidence_class_locked: bool,
) -> dict[str, Any]:
    """建立不含虛構綜合分數、等待人工證明的公開評測草稿。"""

    report = {
        "schema_version": "2.0",
        "status": "review-required",
        "evidence_class": evidence_class,
        "evidence_class_locked": evidence_class_locked,
        **summary,
    }
    report.pop("public_composite_score", None)
    return _sanitize(report)


def publish_sanitized(draft: ExportArtifact, authority_id: str, attestation_ref: str,
                      verifier_registry, now: datetime) -> ExportArtifact:
    verifier_registry.verify(authority_id, attestation_ref, draft.review_subject_digest, now)
    published = replace(draft, status="published", review_authority=authority_id,
                        reviewed_at=now.isoformat())
    return replace(published, artifact_digest=calculate_artifact_digest(published))
