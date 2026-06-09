"""Batch experiment meta updates for UI SSE and CLI runners."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from service.meta.loader import MetaLoader


def batch_progress_pct(completed: int, total: int) -> int:
    if total <= 0:
        return 100
    return int(completed / total * 100)


def build_batch_finalize_update(
    *,
    status: str,
    completed: int,
    total: int,
    error: str = "",
    failed_at_sample: int | None = None,
) -> dict[str, Any]:
    """Build meta/exps update payload for batch run finalization."""
    progress = batch_progress_pct(completed, total)
    if status == "completed" and completed >= total:
        progress = 100
    payload: dict[str, Any] = {"status": status, "progress": progress}
    if status == "failed":
        payload["last_error"] = error or "Batch run failed"
        if failed_at_sample is not None:
            payload["failed_at_sample"] = failed_at_sample
    elif status == "completed":
        payload["last_error"] = ""
        payload["failed_at_sample"] = None
    return payload


def append_batch_failure_history(exp_id: str, *, idx: int, error: str) -> None:
    exp_cfg = MetaLoader.load("exps", exp_id) or {}
    history = list(exp_cfg.get("history") or [])
    history.append(
        {
            "idx": idx,
            "timestamp": datetime.now().isoformat(),
            "status": "failed",
            "error": error,
        }
    )
    MetaLoader.update("exps", exp_id, {"history": history})


def finalize_batch_exp_meta(
    exp_id: str,
    *,
    status: str,
    completed: int,
    total: int,
    error: str = "",
    failed_at_sample: int | None = None,
    record_history: bool = False,
) -> None:
    payload = build_batch_finalize_update(
        status=status,
        completed=completed,
        total=total,
        error=error,
        failed_at_sample=failed_at_sample,
    )
    MetaLoader.update("exps", exp_id, payload)
    if record_history and status == "failed" and failed_at_sample is not None and error:
        append_batch_failure_history(exp_id, idx=failed_at_sample, error=error)
