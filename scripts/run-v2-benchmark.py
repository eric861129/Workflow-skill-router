from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
CORE_SOURCE = ROOT / "packages" / "router-core" / "src"
if str(CORE_SOURCE) not in sys.path:
    sys.path.insert(0, str(CORE_SOURCE))

from workflow_skill_router.evaluation.contracts import (
    EvaluationExecutionMode,
    EvaluationIntegrityError,
    EvaluationProfile,
    ModelExecutionPayload,
    ModelTurnRequest,
)
from workflow_skill_router.evaluation.reporting import build_benchmark_review_report
from workflow_skill_router.evaluation.local_evidence import LocalEvidenceProtector
from workflow_skill_router.evaluation.subprocess_adapter import SubprocessExecutionAdapter
from workflow_skill_router.schemas.artifacts import canonical_json_bytes


V2 = ROOT / "evaluation" / "v2"
EVALUATION_CONTRACT_ID = "workflow-skill-router.behavior-routing"
ROUTE_FIELDS = (
    "envelope",
    "selection_mode",
    "primary_skill",
    "support_skills",
    "consent_action",
    "goal_relation",
)


def digest(value: object) -> str:
    return "sha256:" + sha256(canonical_json_bytes(value)).hexdigest()


def load_cases(suite: str) -> list[dict[str, Any]]:
    cases = [
        json.loads(line)
        for line in (V2 / "cases" / "behavior-routing.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    revisions = {case.get("contract_revision") for case in cases}
    if revisions != {"2.2.0"}:
        raise EvaluationIntegrityError("evaluation_contract_revision_mismatch")
    if len({case["id"] for case in cases}) != len(cases):
        raise EvaluationIntegrityError("evaluation_case_id_duplicate")
    if suite == "full":
        return cases
    selected = json.loads((V2 / "profiles" / "beta-smoke.json").read_text(encoding="utf-8"))
    if (
        selected.get("contract_id") != EVALUATION_CONTRACT_ID
        or selected.get("contract_revision") not in revisions
    ):
        raise EvaluationIntegrityError("evaluation_profile_contract_mismatch")
    by_id = {case["id"]: case for case in cases}
    return [by_id[case_id] for case_id in selected["case_ids"]]


def load_profiles() -> dict[str, dict[str, Any]]:
    profiles = {
        "baseline": json.loads((V2 / "baselines" / "no-router.json").read_text(encoding="utf-8")),
        "candidate": json.loads((V2 / "profiles" / "router-v2.json").read_text(encoding="utf-8")),
    }
    validate_instruction_package(profiles["candidate"])
    if profiles["baseline"].get("execution", {}).get("mode") != "model-only":
        raise EvaluationIntegrityError("baseline_execution_mode_invalid")
    if profiles["candidate"].get("execution", {}).get("mode") != "hybrid-router":
        raise EvaluationIntegrityError("candidate_execution_mode_invalid")
    return profiles


def validate_instruction_package(profile: Mapping[str, Any]) -> None:
    package = profile.get("instruction_package")
    if not isinstance(package, Mapping):
        raise EvaluationIntegrityError("instruction_package_missing")
    relative_paths = package.get("files")
    declared_digest = package.get("digest")
    if not isinstance(relative_paths, list) or not relative_paths:
        raise EvaluationIntegrityError("instruction_package_files_invalid")
    if not isinstance(declared_digest, str) or not declared_digest.startswith("sha256:"):
        raise EvaluationIntegrityError("instruction_package_digest_invalid")

    records = []
    for relative in relative_paths:
        if not isinstance(relative, str) or not relative:
            raise EvaluationIntegrityError("instruction_package_path_invalid")
        path = (ROOT / relative).resolve()
        try:
            path.relative_to(ROOT.resolve())
        except ValueError as error:
            raise EvaluationIntegrityError("instruction_package_path_outside_root") from error
        if not path.is_file():
            raise EvaluationIntegrityError("instruction_package_file_missing")
        records.append({
            "path": path.relative_to(ROOT.resolve()).as_posix(),
            "sha256": sha256(path.read_bytes()).hexdigest(),
        })

    records.sort(key=lambda item: item["path"].casefold())
    if digest(records) != declared_digest:
        raise EvaluationIntegrityError("instruction_package_digest_mismatch")


def instruction_text(profile: Mapping[str, Any]) -> str:
    package = profile.get("instruction_package")
    if not isinstance(package, dict):
        return ""
    sections = []
    for relative in package["files"]:
        path = ROOT / relative
        sections.append(f"--- {relative} ---\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(sections)


def model_prompt(case: Mapping[str, Any], profile: Mapping[str, Any]) -> str:
    common = (
        "Return one routing decision as JSON. Do not execute the requested task. "
        "The public task and SKILL catalog are identical in both comparison arms."
    )
    catalog = json.dumps(profile["skill_catalog"], ensure_ascii=False)
    snapshot = case.get("capability_snapshot")
    snapshot_text = (
        "\n\nVerified capability snapshot:\n"
        + json.dumps(snapshot, ensure_ascii=False)
        if isinstance(snapshot, Mapping)
        else ""
    )
    public_input = (
        f"{common}\n\nAvailable SKILL catalog:\n{catalog}"
        f"{snapshot_text}\n\nUser task:\n{case['prompt']}"
    )
    instructions = instruction_text(profile)
    if instructions:
        return f"Router instruction package:\n{instructions}\n\n{public_input}"
    return public_input


def make_attempt_nonce(
    suite: str,
    arm: str,
    case_id: str,
    repeat: int,
    prompt: str,
    allowed_tools: list[str],
) -> str:
    binding = digest({
        "suite": suite,
        "arm": arm,
        "case_id": case_id,
        "repeat": repeat,
        "prompt_digest": digest({"prompt": prompt}),
        "tool_inventory_digest": digest({"allowed_tools": allowed_tools}),
    })
    return "attempt:" + binding.removeprefix("sha256:")


def public_case_payload(case: Mapping[str, Any]) -> dict[str, Any]:
    """建立不含 scoring key、可公開綁定的案例輸入。"""

    payload = {
        "id": case["id"],
        "contract_revision": case["contract_revision"],
        "prompt": case["prompt"],
        "allowed_tools": case["allowed_tools"],
        "interaction_script": case["interaction_script"],
    }
    snapshot = case.get("capability_snapshot")
    if isinstance(snapshot, Mapping):
        payload["capability_snapshot"] = snapshot
    return payload


def prepare_output_directory(
    output_dir: Path,
    protector: LocalEvidenceProtector,
) -> Path:
    """建立 restricted evidence root，並拒絕混用舊版公開 raw 產物。"""

    if output_dir.exists() and not output_dir.is_dir():
        raise EvaluationIntegrityError("benchmark_output_root_invalid")
    legacy_public_artifacts = (
        output_dir / "checkpoint.json",
        output_dir / "raw-results.json",
    )
    if any(path.exists() for path in legacy_public_artifacts):
        raise EvaluationIntegrityError("benchmark_legacy_public_evidence_present")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise EvaluationIntegrityError("benchmark_output_not_fresh")
    output_dir.mkdir(parents=True, exist_ok=True)
    restricted_dir = output_dir / "restricted"
    restricted_dir.mkdir(parents=True, exist_ok=True)
    protector.protect_directory(restricted_dir)
    return restricted_dir


def normalize_skill_id(value: object) -> object:
    if not isinstance(value, str):
        return value
    normalized = value.strip().lower()
    return normalized.removeprefix("skill:")


def normalized_field(name: str, value: object) -> object:
    if name == "primary_skill":
        return normalize_skill_id(value)
    if name == "support_skills" and isinstance(value, list):
        return sorted(normalize_skill_id(item) for item in value)
    return value


def _score_expected(
    expected: Mapping[str, Any],
    route: Mapping[str, Any] | None,
) -> tuple[bool, list[str]]:
    if route is None:
        return False, ["route-missing"]
    violations = [
        f"{name}-mismatch"
        for name in ROUTE_FIELDS
        if normalized_field(name, route.get(name)) != normalized_field(name, expected.get(name))
    ]
    hard = []
    if expected["selection_mode"] == "explicit-locked":
        if (
            route.get("selection_mode") != "explicit-locked"
            or normalize_skill_id(route.get("primary_skill")) != normalize_skill_id(expected["primary_skill"])
        ):
            hard.append("explicit-skill-not-preserved")
    if expected["consent_action"] in {"approved", "rejected"} and route.get("consent_action") != expected["consent_action"]:
        hard.append("scoped-consent-not-preserved")
    return not violations, hard


def score_route(case: Mapping[str, Any], route: Mapping[str, Any] | None) -> tuple[bool, list[str]]:
    return _score_expected(case["expected"], route)


def score_attempt(
    case: Mapping[str, Any],
    routes: list[Mapping[str, Any] | None],
) -> tuple[bool, list[str], list[bool]]:
    """逐 turn 驗證多階段／同意契約；單輪案例維持 final-route 相容性。"""

    declared = case.get("expected_turns")
    if isinstance(declared, list):
        expected_turns = declared
        actual_turns = routes
    else:
        expected_turns = [case["expected"]]
        actual_turns = [routes[-1] if routes else None]
    turn_passes: list[bool] = []
    hard: list[str] = []
    for index, expected in enumerate(expected_turns):
        route = actual_turns[index] if index < len(actual_turns) else None
        passed, turn_hard = _score_expected(expected, route)
        turn_passes.append(passed)
        hard.extend(f"turn-{index + 1}:{item}" for item in turn_hard)
    if len(actual_turns) != len(expected_turns):
        turn_passes.append(False)
    return all(turn_passes), hard, turn_passes


def arm_metrics(records: list[dict[str, Any]], cases: list[dict[str, Any]]) -> dict[str, object]:
    by_case = {case["id"]: case for case in cases}
    matches = {name: 0 for name in ROUTE_FIELDS}
    explicit_total = 0
    explicit_preserved = 0
    signatures: dict[str, set[str]] = {case["id"]: set() for case in cases}
    for record in records:
        expected = by_case[record["case_id"]]["expected"]
        route = record["route"]
        for name in ROUTE_FIELDS:
            if normalized_field(name, route.get(name)) == normalized_field(name, expected.get(name)):
                matches[name] += 1
        if expected["selection_mode"] == "explicit-locked":
            explicit_total += 1
            if (
                route.get("selection_mode") == "explicit-locked"
                and normalize_skill_id(route.get("primary_skill"))
                == normalize_skill_id(expected["primary_skill"])
            ):
                explicit_preserved += 1
        signature = {
            name: normalized_field(name, route.get(name))
            for name in ROUTE_FIELDS
        }
        signatures[record["case_id"]].add(json.dumps(signature, sort_keys=True, separators=(",", ":")))
    total = len(records)
    turn_total = sum(record.get("turn_count", 1) for record in records)
    turn_pass_total = sum(
        record.get("turn_pass_count", 1 if record["passed"] else 0)
        for record in records
    )
    return {
        "attempt_count": total,
        "route_contract_match_rate": sum(1 for record in records if record["passed"]) / total,
        "turn_contract_match_rate": turn_pass_total / turn_total if turn_total else None,
        "envelope_match_rate": matches["envelope"] / total,
        "selection_mode_match_rate": matches["selection_mode"] / total,
        "primary_skill_match_rate": matches["primary_skill"] / total,
        "support_skill_match_rate": matches["support_skills"] / total,
        "consent_decision_match_rate": matches["consent_action"] / total,
        "goal_relation_match_rate": matches["goal_relation"] / total,
        "explicit_skill_preservation": (
            explicit_preserved / explicit_total if explicit_total else None
        ),
        "hard_violation_count": sum(len(record["hard_violations"]) for record in records),
        "within_case_consistency_rate": (
            sum(1 for values in signatures.values() if len(values) == 1) / len(signatures)
        ),
    }


def case_diagnostics(
    records: list[dict[str, Any]],
    cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """輸出不含 prompt、expected/actual route value 的案例級聚合診斷。"""

    diagnostics: list[dict[str, Any]] = []
    for case in cases:
        expected = case["expected"]
        arms: dict[str, dict[str, Any]] = {}
        for arm in ("baseline", "candidate"):
            arm_records = [
                record
                for record in records
                if record["arm"] == arm and record["case_id"] == case["id"]
            ]
            total = len(arm_records)
            turn_count = sum(record.get("turn_count", 1) for record in arm_records)
            turn_pass_count = sum(
                record.get("turn_pass_count", 1 if record["passed"] else 0)
                for record in arm_records
            )
            matches = {name: 0 for name in ROUTE_FIELDS}
            for record in arm_records:
                route = record.get("route")
                route_mapping = route if isinstance(route, Mapping) else {}
                for name in ROUTE_FIELDS:
                    if normalized_field(name, route_mapping.get(name)) == normalized_field(
                        name,
                        expected.get(name),
                    ):
                        matches[name] += 1
            arms[arm] = {
                "attempt_count": total,
                "turn_count": turn_count,
                "turn_pass_count": turn_pass_count,
                "pass_count": sum(1 for record in arm_records if record["passed"]),
                "pass_rate": (
                    sum(1 for record in arm_records if record["passed"]) / total
                    if total
                    else None
                ),
                "hard_violation_count": sum(
                    len(record["hard_violations"])
                    for record in arm_records
                ),
                "turn_pass_rate": (
                    turn_pass_count / turn_count
                    if turn_count
                    else None
                ),
                "field_match_rates": {
                    name: matches[name] / total if total else None
                    for name in ROUTE_FIELDS
                },
            }
        baseline = arms["baseline"]
        candidate = arms["candidate"]
        diagnostics.append({
            "case_id": case["id"],
            "arms": arms,
            "candidate_minus_baseline": {
                "pass_rate": (
                    candidate["pass_rate"] - baseline["pass_rate"]
                    if candidate["pass_rate"] is not None
                    and baseline["pass_rate"] is not None
                    else None
                ),
                "turn_pass_rate": (
                    candidate["turn_pass_rate"] - baseline["turn_pass_rate"]
                    if candidate["turn_pass_rate"] is not None
                    and baseline["turn_pass_rate"] is not None
                    else None
                ),
                "hard_violation_count": (
                    candidate["hard_violation_count"]
                    - baseline["hard_violation_count"]
                ),
                "field_match_rates": {
                    name: (
                        candidate["field_match_rates"][name]
                        - baseline["field_match_rates"][name]
                        if candidate["field_match_rates"][name] is not None
                        and baseline["field_match_rates"][name] is not None
                        else None
                    )
                    for name in ROUTE_FIELDS
                },
            },
        })
    return diagnostics


def codex_version(adapter_arguments: list[str]) -> str | None:
    if "--codex-executable" not in adapter_arguments:
        return None
    index = adapter_arguments.index("--codex-executable") + 1
    if index >= len(adapter_arguments):
        return None
    try:
        result = subprocess.run(
            [adapter_arguments[index], "--version"],
            shell=False,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None


def adapter_option(adapter_arguments: list[str], name: str) -> str | None:
    if name not in adapter_arguments:
        return None
    index = adapter_arguments.index(name) + 1
    return adapter_arguments[index] if index < len(adapter_arguments) else None


def recover_attempt(
    attempt_root: Path | None,
    attempt_nonce: str,
    expected_turns: int,
) -> tuple[str, list[dict[str, Any]]] | None:
    if attempt_root is None or not attempt_root.is_dir():
        return None
    matches: list[tuple[float, str, list[dict[str, Any]]]] = []
    protector = LocalEvidenceProtector()
    for transcript_path in attempt_root.glob("*/transcript.json"):
        if (
            not protector.verify_directory(transcript_path.parent)
            or not protector.verify_file(transcript_path)
        ):
            continue
        try:
            transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        turns = transcript.get("turns")
        context_id = transcript_path.parent.name
        if transcript.get("attempt_nonce") != attempt_nonce or not isinstance(turns, list):
            continue
        if len(turns) != expected_turns or (transcript_path.parent / "failure.json").exists():
            continue
        responses = []
        valid = True
        for turn in turns:
            route = turn.get("assistant") if isinstance(turn, dict) else None
            if not isinstance(route, dict):
                valid = False
                break
            response = {
                "attempt_nonce": attempt_nonce,
                "context_id": context_id,
                "route": route,
                "text": json.dumps(route, ensure_ascii=False, sort_keys=True),
            }
            model_consent_intent = turn.get("model_consent_intent")
            if model_consent_intent is not None:
                if model_consent_intent not in {"approved", "rejected", "unclear"}:
                    valid = False
                    break
                response["model_consent_intent"] = model_consent_intent
            responses.append(response)
        if valid:
            matches.append((transcript_path.stat().st_mtime, context_id, responses))
    if not matches:
        return None
    if len(matches) > 1:
        raise EvaluationIntegrityError("resume_nonce_ambiguous")
    _, context_id, responses = max(matches, key=lambda item: item[0])
    return context_id, responses


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the paired Workflow Skill Router V2 benchmark")
    parser.add_argument("--suite", required=True, choices=("full", "beta-smoke"))
    parser.add_argument("--evidence-class", required=True, choices=("reference-driver", "behavior"))
    parser.add_argument("--adapter-executable", required=True)
    parser.add_argument("--adapter-arg", action="append", default=[])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--confirm-live-run", action="store_true")
    parser.add_argument("--excluded-preflight-attempts", type=int, default=0)
    parser.add_argument("--resume-attempt-root", type=Path)
    parser.add_argument("--execution-resumed-attempts", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.repeats < 3:
        raise SystemExit("Behavior benchmark requires at least three repeats.")
    if args.evidence_class == "behavior" and not args.confirm_live_run:
        raise SystemExit("Behavior model execution requires --confirm-live-run.")
    adapter_names = [Path(item).name for item in args.adapter_arg]
    if args.evidence_class == "behavior" and "reference_driver.py" in adapter_names:
        raise SystemExit("The reference driver cannot be relabeled as Behavior evidence.")

    cases = load_cases(args.suite)
    profiles = load_profiles()
    command = (args.adapter_executable, *args.adapter_arg)
    adapter = SubprocessExecutionAdapter(command, timeout_seconds=args.timeout_seconds)
    output_dir = args.output_dir.resolve()
    protector = LocalEvidenceProtector()
    restricted_dir = prepare_output_directory(output_dir, protector)
    records: list[dict[str, Any]] = []
    elapsed_values: list[float] = []
    resumed_attempt_count = 0
    expected_attempts = len(cases) * 2 * args.repeats
    resume_root = args.resume_attempt_root.resolve() if args.resume_attempt_root else None
    checkpoint_path = restricted_dir / "checkpoint.json"
    checkpoint_protected = False

    for arm, profile in profiles.items():
        for case in cases:
            prompt = model_prompt(case, profile)
            payload = ModelExecutionPayload(
                "case:" + sha256(case["id"].encode("utf-8")).hexdigest()[:24],
                prompt,
                EvaluationProfile.BEHAVIOR,
                tuple(case["allowed_tools"]),
                EvaluationExecutionMode(profile["execution"]["mode"]),
            )
            for repeat in range(args.repeats):
                print(
                    f"benchmark attempt {len(records) + 1}/{expected_attempts} "
                    f"arm={arm} case={case['id']} repeat={repeat + 1}",
                    file=sys.stderr,
                    flush=True,
                )
                nonce = make_attempt_nonce(
                    args.suite,
                    arm,
                    case["id"],
                    repeat,
                    prompt,
                    case["allowed_tools"],
                )
                prompts = (prompt, *case["interaction_script"])
                recovered = recover_attempt(resume_root, nonce, len(prompts))
                if recovered is not None:
                    context_id, responses = recovered
                    elapsed_ms = None
                    resumed_attempt_count += 1
                else:
                    started = time.perf_counter()
                    context_id = adapter.start_attempt(payload, nonce)
                    responses = []
                    for turn_index, turn_prompt in enumerate(prompts):
                        responses.append(dict(adapter.execute_turn(ModelTurnRequest(
                            nonce,
                            turn_index,
                            turn_prompt,
                            tuple(case["allowed_tools"]),
                        ))))
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    elapsed_values.append(elapsed_ms)
                routes = [
                    response.get("route")
                    if isinstance(response.get("route"), dict)
                    else None
                    for response in responses
                ]
                route = routes[-1] if routes else None
                model_consent_intent = next((
                    response.get("model_consent_intent")
                    for response in reversed(responses)
                    if response.get("model_consent_intent") is not None
                ), None)
                passed, hard_violations, turn_passes = score_attempt(case, routes)
                trace_digest = digest({"responses": responses})
                records.append({
                    "arm": arm,
                    "case_id": case["id"],
                    "opaque_run_case_id": payload.opaque_run_case_id,
                    "attempt_nonce": nonce,
                    "fresh_context_id": context_id,
                    "prompt_digest": digest({"prompt": prompt}),
                    "public_case_digest": digest(public_case_payload(case)),
                    "tool_inventory_digest": digest({"allowed_tools": case["allowed_tools"]}),
                    "trace_digest": trace_digest,
                    "elapsed_ms": elapsed_ms if args.evidence_class == "behavior" else None,
                    "route": route,
                    "model_consent_intent": model_consent_intent,
                    "hybrid_transition_applied": (
                        profile["execution"]["mode"] == "hybrid-router"
                        and model_consent_intent in {"approved", "rejected"}
                        and isinstance(route, dict)
                        and route.get("consent_action") == model_consent_intent
                    ),
                    "turn_count": len(routes),
                    "turn_pass_count": sum(1 for item in turn_passes if item),
                    "passed": passed,
                    "hard_violations": hard_violations,
                })
                checkpoint_path.write_text(
                    json.dumps({"records": records}, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                    encoding="utf-8",
                )
                if not checkpoint_protected:
                    protector.protect_file(checkpoint_path)
                    checkpoint_protected = True

    nonces = [record["attempt_nonce"] for record in records]
    contexts = [record["fresh_context_id"] for record in records]
    if len(records) != expected_attempts or len(set(nonces)) != expected_attempts or len(set(contexts)) != expected_attempts:
        raise EvaluationIntegrityError("benchmark_attempt_integrity_failed")
    if any(not record["trace_digest"] for record in records):
        raise EvaluationIntegrityError("benchmark_trace_digest_missing")
    if not protector.verify_file(checkpoint_path):
        raise EvaluationIntegrityError("benchmark_checkpoint_unprotected")

    pass_values = [1.0 if record["passed"] else 0.0 for record in records]
    explicit = [record for record in records if next(
        case for case in cases if case["id"] == record["case_id"]
    )["expected"]["selection_mode"] == "explicit-locked"]
    explicit_ok = [record for record in explicit if "explicit-skill-not-preserved" not in record["hard_violations"]]
    metric_status = "reference-only" if args.evidence_class == "reference-driver" else "observed"
    adapter_path = next((ROOT / item for item in args.adapter_arg if item.endswith(".py")), None)
    adapter_revision = (
        "sha256:" + sha256(adapter_path.read_bytes()).hexdigest()
        if adapter_path is not None and adapter_path.is_file() else None
    )
    live_elapsed = elapsed_values if args.evidence_class == "behavior" else []
    records_by_arm = {
        arm: [record for record in records if record["arm"] == arm]
        for arm in ("baseline", "candidate")
    }
    metrics_by_arm = {
        arm: arm_metrics(arm_records, cases)
        for arm, arm_records in records_by_arm.items()
    }
    delta_fields = (
        "route_contract_match_rate",
        "turn_contract_match_rate",
        "envelope_match_rate",
        "selection_mode_match_rate",
        "primary_skill_match_rate",
        "support_skill_match_rate",
        "consent_decision_match_rate",
        "goal_relation_match_rate",
        "explicit_skill_preservation",
        "hard_violation_count",
        "within_case_consistency_rate",
    )
    comparison_deltas = {
        name: metrics_by_arm["candidate"][name] - metrics_by_arm["baseline"][name]
        for name in delta_fields
        if metrics_by_arm["candidate"][name] is not None
        and metrics_by_arm["baseline"][name] is not None
    }
    public_case_set_digest = digest([public_case_payload(case) for case in cases])
    skill_catalog_digest = digest(profiles["baseline"]["skill_catalog"])
    arm_manifests = {
        arm: {
            "arm": arm,
            "attempt_count": len(arm_records),
            "case_ids": [case["id"] for case in cases],
            "public_case_set_digest": public_case_set_digest,
            "skill_catalog_digest": skill_catalog_digest,
            "execution_config_digest": digest(profiles[arm]["execution"]),
            "execution_mode": profiles[arm]["execution"]["mode"],
            "instruction_package_digest": (
                profiles[arm]["instruction_package"]["digest"]
                if profiles[arm]["instruction_package"] else None
            ),
            "attempt_nonces": [record["attempt_nonce"] for record in arm_records],
            "fresh_context_ids": [record["fresh_context_id"] for record in arm_records],
            "trace_digests": [record["trace_digest"] for record in arm_records],
        }
        for arm, arm_records in records_by_arm.items()
    }
    summary = {
        "suite": args.suite,
        "case_count": len(cases),
        "arm_count": 2,
        "attempt_count": len(records),
        "attempt_nonces": nonces,
        "fresh_context_ids": contexts,
        "paired_case_ids": [case["id"] for case in cases],
        "arm_manifests": arm_manifests,
        "comparison": {
            "paired_attempt_count": len(records_by_arm["baseline"]),
            "baseline": metrics_by_arm["baseline"],
            "candidate": metrics_by_arm["candidate"],
            "candidate_minus_baseline": comparison_deltas,
            "interpretation_status": "review-required",
        },
        "case_diagnostics": case_diagnostics(records, cases),
        "metrics": {
            "pass_rate": {"value": sum(pass_values) / len(pass_values), "metric_status": metric_status},
            "variance": {"value": statistics.pvariance(pass_values), "metric_status": metric_status},
            "hard_violations": {
                "value": sum(len(record["hard_violations"]) for record in records),
                "metric_status": metric_status,
            },
            "explicit_skill_preservation": {
                "value": len(explicit_ok) / len(explicit) if explicit else None,
                "metric_status": metric_status if explicit else "unavailable",
            },
            "support_activation": {"value": None, "metric_status": "not-observable"},
            "hybrid_consent_transition": {
                "value": (
                    None
                    if args.evidence_class == "reference-driver"
                    else
                    sum(
                        1 for record in records_by_arm["candidate"]
                        if record["hybrid_transition_applied"]
                    )
                    / sum(
                        1 for record in records_by_arm["candidate"]
                        if next(
                            case for case in cases if case["id"] == record["case_id"]
                        )["expected"]["consent_action"] in {"approved", "rejected"}
                    )
                    if any(
                        case["expected"]["consent_action"] in {"approved", "rejected"}
                        for case in cases
                    )
                    else None
                ),
                "metric_status": (
                    "reference-only"
                    if args.evidence_class == "reference-driver"
                    else "observed"
                    if any(
                        case["expected"]["consent_action"] in {"approved", "rejected"}
                        for case in cases
                    )
                    else "unavailable"
                ),
            },
            "real_tool_activation": {"value": None, "metric_status": "not-observable"},
            "latency_ms": {
                "value": sum(live_elapsed) / len(live_elapsed) if live_elapsed else None,
                "metric_status": (
                    "observed" if len(live_elapsed) == len(records)
                    else "partial" if live_elapsed
                    else "unavailable"
                ),
                "observed_attempt_count": len(live_elapsed),
            },
            "model_usage": {"value": None, "metric_status": "unavailable", "unit": "tokens"},
            "cost": {"value": None, "metric_status": "unavailable"},
        },
        "provenance": {
            "evaluation_contract_id": EVALUATION_CONTRACT_ID,
            "evaluation_contract_revision": cases[0]["contract_revision"],
            "adapter": adapter_names[0] if adapter_names else None,
            "adapter_revision": adapter_revision,
            "codex_cli_version": codex_version(args.adapter_arg),
            "model_identifier": adapter_option(args.adapter_arg, "--model"),
            "model_identity_status": (
                "configured" if adapter_option(args.adapter_arg, "--model") else "unavailable"
            ),
            "sampling_settings": None,
            "sampling_settings_status": "unavailable",
            "adapter_timeout_seconds": args.timeout_seconds,
            "model_turn_timeout_seconds": int(
                adapter_option(args.adapter_arg, "--timeout-seconds") or args.timeout_seconds
            ),
            "repeats": args.repeats,
            "router_instruction_digest": profiles["candidate"]["instruction_package"]["digest"],
            "excluded_preflight_attempts": args.excluded_preflight_attempts,
            "execution_resumed_attempt_count": (
                args.execution_resumed_attempts
                if args.execution_resumed_attempts is not None
                else resumed_attempt_count
            ),
            "report_recovered_attempt_count": resumed_attempt_count,
            "evidence_protection": {
                "kind": "os-permission",
                "status": "verified",
                "directory": restricted_dir.name,
                "artifacts": ["checkpoint.json", "raw-results.json"],
            },
        },
        "attempts": [{
            key: record[key]
            for key in (
                "arm", "case_id", "opaque_run_case_id", "attempt_nonce", "fresh_context_id",
                "prompt_digest", "public_case_digest", "tool_inventory_digest", "trace_digest", "elapsed_ms",
                "turn_count", "turn_pass_count", "passed", "hard_violations",
                "model_consent_intent", "hybrid_transition_applied",
            )
        } for record in records],
        "limitations": [
            (
                "The reference driver does not execute the hybrid consent state machine, so hybrid transition metrics are unavailable."
                if args.evidence_class == "reference-driver"
                else "The candidate consent route is materialized through the deterministic core after a fresh model classifies consent intent."
            ),
            "Node MCP transport and fail-closed scope behavior require matching deterministic integration evidence from the same source revision.",
            "Real SKILL activation and task Outcome are not observable, so this report alone cannot establish hybrid-full conformance.",
        ],
    }
    report = build_benchmark_review_report(
        summary,
        args.evidence_class,
        evidence_class_locked=args.evidence_class == "reference-driver",
    )
    raw_path = restricted_dir / "raw-results.json"
    raw_path.write_text(json.dumps({
        "adapter_command": list(command),
        "records": records,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    protector.protect_file(raw_path)
    report_path = output_dir / "sanitized-report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "attempt_count": len(records),
        "evidence_class": args.evidence_class,
        "report": report_path.name,
        "status": "review-required",
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
