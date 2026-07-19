from __future__ import annotations

from contextlib import closing
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3

from .contracts import EvaluationAttempt, EvaluationRunResult


class EvaluationStore:
    def __init__(self, database: Path) -> None:
        self._database = database

    def save_run(self, result: EvaluationRunResult, authorization_ref: str, created_at: str,
                 raw_trace_ref: str | None = None) -> None:
        combined = "sha256:none" if not result.attempts else result.attempts[0].raw_trace_digest
        with closing(sqlite3.connect(self._database)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO evaluation_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (result.run_id, authorization_ref, result.profile.value, result.adapter_kind,
                 result.status.value, result.manifest_digest, raw_trace_ref, combined, created_at),
            )
            connection.executemany(
                "INSERT INTO evaluation_attempts VALUES (?, ?, ?, ?, ?, ?)",
                [(item.attempt_id, result.run_id, item.fresh_context_id, item.status.value,
                  item.raw_trace_digest, item.failure) for item in result.attempts],
            )
            connection.commit()

    def load_run(self, run_id: str) -> dict[str, object]:
        with closing(sqlite3.connect(self._database)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT * FROM evaluation_runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise LookupError(run_id)
        return dict(row)

    def save_score(self, run_id: str, score_digest: str, hard_violations: int,
                   metrics: dict[str, object], release_eligible: bool) -> None:
        with closing(sqlite3.connect(self._database)) as connection:
            connection.execute("INSERT INTO evaluation_scores VALUES (?, ?, ?, ?, ?)", (
                run_id, score_digest, hard_violations,
                json.dumps(metrics, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                int(release_eligible),
            ))
            connection.commit()
