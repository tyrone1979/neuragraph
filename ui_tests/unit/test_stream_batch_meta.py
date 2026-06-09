"""Tests for batch SSE experiment meta finalization."""

from service.experiment_batch_meta import build_batch_finalize_update


def test_build_batch_finalize_failed_keeps_partial_progress():
    payload = build_batch_finalize_update(
        status="failed",
        completed=190,
        total=500,
        error="LLM timeout",
        failed_at_sample=191,
    )
    assert payload["status"] == "failed"
    assert payload["progress"] == 38
    assert payload["last_error"] == "LLM timeout"
    assert payload["failed_at_sample"] == 191


def test_build_batch_finalize_completed_clears_error():
    payload = build_batch_finalize_update(
        status="completed",
        completed=500,
        total=500,
    )
    assert payload["status"] == "completed"
    assert payload["progress"] == 100
    assert payload["last_error"] == ""
    assert payload["failed_at_sample"] is None


def test_build_batch_finalize_does_not_force_100_on_failed():
    payload = build_batch_finalize_update(
        status="failed",
        completed=10,
        total=100,
        error="boom",
        failed_at_sample=11,
    )
    assert payload["progress"] == 10
    assert "failed_at_sample" in payload
