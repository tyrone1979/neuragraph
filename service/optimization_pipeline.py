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
    _micro_metrics,
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
    _load_rows,
    _run_experiment,
    _run_experiment_with_progress,
    _run_refiner,
    _score_report_quality,
    _set_flow_step,
    _snapshot_accepted_modifications,
    _write_text,
    generate_baseline_test_report,
    init_optimization_flow_steps,
)
from service.meta.loader import MetaLoader
from service.meta.agent_version import AgentVersionStore
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


def _exp_id_of(meta: dict[str, Any]) -> str:
    return str(meta.get("exp_id") or meta.get("id") or "").strip()


def _linked_tuning_experiments(
    runner_id: str, tuning_dataset: str
) -> tuple[str, list[str]]:
    """Find latest completed opt_base_tune_* and opt_cand_* for the same runner/tuning split."""
    tune_id = ""
    tune_ts = ""
    cands: list[str] = []
    for meta in MetaLoader.loads("exps") or []:
        eid = _exp_id_of(meta)
        if not eid or str(meta.get("runner_id") or "") != runner_id:
            continue
        ds = str(meta.get("tuning_dataset") or meta.get("dataset") or "").strip()
        if ds != tuning_dataset:
            continue
        if str(meta.get("status") or "").lower() != "completed":
            continue
        created = str(meta.get("created_at") or meta.get("updated_at") or "")
        if eid.startswith("opt_base_tune_"):
            if not tune_id or created >= tune_ts:
                tune_id = eid
                tune_ts = created
        elif eid.startswith("opt_cand_"):
            cands.append(eid)
    return tune_id, cands


def _candidates_after_tune(tune_id: str, candidate_ids: list[str]) -> list[str]:
    """Keep candidates run after the tuning baseline (same optimization session)."""
    if not tune_id or not candidate_ids:
        return candidate_ids
    tune_meta = MetaLoader.load("exps", tune_id) or {}
    tune_ts = str(tune_meta.get("created_at") or tune_meta.get("updated_at") or "")
    if not tune_ts:
        return candidate_ids
    scoped: list[str] = []
    for cid in candidate_ids:
        meta = MetaLoader.load("exps", cid) or {}
        created = str(meta.get("created_at") or meta.get("updated_at") or "")
        if created >= tune_ts:
            scoped.append(cid)
    return scoped or candidate_ids


def _needs_opt_context_recovery(ctx: dict[str, Any]) -> bool:
    if not ctx.get("baseline_tune_exp_id"):
        return True
    if ctx.get("optimize_rounds_done"):
        return False
    return not ctx.get("rounds")


def _best_candidate_for_tuning(tune_id: str, candidate_ids: list[str]) -> str:
    if not tune_id or not candidate_ids:
        return ""
    candidate_ids = _candidates_after_tune(tune_id, candidate_ids)
    baseline = _avg_metrics(tune_id)
    if not baseline:
        return candidate_ids[0]
    best_id = ""
    best_delta = -999.0
    for cid in candidate_ids:
        metrics = _avg_metrics(cid)
        if not metrics:
            continue
        delta = float(metrics.get("f1") or 0) - float(baseline.get("f1") or 0)
        if delta > best_delta:
            best_delta = delta
            best_id = cid
    return best_id or candidate_ids[0]


def _needs_version_backfill(ctx: dict[str, Any]) -> bool:
    if not ctx.get("rounds"):
        return False
    if ctx.get("cumulative_version_map"):
        return False
    return any(r.get("accepted") for r in (ctx.get("rounds") or []) if isinstance(r, dict))


def _infer_accepted_version_map(
    tune_exp_id: str,
    candidate_exp_id: str,
    target_agent_ids: list[str],
) -> dict[str, str]:
    """Infer accepted agent versions when orphan candidate runs lack snapshots."""
    tune_meta = MetaLoader.load("exps", tune_exp_id) or {}
    cand_meta = MetaLoader.load("exps", candidate_exp_id) or {}
    tune_ts = str(tune_meta.get("updated_at") or tune_meta.get("created_at") or "")
    cand_ts = str(cand_meta.get("updated_at") or cand_meta.get("created_at") or "")
    store = AgentVersionStore()
    accepted: dict[str, str] = {}
    for agent_id in target_agent_ids:
        agent_id = str(agent_id or "").strip()
        if not agent_id:
            continue
        baseline_ver = store.version_at_time(agent_id, tune_ts)
        baseline_hash = ""
        if baseline_ver:
            baseline_payload = store.load_version(agent_id, baseline_ver) or {}
            baseline_hash = str(baseline_payload.get("content_hash") or "")

        post_run = [
            v
            for v in store.list_versions(agent_id)
            if cand_ts and str(v.get("created_at") or "") >= cand_ts
            and str(v.get("version") or "") != baseline_ver
            and str(v.get("content_hash") or "") != baseline_hash
        ]
        if post_run:
            post_run.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            accepted[agent_id] = str(post_run[0].get("version") or "")
            continue

        current_ver = store.find_version_by_content(agent_id, MetaLoader.load("agents", agent_id) or {})
        if current_ver and current_ver != baseline_ver:
            accepted[agent_id] = current_ver
    return accepted


def _backfill_accepted_versions(ctx: dict[str, Any]) -> dict[str, Any]:
    tune_id = str(ctx.get("baseline_tune_exp_id") or "")
    if not tune_id:
        return ctx
    rounds = list(ctx.get("rounds") or [])
    target_agents = [
        str(r.get("target_agent_id") or "").strip()
        for r in rounds
        if isinstance(r, dict) and r.get("accepted") and r.get("target_agent_id")
    ]
    if not target_agents:
        return ctx
    cand_id = str(ctx.get("current_best_exp_id") or "")
    for r in reversed(rounds):
        if not isinstance(r, dict) or not r.get("accepted"):
            continue
        eid = str(r.get("display_exp_id") or r.get("candidate_exp_id") or "")
        if eid:
            cand_id = eid
            break
    if not cand_id or cand_id == tune_id:
        return ctx
    version_map = _infer_accepted_version_map(tune_id, cand_id, target_agents)
    if not version_map:
        return ctx
    ctx = {**ctx, "cumulative_version_map": version_map}
    updated_rounds: list[dict[str, Any]] = []
    for r in rounds:
        if not isinstance(r, dict):
            updated_rounds.append(r)
            continue
        row = dict(r)
        if row.get("accepted"):
            agent_id = str(row.get("target_agent_id") or "")
            if agent_id in version_map:
                row["version_map"] = {agent_id: version_map[agent_id]}
        updated_rounds.append(row)
    ctx["rounds"] = updated_rounds
    return ctx


def _recover_opt_context(
    parent_exp_id: str,
    exp_cfg: dict[str, Any],
    tuning_dataset: str,
) -> dict[str, Any]:
    """Link orphan tuning/candidate runs to a parent wizard experiment."""
    ctx = load_opt_context(parent_exp_id)
    if ctx.get("baseline_tune_exp_id") and ctx.get("rounds") and ctx.get("cumulative_version_map"):
        return ctx
    if ctx.get("baseline_tune_exp_id") and ctx.get("rounds"):
        ctx = _backfill_accepted_versions(ctx)
        save_opt_context(parent_exp_id, ctx)
        return ctx
    runner_id = str(exp_cfg.get("runner_id") or "")
    tune_id, cand_ids = _linked_tuning_experiments(runner_id, tuning_dataset)
    if not tune_id:
        return ctx
    cand_id = str(ctx.get("current_best_exp_id") or "")
    if cand_id not in cand_ids:
        cand_id = _best_candidate_for_tuning(tune_id, cand_ids)
    tune_metrics = _avg_metrics(tune_id)
    report_path = ROOT / "result" / tune_id / "report_tuning_baseline.md"
    ctx = {
        **ctx,
        "baseline_tune_exp_id": tune_id,
        "baseline_tuning_report_path": str(report_path) if report_path.is_file() else "",
        "current_best_exp_id": cand_id or tune_id,
        "current_best_metrics": _avg_metrics(cand_id) if cand_id else tune_metrics,
        "optimize_rounds_done": bool(cand_id and cand_id != tune_id),
    }
    if cand_id and cand_id != tune_id:
        cand_metrics = _avg_metrics(cand_id)
        delta = {
            k: float(cand_metrics.get(k) or 0) - float(tune_metrics.get(k) or 0)
            for k in ("precision", "recall", "f1")
            if k in tune_metrics and k in cand_metrics
        }
        accepted = delta.get("f1", 0) > 0
        target_agent = "relation_verify_llm"
        for mod in ctx.get("modifications") or []:
            if isinstance(mod, dict) and str(mod.get("target_agent_id") or "").strip():
                target_agent = str(mod.get("target_agent_id") or target_agent)
                break
        version_map: dict[str, str] = {}
        if accepted:
            version_map = _infer_accepted_version_map(tune_id, cand_id, [target_agent])
        ctx["rounds"] = [
            {
                "round": 1,
                "target_agent_id": target_agent,
                "candidate_exp_id": cand_id,
                "display_exp_id": cand_id,
                "baseline_metrics": tune_metrics,
                "candidate_metrics": cand_metrics,
                "metrics_delta": delta,
                "accepted": accepted,
                "reason": "f1 improved" if accepted else "f1 did not improve",
                "version_map": version_map,
            }
        ]
        if accepted and version_map:
            ctx["cumulative_version_map"] = dict(version_map)
    else:
        ctx.setdefault("rounds", [])
    save_opt_context(parent_exp_id, ctx)
    return ctx


def _attach_flow_exp_links(flow_steps: list[dict[str, Any]], ctx: dict[str, Any]) -> None:
    tune_id = str(ctx.get("baseline_tune_exp_id") or "")
    for step in flow_steps:
        links: list[dict[str, str]] = []
        if step.get("id") == "baseline_tuning" and tune_id:
            links.append({"label": "Tuning baseline", "exp_id": tune_id})
        elif step.get("id") == "baseline_tuning_report" and tune_id:
            links.append({"label": "Tuning report", "exp_id": tune_id})
        elif step.get("id") == "optimize_rounds":
            for r in ctx.get("rounds") or []:
                eid = str(r.get("display_exp_id") or r.get("candidate_exp_id") or "")
                if not eid:
                    continue
                rnd = r.get("round")
                agent = str(r.get("target_agent_id") or "")
                links.append(
                    {
                        "label": f"R{rnd} {agent}".strip(),
                        "exp_id": eid,
                    }
                )
            best = str(ctx.get("current_best_exp_id") or "")
            if best and best != tune_id and not any(x.get("exp_id") == best for x in links):
                links.insert(0, {"label": "Optimized best", "exp_id": best})
        if links:
            step["exp_links"] = links


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
    if _needs_opt_context_recovery(ctx):
        ctx = _recover_opt_context(exp_id, exp_cfg, tuning)
    elif _needs_version_backfill(ctx):
        ctx = _backfill_accepted_versions(ctx)
        save_opt_context(exp_id, ctx)
    tune_id = str(ctx.get("baseline_tune_exp_id") or "")
    if tune_id:
        tune_cfg = MetaLoader.load("exps", tune_id) or {}
        if str(tune_cfg.get("status") or "").lower() == "completed":
            _set_flow_step(flow_steps, "baseline_tuning", "done", f"Tuning baseline on {tuning}")
        report_path = ctx.get("baseline_tuning_report_path") or str(
            ROOT / "result" / tune_id / "report_tuning_baseline.md"
        )
        if Path(str(report_path)).is_file() or ctx.get("modifications") is not None:
            mod_count = len(ctx.get("modifications") or [])
            detail = f"{mod_count} suggestion(s)" if mod_count else "Tuning report ready"
            _set_flow_step(flow_steps, "baseline_tuning_report", "done", detail)
    rounds = ctx.get("rounds") or []
    if rounds:
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
    _attach_flow_exp_links(flow_steps, ctx)
    return flow_steps


def optimization_flow_state(exp_id: str) -> dict[str, Any]:
    exp_cfg = MetaLoader.load("exps", exp_id) or {}
    exp_cfg["exp_id"] = exp_id
    tuning, test = _resolve_dual_datasets(exp_cfg)
    flow_steps = _flow_from_context(exp_id, exp_cfg, tuning, test)
    ready = _baseline_test_ready(exp_cfg, test)
    report_ready = _baseline_report_ready(exp_id)
    ctx = load_opt_context(exp_id)
    if _needs_opt_context_recovery(ctx):
        ctx = _recover_opt_context(exp_id, exp_cfg, tuning)
    elif _needs_version_backfill(ctx):
        ctx = _backfill_accepted_versions(ctx)
        save_opt_context(exp_id, ctx)
    optimization_summary = None
    if ctx.get("optimize_rounds_done") or ctx.get("rounds"):
        optimization_summary = _build_summary(exp_id, exp_cfg, tuning, test, ctx, flow_steps)
    tune_id = str(ctx.get("baseline_tune_exp_id") or "")
    return {
        "exp_id": exp_id,
        "baseline_test_ready": ready,
        "baseline_report_ready": report_ready,
        "awaiting_optimization_confirm": ready and report_ready,
        "status": str(exp_cfg.get("status") or ""),
        "tuning_dataset": tuning,
        "test_dataset": test,
        "baseline_test_metrics": _avg_metrics(exp_id) if ready else {},
        "baseline_test_micro_metrics": _micro_metrics(exp_id) if ready else {},
        "baseline_tuning_exp_id": tune_id,
        "baseline_tuning_metrics": _avg_metrics(tune_id) if tune_id else {},
        "flow_steps": flow_steps,
        "context": ctx,
        "optimization_summary": optimization_summary,
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
        **extra: Any,
    ) -> None:
        if flow_step and flow_status:
            _set_flow_step(flow_steps, flow_step, flow_status, flow_detail or message)
        if progress_cb:
            progress_cb(
                {
                    "progress": progress,
                    "stage": stage,
                    "message": message,
                    "flow_step": flow_step,
                    "flow_status": flow_status,
                    "flow_detail": flow_detail or message,
                    "flow_steps": [dict(s) for s in flow_steps],
                    **extra,
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
        ctx["baseline_tune_exp_id"] = tune_id
        ctx["tag"] = ctx.get("tag") or _now_tag()
        save_opt_context(exp_id, ctx)
        _set_flow_step(flow_steps, "baseline_tuning", "running", f"Streaming {tune_id}")
        emit(
            0,
            "baseline_tuning",
            "Ready to stream tuning baseline",
            flow_step="baseline_tuning",
            flow_status="running",
            flow_detail=f"Streaming {tune_id}",
        )
        return {
            "step_id": step_id,
            "needs_stream": True,
            "stream_exp_id": tune_id,
            "flow_steps": flow_steps,
            "baseline_tune_exp_id": tune_id,
        }

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
        agents_cfg = baseline_payload.get("agents") if isinstance(baseline_payload, dict) else {}
        if not isinstance(agents_cfg, dict):
            agents_cfg = {}
        modifications, filtered_modifications = filter_disallowed_modifications(
            [m for m in raw_modifications if isinstance(m, dict) and str(m.get("target_agent_id") or "").strip()],
            agents_cfg=agents_cfg,
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

        samples_per_run = max(1, len(_load_rows(base_runner, active_tuning)))
        completed_units = 0.0
        total_units = float(max(1, total_rounds) * samples_per_run)

        def _optimize_progress_emit(
            units_done: float,
            message: str,
            *,
            flow_detail: str = "",
            sample_index: int | None = None,
            sample_total: int | None = None,
            round_index: int | None = None,
        ) -> None:
            pct = 5 + int(min(1.0, units_done / max(1.0, total_units)) * 90)
            emit(
                pct,
                "optimize_rounds",
                message,
                flow_step="optimize_rounds",
                flow_status="running",
                flow_detail=flow_detail or message,
                sample_index=sample_index,
                sample_total=sample_total,
                round_index=round_index,
                round_total=total_rounds,
            )

        def _run_round_experiment(exp_cfg: dict[str, Any], round_idx: int, phase: str) -> None:
            nonlocal completed_units, total_units

            def sample_cb(evt: dict[str, Any]) -> None:
                sample_done = float(evt.get("completed_samples") or 0)
                units = completed_units + sample_done
                _optimize_progress_emit(
                    units,
                    evt.get("message") or f"Round {round_idx}/{total_rounds}: {phase}",
                    flow_detail=f"Round {round_idx}/{total_rounds} · {phase}",
                    sample_index=evt.get("sample_index"),
                    sample_total=evt.get("sample_total"),
                    round_index=round_idx,
                )

            _run_experiment_with_progress(
                exp_cfg,
                progress_cb=sample_cb,
                meta={
                    "round_index": round_idx,
                    "round_total": total_rounds,
                    "phase": phase,
                    "stage": "optimize_rounds",
                },
            )
            completed_units += float(samples_per_run)

        for idx, mod in enumerate(modifications, start=1):
            if idx < start_idx:
                continue
            target_agent = str(mod.get("target_agent_id") or "").strip()
            prev_best_exp_id = current_best_exp_id
            prev_best_report = current_best_report
            prev_best_metrics = dict(current_best_metrics)
            prev_best_report_score = dict(current_best_report_score)
            _optimize_progress_emit(
                completed_units,
                f"Round {idx}/{total_rounds}: {target_agent}",
                flow_detail=f"Round {idx}/{total_rounds}",
                round_index=idx,
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
                _run_round_experiment(candidate_cfg, idx, "candidate")
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
                            total_units += float(samples_per_run)
                            _run_round_experiment(pinned_cfg, idx, "pinned verify")
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
        summary = _build_summary(exp_id, baseline_cfg, active_tuning, active_test, ctx, flow_steps)
        emit(
            100,
            "optimize_rounds_done",
            detail,
            flow_step="optimize_rounds",
            flow_status="done",
            flow_detail=detail,
            summary=summary,
        )
        return {
            "step_id": step_id,
            "flow_steps": flow_steps,
            "rounds": rounds,
            "accepted_total": accepted_total,
            "summary": summary,
        }

    if step_id == "final_test":
        cumulative_version_map = dict(ctx.get("cumulative_version_map") or {})
        if not cumulative_version_map:
            _set_flow_step(flow_steps, "final_test", "skipped", "No accepted agent changes")
            _set_flow_step(flow_steps, "final_test_report", "skipped", "No optimized test report")
            ctx["optimized_test_exp_id"] = ""
            save_opt_context(exp_id, ctx)
            return {"step_id": step_id, "flow_steps": flow_steps, "skipped": True}
        if force:
            ctx.pop("optimized_test_exp_id", None)
            ctx.pop("optimized_test_report_path", None)
            ctx.pop("final_graph_id", None)
            save_opt_context(exp_id, ctx)
        final_exp_id = str(ctx.get("optimized_test_exp_id") or "")
        if final_exp_id and not force:
            final_cfg = MetaLoader.load("exps", final_exp_id) or {}
            final_status = str(final_cfg.get("status") or "").lower()
            if final_status == "completed":
                _set_flow_step(flow_steps, "final_test", "done", f"Completed {final_exp_id}")
                return {
                    "step_id": step_id,
                    "flow_steps": flow_steps,
                    "optimized_test_exp_id": final_exp_id,
                }
            _set_flow_step(flow_steps, "final_test", "running", f"Streaming {final_exp_id}")
            emit(
                0,
                "final_test",
                "Ready to stream optimized test",
                flow_step="final_test",
                flow_status="running",
                flow_detail=f"Streaming {final_exp_id}",
            )
            return {
                "step_id": step_id,
                "needs_stream": True,
                "stream_exp_id": final_exp_id,
                "flow_steps": flow_steps,
                "optimized_test_exp_id": final_exp_id,
            }
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
        ctx["final_graph_id"] = final_graph_id
        ctx["optimized_test_exp_id"] = final_exp_id
        save_opt_context(exp_id, ctx)
        _set_flow_step(flow_steps, "final_test", "running", f"Streaming {final_exp_id}")
        emit(
            0,
            "final_test",
            "Ready to stream optimized test",
            flow_step="final_test",
            flow_status="running",
            flow_detail=f"Streaming {final_exp_id}",
        )
        return {
            "step_id": step_id,
            "needs_stream": True,
            "stream_exp_id": final_exp_id,
            "flow_steps": flow_steps,
            "optimized_test_exp_id": final_exp_id,
        }

    if step_id == "final_test_report":
        final_exp_id = str(ctx.get("optimized_test_exp_id") or "")
        if not final_exp_id:
            _set_flow_step(flow_steps, "final_test_report", "skipped", "No optimized test run to report")
            return {"step_id": step_id, "flow_steps": flow_steps, "skipped": True}
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
        "baseline_test_micro_metrics": _micro_metrics(exp_id),
        "baseline_tuning_metrics": _avg_metrics(tune_id) if tune_id else {},
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
        "final_test_micro_metrics": _micro_metrics(optimized_test_exp_id) if optimized_test_exp_id else {},
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
