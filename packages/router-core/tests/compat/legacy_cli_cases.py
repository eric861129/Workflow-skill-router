from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class LegacyCliCase:
    name: str
    argv: tuple[str, ...]
    env: Mapping[str, str] = field(default_factory=dict)
    input_files: Mapping[str, str] = field(default_factory=dict)
    artifact_paths: tuple[str, ...] = ()


FIXED_GENERATED_AT = "2000-01-01T00:00:00Z"
STRICT_SCENARIO = '{"id":"strict","task":"測試","expected":{"primary":"expected","supporting":[]},"forbidden":[],"max_skills":1,"tags":[]}\n'
STRICT_MISMATCH = '{"id":"strict","selected":{"primary":"wrong","supporting":[]},"explanation":"刻意不相符","stage_split":false}\n'
VIOLATION_SCENARIO = '{"id":"violation","task":"測試","expected":{"primary":"safe","supporting":[]},"forbidden":["forbidden"],"max_skills":1,"tags":[]}\n'
VIOLATION_PREDICTION = '{"id":"violation","selected":{"primary":"forbidden","supporting":[]},"explanation":"刻意違規","stage_split":false}\n'


CASES = (
    LegacyCliCase("scan-help", ("scripts/scan-skills.py", "--help")),
    LegacyCliCase("scan-missing-path", ("scripts/scan-skills.py", "{tmp}/missing-skills")),
    LegacyCliCase(
        "scan-stdout-json",
        ("scripts/scan-skills.py", "sample-skills", "--format", "json", "--generated-at", FIXED_GENERATED_AT),
    ),
    LegacyCliCase(
        "scan-stdout-markdown",
        ("scripts/scan-skills.py", "sample-skills", "--format", "markdown", "--generated-at", FIXED_GENERATED_AT),
    ),
    LegacyCliCase(
        "scan-generated-shape",
        (
            "scripts/scan-skills.py", "sample-skills", "--out", "{tmp}/index.json",
            "--markdown", "{tmp}/summary.md", "--warnings", "{tmp}/warnings.md",
            "--suggest-tree", "{tmp}/tree.md", "--generated-at", FIXED_GENERATED_AT,
        ),
        artifact_paths=("index.json", "summary.md", "warnings.md", "tree.md"),
    ),
    LegacyCliCase("validate-help", ("scripts/validate-router.py", "--help")),
    LegacyCliCase("validate-path", ("scripts/validate-router.py", "starter/workflow-skill-router")),
    LegacyCliCase("validate-missing-path-argument", ("scripts/validate-router.py",)),
    LegacyCliCase("validate-self-test", ("scripts/validate-router.py", "--self-test")),
    LegacyCliCase("validate-public-readiness", ("scripts/validate-router.py", ".", "--public-readiness")),
    LegacyCliCase(
        "validate-public-readiness-env-marker-failure",
        ("scripts/validate-router.py", ".", "--public-readiness"),
        env={"WORKFLOW_SKILL_ROUTER_PUBLIC_FORBIDDEN_MARKERS": "Workflow Skill Router"},
    ),
    LegacyCliCase("evaluate-help", ("scripts/evaluate-routing.py", "--help")),
    LegacyCliCase(
        "evaluate-generated-shape",
        (
            "scripts/evaluate-routing.py", "--scenarios", "evaluation/scenarios.example.jsonl",
            "--predictions", "evaluation/predictions.example.jsonl", "--report", "{tmp}/report.md",
            "--json-report", "{tmp}/report.json",
        ),
        artifact_paths=("report.md", "report.json"),
    ),
    LegacyCliCase(
        "evaluate-strict-failure",
        (
            "scripts/evaluate-routing.py", "--scenarios", "{tmp}/strict-scenarios.jsonl",
            "--predictions", "{tmp}/strict-predictions.jsonl", "--report", "{tmp}/strict-report.md",
            "--strict",
        ),
        input_files={"strict-scenarios.jsonl": STRICT_SCENARIO, "strict-predictions.jsonl": STRICT_MISMATCH},
        artifact_paths=("strict-report.md",),
    ),
    LegacyCliCase(
        "evaluate-fail-on-violations-failure",
        (
            "scripts/evaluate-routing.py", "--scenarios", "{tmp}/violation-scenarios.jsonl",
            "--predictions", "{tmp}/violation-predictions.jsonl", "--report", "{tmp}/violation-report.md",
            "--json-report", "{tmp}/violation-report.json", "--fail-on-violations",
        ),
        input_files={
            "violation-scenarios.jsonl": VIOLATION_SCENARIO,
            "violation-predictions.jsonl": VIOLATION_PREDICTION,
        },
        artifact_paths=("violation-report.md", "violation-report.json"),
    ),
    LegacyCliCase(
        "evaluate-invalid-json-failure",
        (
            "scripts/evaluate-routing.py", "--scenarios", "{tmp}/invalid.jsonl",
            "--predictions", "evaluation/predictions.example.jsonl", "--report", "{tmp}/invalid-report.md",
        ),
        input_files={"invalid.jsonl": "{not-json}\n"},
        artifact_paths=("invalid-report.md",),
    ),
    LegacyCliCase("route-cases", ("scripts/validate-route-cases.py",)),
    LegacyCliCase("gallery-check", ("scripts/build-route-gallery.py", "--check")),
    LegacyCliCase("metrics-check", ("scripts/render-routing-metrics-trend.py", "--check")),
    LegacyCliCase("public-audit", ("scripts/audit-public-readiness.py",)),
    LegacyCliCase("markdown-links", ("scripts/check-markdown-links.py", ".")),
    LegacyCliCase(
        "release-smoke",
        ("scripts/smoke-release-assets.py", "--work-dir", "{tmp}/release-smoke"),
    ),
    LegacyCliCase("package-help", ("scripts/package-downloads.py", "--help")),
    LegacyCliCase(
        "package-env-root-refuses-missing-filters",
        ("scripts/package-downloads.py",),
        env={
            "WORKFLOW_SKILL_ROUTER_SKILLS_ROOT": "sample-skills",
            "WORKFLOW_SKILL_ROUTER_EXCLUDE_NAMES": "",
            "WORKFLOW_SKILL_ROUTER_EXCLUDE_PREFIXES": "",
            "WORKFLOW_SKILL_ROUTER_PRIVATE_MARKERS": "",
        },
    ),
    LegacyCliCase(
        "package-refuses-unfiltered-private-root",
        ("scripts/package-downloads.py", "--skills-root", "sample-skills"),
        env={
            "WORKFLOW_SKILL_ROUTER_EXCLUDE_NAMES": "",
            "WORKFLOW_SKILL_ROUTER_EXCLUDE_PREFIXES": "",
            "WORKFLOW_SKILL_ROUTER_PRIVATE_MARKERS": "",
        },
    ),
)
