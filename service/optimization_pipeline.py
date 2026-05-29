"""Per-step optimization pipeline runners with persisted context."""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from service.optimize_suggestion_filter import filter_disallowed_modifications
from service.experiment_optimize import (
    ROOT,
    _apply_modifications,
    _avg_metrics,
    _baseline_report_ready,
    _baseline_test_ready,
    _baseline_test_report_path,
    _build_exp_cfg,
    _build_report_payload,
    _compare_reports_with_llm,
    _create_candidate_graph,
    _generate_and_save_report,
    _generate_report,
    _now_tag,
    _resolve_dual_datasets,
    _restore_agents_after_negative_delta,
    _run_experiment,
    _run_refiner,
    _score_report_quality,
    _set_flow_step,
    _snapshot_accepted_modifications,
    _write_text,
    generate_baseline_test_report,
    init_optimization_flow_steps,
)
from service.meta.loader import MetaLoader
from service.result.loader import ResultLoader


FLOW_STEP_ORDER = [
    "baseline_test",
    "baseline_test_report",
    "baseline_tuning",
    "baseline_tuning_report",
    "optimize_rounds",
    "final_test",
    "final_test_report",
]


def _ctx_path(exp_id: str) -> Path:
    return ROOT / "result" / exp_id / "optimization_context.json"


def load_opt_context(exp_id: str) -> dict[str, Any]:
    path = _ctx_path(exp_id)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_opt_context(exp_id: str, ctx: dict[str, Any]) -> None:
    _write_text(_ctx_path(exp_id), json.dumps(ctx, ensure_ascii=False, indent=2))


def _step_index(step_id: str) -> int:
    try:
        return FLOW_STEP_ORDER.index(step_id)
    except ValueError as ex:
        raise RuntimeError(f"Unknown optimization step: {step_id}") from ex


def clear_downstream_optimization(exp_id: str, from_step_id: str) -> None:
    """Clear artifacts and context for steps after from_step_id."""
    idx = _step_index(from_step_id)
    downstream = set(FLOW_STEP_ORDER[idx + 1 :])
    ctx = load_opt_context(exp_id)
    compare_tag = str(ctx.get("tag") or "")
    result_dir = ROOT / "result" / exp_id

    if "baseline_test_report" in downstream:
        report = _baseline_test_report_path(exp_id)
        if report.is_file():
            report.unlink()

    if downstream & {
        "baseline_tuning",
        "baseline_tuning_report",
        "optimize_rounds",
        "final_test",
        "final_test_report",
    }:
        ctx = {}
        if compare_tag:
            compare = ROOT / "result" / f"opt_compare_{compare_tag}.json"
            if compare.is_file():
                compare.unlink()

    if from_step_id == "baseline_test":
        states = result_dir / "states.json"
        if states.is_file():
            states.unlink()
        report = _baseline_test_report_path(exp_id)
        if report.is_file():
            report.unlink()
        ctx = {}

    save_opt_context(exp_id, ctx)


def reset_baseline_test(exp_id: str) -> None:
    exp_cfg = MetaLoader.load("exps", exp_id) or {}
    exp_cfg["status"] = "pending"
    exp_cfg["progress"] = 0
    MetaLoader.dump("exps", exp_id, exp_cfg)
    clear_downstream_optimization(exp_id, "baseline_test")


def _resolve_datasets(
    exp_id: str,
    *,
    tuning_dataset: str = "",
    test_dataset: str = "",
) -> tuple[dict[str, Any], str, str]:
    baseline_cfg = MetaLoader.load("exps", exp_id) or {}
    baseline_cfg["exp_id"] = exp_id
    cfg_tuning, cfg_test = _resolve_dual_datasets(baseline_cfg)
    active_tuning = str(tuning_dataset or "").strip() or cfg_tuning
    active_test = str(test_dataset or "").strip() or cfg_test
    if not active_tuning or not active_test:
        raise RuntimeError("tuning_dataset and test_dataset are required.")
    baseline_cfg["tuning_dataset"] = active_tuning
    baseline_cfg["test_dataset"] = active_test
    baseline_cfg["dataset"] = active_test
    MetaLoader.dump("exps", exp_id, baseline_cfg)
    return baseline_cfg, active_tuning, active_test


def _flow_from_context(exp_id: str, exp_cfg: dict[str, Any], tuning: str, test: str) -> list[dict[str, Any]]:
    flow_steps = init_optimization_flow_steps()
    if _baseline_test_ready(exp_cfg, test):
        _set_flow_step(flow_steps, "baseline_test", "done", f"Completed on {test}")
    if _baseline_report_ready(exp_id):
        _set_flow_step(flow_steps, "baseline_test_report", "done", "Baseline test report ready")
    ctx = load_opt_context(exp_id)
    tune_id = str(ctx.get("baseline_tune_exp_id") or "")
    if tune_id:
        tune_cfg = MetaLoader.load("exps", tune_id) or {}
        if str(tune_cfg.get("status") or "").lower() == "completed":
            _set_flow_step(flow_steps, "baseline_tuning", "done", f"Tuning baseline on {tuning}")
    if ctx.get("modifications") is not None and ctx.get("baseline_tuning_report_path"):
        _set_flow_step(
            flow_steps,
            "baseline_tuning_report",
            "done",
            f"{len(ctx.get('modifications') or [])} suggestion(s)",
        )
    rounds = ctx.get("rounds") or []
    if rounds is not None and ctx.get("optimize_rounds_done"):
        accepted = sum(1 for r in rounds if r.get("accepted"))
        _set_flow_step(
            flow_steps,
            "optimize_rounds",
            "done",
            f"{accepted} accepted of {len(rounds)}",
        )
    if ctx.get("optimized_test_exp_id"):
        _set_flow_step(flow_steps, "final_test", "done", "Optimized test completed")
    if ctx.get("optimized_test_report_path"):
        _set_flow_step(flow_steps, "final_test_report", "done", "Compare reports ready")
    return flow_steps


def optimization_flow_state(exp_id: str) -> dict[str, Any]:
    exp_cfg = MetaLoader.load("exps", exp_id) or {}
    exp_cfg["exp_id"] = exp_id
    tuning, test = _resolve_dual_datasets(exp_cfg)
    flow_steps = _flow_from_context(exp_id, exp_cfg, tuning, test)
    ready = _baseline_test_ready(exp_cfg, test)
    report_ready = _baseline_report_ready(exp_id)
    return {
        "exp_id": exp_id,
        "baseline_test_ready": ready,
        "baseline_report_ready": report_ready,
        "awaiting_optimization_confirm": ready and report_ready,
        "status": str(exp_cfg.get("status") or ""),
        "tuning_dataset": tuning,
        "test_dataset": test,
        "baseline_test_metrics": _avg_metrics(exp_id) if ready else {},
        "flow_steps": flow_steps,
        "context": load_opt_context(exp_id),
    }


def run_optimization_step(
    exp_id: str,
    step_id: str,
    *,
    tuning_dataset: str = "",
    test_dataset: str = "",
    max_agent_updates: int = 3,
    progress_cb: Callable[[dict[str, Any]], None] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    if step_id not in FLOW_STEP_ORDER:
        raise RuntimeError(f"Unknown step: {step_id}")

    if force:
        clear_downstream_optimization(exp_id, step_id)

    baseline_cfg, active_tuning, active_test = _resolve_datasets(
        exp_id, tuning_dataset=tuning_dataset, test_dataset=test_dataset
    )
    ctx = load_opt_context(exp_id)
    flow_steps = _flow_from_context(exp_id, baseline_cfg, active_tuning, active_test)

    def emit(
        progress: int,
        stage: str,
        message: str,
        *,
        flow_step: str = "",
        flow_status: str = "",
        flow_detail: str = "",
    ) -> None:
        if flow_step and flow_status:
            _set_flow_step(flow_steps, flow_step, flow_status, flow_detail)
        if progress_cb:
            progress_cb(
                {
                    "progress": progress,
                    "stage": stage,
                    "message": message,
                    "flow_step": flow_step,
                    "flow_status": flow_status,
                    "flow_steps": [dict(s) for s in flow_steps],
                }
            )

    if step_id == "baseline_test":
        reset_baseline_test(exp_id)
        _set_flow_step(flow_steps, "baseline_test", "pending", "Ready to run baseline test")
        emit(0, "baseline_test", "Reset baseline test — run via stream", flow_step="baseline_test", flow_status="pending")
        return {
            "step_id": step_id,
            "needs_stream": True,
            "flow_steps": flow_steps,
        }

    if step_id == "baseline_test_report":
        if not _baseline_test_ready(baseline_cfg, active_test):
            raise RuntimeError("Complete baseline test (step 1) first.")
        emit(10, "baseline_test_report", "Generating baseline test report", flow_step="baseline_test_report", flow_status="running")
        data = generate_baseline_test_report(exp_id)
        _set_flow_step(flow_steps, "baseline_test_report", "done", "Baseline test report ready")
        emit(100, "baseline_test_report_done", "Report ready", flow_step="baseline_test_report", flow_status="done")
        return {"step_id": step_id, "flow_steps": flow_steps, **data}

    if step_id == "baseline_tuning":
        if not _baseline_report_ready(exp_id):
            raise RuntimeError("Complete baseline test report (step 2) first.")
        tune_id = str(ctx.get("baseline_tune_exp_id") or "")
        if tune_id and not force:
            tune_cfg = MetaLoader.load("exps", tune_id) or {}
            if str(tune_cfg.get("status") or "").lower() == "completed":
                _set_flow_step(flow_steps, "baseline_tuning", "done", f"Reusing {tune_id}")
                return {"step_id": step_id, "flow_steps": flow_steps, "baseline_tune_exp_id": tune_id}

        tune_id = f"opt_base_tune_{uuid.uuid4().hex[:8]}"
        tune_cfg = _build_exp_cfg(
            exp_id=tune_id,
            runner_id=str(baseline_cfg.get("runner_id") or ""),
            dataset=active_tuning,
            tuning_dataset=active_tuning,
            test_dataset=active_test,
            runner_type=str(baseline_cfg.get("runner_type") or "graph"),
        )
        MetaLoader.dump("exps", tune_id, tune_cfg)
        emit(20, "baseline_tuning", "Running tuning baseline", flow_step="baseline_tuning", flow_status="running")
        _run_experiment(tune_cfg)
        ctx["baseline_tune_exp_id"] = tune_id
        ctx["tag"] = ctx.get("tag") or _now_tag()
        save_opt_context(exp_id, ctx)
        _set_flow_step(flow_steps, "baseline_tuning", "done", f"Completed {tune_id}")
        emit(100, "baseline_tuning_done", "Tuning baseline done", flow_step="baseline_tuning", flow_status="done")
        return {"step_id": step_id, "flow_steps": flow_steps, "baseline_tune_exp_id": tune_id}

    if step_id == "baseline_tuning_report":
        tune_id = str(ctx.get("baseline_tune_exp_id") or "")
        if not tune_id:
            raise RuntimeError("Complete tuning baseline run (step 3) first.")
        tune_cfg = MetaLoader.load("exps", tune_id) or {}
        emit(30, "baseline_tuning_report", "Generating tuning report", flow_step="baseline_tuning_report", flow_status="running")
        baseline_payload = _build_report_payload(tune_id, tune_cfg)
        baseline_report = _generate_report(baseline_payload)
        report_path = ROOT / "result" / tune_id / "report_tuning_baseline.md"
        _write_text(report_path, baseline_report)
        _write_text(ROOT / "result" / tune_id / "report.md", baseline_report)
        raw_modifications = _run_refiner(
            baseline_report,
            baseline_payload,
            max_updates=max(10, max_agent_updates),
        )
        modifications, filtered_modifications = filter_disallowed_modifications(
            [m for m in raw_modifications if isinstance(m, dict) and str(m.get("target_agent_id") or "").strip()]
        )
        ctx["baseline_tuning_report_path"] = str(report_path)
        ctx["modifications"] = modifications
        ctx["filtered_modifications"] = filtered_modifications
        ctx["current_best_exp_id"] = tune_id
        ctx["current_best_report"] = baseline_report
        ctx["current_best_metrics"] = _avg_metrics(tune_id)
        ctx["cumulative_version_map"] = {}
        ctx["rounds"] = []
        save_opt_context(exp_id, ctx)
        detail = f"{len(modifications)} suggestion(s)"
        if filtered_modifications:
            detail += f" ({len(filtered_modifications)} filtered)"
        _set_flow_step(flow_steps, "baseline_tuning_report", "done", detail)
        emit(100, "baseline_tuning_report_done", detail, flow_step="baseline_tuning_report", flow_status="done", flow_detail=detail)
        return {
            "step_id": step_id,
            "flow_steps": flow_steps,
            "suggestion_count": len(modifications),
            "baseline_tuning_report_path": str(report_path),
        }

    if step_id == "optimize_rounds":
        modifications = ctx.get("modifications") or []
        if not ctx.get("baseline_tune_exp_id"):
            raise RuntimeError("Complete tuning report (step 4) first.")
        base_runner = str(baseline_cfg.get("runner_id") or "")
        if not base_runner:
            raise RuntimeError("Missing runner_id")
        tag = str(ctx.get("tag") or _now_tag())
        ctx["tag"] = tag
        current_best_exp_id = str(ctx.get("current_best_exp_id") or ctx["baseline_tune_exp_id"])
        current_best_report = str(ctx.get("current_best_report") or "")
        current_best_metrics = dict(ctx.get("current_best_metrics") or _avg_metrics(current_best_exp_id))
        current_best_report_score = _score_report_quality(current_best_report, metrics_delta=None, is_candidate=False)
        cumulative_version_map: dict[str, str] = dict(ctx.get("cumulative_version_map") or {})
        rounds: list[dict[str, Any]] = list(ctx.get("rounds") or [])
        total_rounds = len(modifications)

        _set_flow_step(flow_steps, "optimize_rounds", "running", f"0 / {total_rounds} rounds")
        emit(5, "optimize_rounds", f"Starting {total_rounds} round(s)", flow_step="optimize_rounds", flow_status="running")

        start_idx = len(rounds) + 1 if rounds and not force else 1
        if force:
            rounds = []
            cumulative_version_map = {}
            start_idx = 1

        for idx, mod in enumerate(modifications, start=1):
            if idx < start_idx:
                continue
            target_agent = str(mod.get("target_agent_id") or "").strip()
            prev_best_exp_id = current_best_exp_id
            prev_best_report = current_best_report
            prev_best_metrics = dict(current_best_metrics)
            prev_best_report_score = dict(current_best_report_score)
            emit(
                5 + int((idx - 1) * 90 / max(1, total_rounds)),
                "round_apply",
                f"Round {idx}/{total_rounds}: {target_agent}",
                flow_step="optimize_rounds",
                flow_status="running",
                flow_detail=f"Round {idx}/{total_rounds}",
            )
            _vmap, originals, applied = _apply_modifications(
                [mod], max_updates=1, change_note_prefix=f"opt_loop {tag} r{idx}"
            )
            if not applied:
                rounds.append(
                    {
                        "round": idx,
                        "target_agent_id": target_agent,
                        "status": "skipped",
                        "reason": "modification produced no effective change",
                    }
                )
                continue
            candidate_exp_id = f"opt_cand_{tag}_r{idx}_{uuid.uuid4().hex[:8]}"
            candidate_cfg = _build_exp_cfg(
                exp_id=candidate_exp_id,
                runner_id=base_runner,
                dataset=active_tuning,
                tuning_dataset=active_tuning,
                test_dataset=active_test,
                runner_type=str(baseline_cfg.get("runner_type") or "graph"),
            )
            MetaLoader.dump("exps", candidate_exp_id, candidate_cfg)
            try:
                _run_experiment(candidate_cfg)
                candidate_payload = _build_report_payload(candidate_exp_id, candidate_cfg)
                candidate_report = _generate_report(candidate_payload)
                _write_text(ROOT / "result" / candidate_exp_id / "report.md", candidate_report)
                cand_metrics = _avg_metrics(candidate_exp_id)
                delta: dict[str, float] = {}
                for k in ("precision", "recall", "f1"):
                    if k in prev_best_metrics and k in cand_metrics:
                        delta[k] = cand_metrics[k] - prev_best_metrics[k]
                f1_delta = float(delta["f1"]) if "f1" in delta else None
                accepted = f1_delta is not None and f1_delta > 0
                round_reason = "f1 improved" if accepted else "f1 did not improve"
                restored_agents: list[str] = []
                version_map: dict[str, str] = {}
                display_exp_id = candidate_exp_id
                display_graph_id = base_runner
                display_metrics = dict(cand_metrics)
                if accepted:
                    version_map = _snapshot_accepted_modifications(
                        applied, [mod], max_updates=1, change_note_prefix=f"opt_loop {tag} r{idx}"
                    )
                    cumulative_version_map.update(version_map)
                    if version_map:
                        try:
                            round_graph_id = f"{base_runner}_opt_{tag}_r{idx}"
                            display_graph_id = _create_candidate_graph(
                                base_runner,
                                cumulative_version_map,
                                round_graph_id,
                                datasets=[active_tuning, active_test],
                            )
                            pinned_exp_id = f"opt_pinned_{tag}_r{idx}_{uuid.uuid4().hex[:8]}"
                            pinned_cfg = _build_exp_cfg(
                                exp_id=pinned_exp_id,
                                runner_id=display_graph_id,
                                dataset=active_tuning,
                                tuning_dataset=active_tuning,
                                test_dataset=active_test,
                                runner_type=str(baseline_cfg.get("runner_type") or "graph"),
                            )
                            MetaLoader.dump("exps", pinned_exp_id, pinned_cfg)
                            _run_experiment(pinned_cfg)
                            pinned_payload = _build_report_payload(pinned_exp_id, pinned_cfg)
                            pinned_report = _generate_report(pinned_payload)
                            _write_text(ROOT / "result" / pinned_exp_id / "report.md", pinned_report)
                            display_exp_id = pinned_exp_id
                            display_metrics = _avg_metrics(pinned_exp_id) or dict(cand_metrics)
                        except Exception:
                            display_exp_id = candidate_exp_id
                            display_graph_id = base_runner
                            display_metrics = dict(cand_metrics)
                    current_best_exp_id = display_exp_id
                    current_best_report = candidate_report
                    current_best_metrics = display_metrics
                    current_best_report_score = _score_report_quality(
                        candidate_report, metrics_delta=delta, is_candidate=True
                    )
                else:
                    restored_agents = _restore_agents_after_negative_delta(
                        originals,
                        reason=(
                            "missing f1 delta"
                            if f1_delta is None
                            else f"non-positive f1 delta ({f1_delta:.6f})"
                        ),
                    )
                candidate_report_score = _score_report_quality(
                    candidate_report, metrics_delta=delta, is_candidate=True
                )
                llm_compare = _compare_reports_with_llm(
                    {
                        "baseline_exp_id": prev_best_exp_id,
                        "candidate_exp_id": candidate_exp_id,
                        "baseline_report": prev_best_report,
                        "candidate_report": candidate_report,
                        "baseline_metrics": prev_best_metrics,
                        "candidate_metrics": cand_metrics,
                        "metrics_delta": delta,
                        "version_map": version_map,
                        "baseline_report_score": prev_best_report_score,
                        "candidate_report_score": candidate_report_score,
                    }
                )
                rounds.append(
                    {
                        "round": idx,
                        "target_agent_id": target_agent,
                        "candidate_exp_id": candidate_exp_id,
                        "candidate_graph_id": base_runner,
                        "display_exp_id": display_exp_id,
                        "display_graph_id": display_graph_id,
                        "baseline_metrics": prev_best_metrics,
                        "candidate_metrics": display_metrics,
                        "metrics_delta": delta,
                        "accepted": accepted,
                        "reason": round_reason,
                        "restored_agents": restored_agents,
                        "version_map": version_map,
                        "baseline_report_score": prev_best_report_score,
                        "candidate_report_score": candidate_report_score,
                        "llm_compare": llm_compare,
                    }
                )
            except Exception as round_ex:
                restored_agents = _restore_agents_after_negative_delta(
                    originals, reason=f"round failed: {round_ex}"
                )
                rounds.append(
                    {
                        "round": idx,
                        "target_agent_id": target_agent,
                        "status": "skipped",
                        "reason": str(round_ex)[:500],
                        "restored_agents": restored_agents,
                    }
                )

        ctx["rounds"] = rounds
        ctx["cumulative_version_map"] = cumulative_version_map
        ctx["current_best_exp_id"] = current_best_exp_id
        ctx["current_best_report"] = current_best_report
        ctx["current_best_metrics"] = current_best_metrics
        ctx["optimize_rounds_done"] = True
        save_opt_context(exp_id, ctx)
        accepted_total = sum(1 for r in rounds if r.get("accepted"))
        detail = f"{accepted_total} accepted of {total_rounds}"
        _set_flow_step(flow_steps, "optimize_rounds", "done", detail)
        emit(100, "optimize_rounds_done", detail, flow_step="optimize_rounds", flow_status="done", flow_detail=detail)
        return {"step_id": step_id, "flow_steps": flow_steps, "rounds": rounds, "accepted_total": accepted_total}

    if step_id == "final_test":
        cumulative_version_map = dict(ctx.get("cumulative_version_map") or {})
        if not cumulative_version_map:
            _set_flow_step(flow_steps, "final_test", "skipped", "No accepted agent changes")
            _set_flow_step(flow_steps, "final_test_report", "skipped", "No optimized test report")
            ctx["optimized_test_exp_id"] = ""
            save_opt_context(exp_id, ctx)
            return {"step_id": step_id, "flow_steps": flow_steps, "skipped": True}
        base_runner = str(baseline_cfg.get("runner_id") or "")
        tag = str(ctx.get("tag") or _now_tag())
        final_graph_id = _create_candidate_graph(
            base_runner,
            cumulative_version_map,
            f"{base_runner}_opt_{tag}",
            datasets=[active_tuning, active_test],
        )
        final_exp_id = f"opt_best_{tag}_{uuid.uuid4().hex[:8]}"
        final_cfg = _build_exp_cfg(
            exp_id=final_exp_id,
            runner_id=final_graph_id,
            dataset=active_test,
            tuning_dataset=active_tuning,
            test_dataset=active_test,
            runner_type=str(baseline_cfg.get("runner_type") or "graph"),
        )
        MetaLoader.dump("exps", final_exp_id, final_cfg)
        emit(50, "final_test", "Running optimized workflow on test dataset", flow_step="final_test", flow_status="running")
        _run_experiment(final_cfg)
        ctx["final_graph_id"] = final_graph_id
        ctx["optimized_test_exp_id"] = final_exp_id
        save_opt_context(exp_id, ctx)
        _set_flow_step(flow_steps, "final_test", "done", f"Completed {final_exp_id}")
        emit(100, "final_test_done", "Optimized test done", flow_step="final_test", flow_status="done")
        return {"step_id": step_id, "flow_steps": flow_steps, "optimized_test_exp_id": final_exp_id}

    if step_id == "final_test_report":
        final_exp_id = str(ctx.get("optimized_test_exp_id") or "")
        if not final_exp_id:
            raise RuntimeError("Complete optimized test run (step 6) first.")
        final_cfg = MetaLoader.load("exps", final_exp_id) or {}
        emit(80, "final_test_report", "Generating optimized test report", flow_step="final_test_report", flow_status="running")
        report_path = _generate_and_save_report(final_exp_id, final_cfg, "report_optimized_test.md")
        final_report = Path(report_path).read_text(encoding="utf-8")
        _write_text(ROOT / "result" / final_exp_id / "report.md", final_report)
        ctx["optimized_test_report_path"] = report_path
        save_opt_context(exp_id, ctx)

        tag = str(ctx.get("tag") or _now_tag())
        summary = _build_summary(exp_id, baseline_cfg, active_tuning, active_test, ctx, flow_steps)
        compare_path = ROOT / "result" / f"opt_compare_{tag}.json"
        _write_text(compare_path, json.dumps(summary, ensure_ascii=False, indent=2))
        summary["compare_path"] = str(compare_path)

        _set_flow_step(flow_steps, "final_test_report", "done", "Compare reports ready")
        emit(100, "final_test_report_done", "Done", flow_step="final_test_report", flow_status="done")
        return {"step_id": step_id, "flow_steps": flow_steps, "summary": summary}

    raise RuntimeError(f"Unhandled step: {step_id}")


def _build_summary(
    exp_id: str,
    baseline_cfg: dict[str, Any],
    active_tuning: str,
    active_test: str,
    ctx: dict[str, Any],
    flow_steps: list[dict[str, Any]],
) -> dict[str, Any]:
    tune_id = str(ctx.get("baseline_tune_exp_id") or "")
    current_best_exp_id = str(ctx.get("current_best_exp_id") or tune_id)
    rounds = list(ctx.get("rounds") or [])
    cumulative_version_map = dict(ctx.get("cumulative_version_map") or {})
    optimized_test_exp_id = str(ctx.get("optimized_test_exp_id") or "")
    return {
        "source_exp_id": exp_id,
        "baseline_exp_id": exp_id,
        "baseline_tuning_exp_id": tune_id,
        "baseline_runner_id": str(baseline_cfg.get("runner_id") or ""),
        "tuning_dataset": active_tuning,
        "test_dataset": active_test,
        "baseline_test_metrics": _avg_metrics(exp_id),
        "baseline_test_report_path": str(_baseline_test_report_path(exp_id)),
        "baseline_tuning_report_path": str(ctx.get("baseline_tuning_report_path") or ""),
        "optimized_test_exp_id": optimized_test_exp_id,
        "optimized_test_report_path": str(ctx.get("optimized_test_report_path") or ""),
        "flow_steps": flow_steps,
        "suggestion_count": len(ctx.get("modifications") or []),
        "rounds": rounds,
        "modifications": ctx.get("modifications") or [],
        "filtered_modifications": ctx.get("filtered_modifications") or [],
        "accepted_version_map": cumulative_version_map,
        "final_best_exp_id": current_best_exp_id,
        "final_best_metrics": ctx.get("current_best_metrics") or {},
        "final_test_metrics": _avg_metrics(optimized_test_exp_id) if optimized_test_exp_id else {},
        "final_graph_id": str(ctx.get("final_graph_id") or ""),
    }


def run_optimization_pipeline(
    exp_id: str,
    *,
    from_step: str = "baseline_test",
    to_step: str = "final_test_report",
    tuning_dataset: str = "",
    test_dataset: str = "",
    max_agent_updates: int = 3,
    progress_cb: Callable[[dict[str, Any]], None] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    start = _step_index(from_step)
    end = _step_index(to_step)
    if end < start:
        raise RuntimeError("to_step must be >= from_step")
    steps = FLOW_STEP_ORDER[start : end + 1]
    last_result: dict[str, Any] = {}
    for step_id in steps:
        last_result = run_optimization_step(
            exp_id,
            step_id,
            tuning_dataset=tuning_dataset,
            test_dataset=test_dataset,
            max_agent_updates=max_agent_updates,
            progress_cb=progress_cb,
            force=force and step_id == from_step,
        )
        if last_result.get("needs_stream"):
            break
    return last_result


def can_run_step(flow_steps: list[dict[str, Any]], step_id: str) -> bool:
    idx = _step_index(step_id)
    if idx == 0:
        return True
    prev = flow_steps[idx - 1] if idx - 1 < len(flow_steps) else None
    if not prev:
        return False
    return str(prev.get("status") or "") == "done"
