from __future__ import annotations

import json
import re
import uuid
import shutil
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from langchain_core.runnables import RunnableConfig

from service.optimize_suggestion_filter import filter_disallowed_modifications
from service.entity.agent import AgentLoader
from service.entity.runner import RunnerLoader
from service.entity.test import TestLoader
from service.meta.agent_version import AgentVersionStore
from service.meta.loader import GraphMetaLoader, MetaLoader
from service.result.loader import (
    ResultLoader,
    build_report_payload_states,
    iter_sample_indices,
)
from utils.graphutils import resolve_report_agent_versions


ROOT = Path(__file__).resolve().parent.parent
MAX_SYSTEM_CHARS = 1200
MAX_HUMAN_CHARS = 1800


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_json_loads(text: str) -> dict | list | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.S | re.I)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass

    l_brace = text.find("{")
    r_brace = text.rfind("}")
    if l_brace >= 0 and r_brace > l_brace:
        try:
            return json.loads(text[l_brace : r_brace + 1])
        except json.JSONDecodeError:
            pass
    return None


def _dedupe_prompt_lines(text: str) -> str:
    lines = [ln.rstrip() for ln in (text or "").replace("\r\n", "\n").split("\n")]
    out: list[str] = []
    seen: set[str] = set()
    for ln in lines:
        key = re.sub(r"\s+", " ", ln.strip().lower())
        if not key:
            if out and out[-1] == "":
                continue
            out.append("")
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(ln.strip())
    # trim surrounding blanks
    while out and out[0] == "":
        out.pop(0)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out)


def _compact_prompt_text(text: str, *, max_chars: int) -> str:
    """
    Compact prompt text while preserving key constraints.
    Strategy:
    1) line de-dup + blank-line cleanup
    2) if still too long, keep important lines first (causation/rules/output/article)
    3) hard truncate with explicit tail marker if needed
    """
    compact = _dedupe_prompt_lines(text)
    if len(compact) <= max_chars:
        return compact

    lines = [ln for ln in compact.split("\n") if ln.strip()]
    scored: list[tuple[int, int, str]] = []
    keywords = (
        "rule",
        "output",
        "must",
        "only",
        "caus",
        "negative",
        "condition",
        "article",
        "{text}",
    )
    for i, ln in enumerate(lines):
        low = ln.lower()
        score = 0
        for kw in keywords:
            if kw in low:
                score += 1
        scored.append((score, i, ln))

    # keep order stable, but prioritize high-value lines first
    chosen_idx: set[int] = set()
    budget = max_chars
    for score, i, ln in sorted(scored, key=lambda x: (-x[0], x[1])):
        cost = len(ln) + 1
        if cost <= budget:
            chosen_idx.add(i)
            budget -= cost
    # rebuild in original order
    rebuilt = "\n".join([lines[i] for i in range(len(lines)) if i in chosen_idx]).strip()
    if len(rebuilt) <= max_chars:
        return rebuilt

    marker = "\n\n[TRIMMED FOR BUDGET]"
    head_budget = max(0, max_chars - len(marker))
    return rebuilt[:head_budget].rstrip() + marker


def _load_rows(runner_id: str, dataset: str) -> list[dict[str, Any]]:
    _fields, rows = TestLoader.load_by_id_file(runner_id, dataset)
    return [dict(r) for r in rows]


def _resolve_dual_datasets(exp_cfg: dict[str, Any]) -> tuple[str, str]:
    """Resolve (tuning_dataset, test_dataset) with legacy fallback."""
    tuning = str(exp_cfg.get("tuning_dataset") or "").strip()
    test = str(exp_cfg.get("test_dataset") or "").strip()
    legacy = str(exp_cfg.get("dataset") or "").strip()
    if not tuning:
        tuning = legacy or test
    if not test:
        test = legacy or tuning
    if not tuning and test:
        tuning = test
    if not test and tuning:
        test = tuning
    return tuning, test


def init_optimization_flow_steps() -> list[dict[str, Any]]:
    return [
        {
            "id": "baseline_test",
            "label": "1. Baseline Test Run",
            "status": "pending",
            "detail": "Run on test dataset",
        },
        {
            "id": "baseline_test_report",
            "label": "2. Baseline Test Report",
            "status": "pending",
            "detail": "Auto-generated after step 1",
        },
        {
            "id": "baseline_tuning",
            "label": "3. Tuning Baseline Run",
            "status": "pending",
        },
        {
            "id": "baseline_tuning_report",
            "label": "4. Tuning Report & Refine",
            "status": "pending",
        },
        {
            "id": "optimize_rounds",
            "label": "5. Optimize Rounds (tuning)",
            "status": "pending",
        },
        {
            "id": "final_test",
            "label": "6. Optimized Test Run",
            "status": "pending",
        },
        {
            "id": "final_test_report",
            "label": "7. Compare Test Reports",
            "status": "pending",
        },
    ]


def _set_flow_step(
    flow_steps: list[dict[str, Any]],
    step_id: str,
    status: str,
    detail: str = "",
) -> None:
    for step in flow_steps:
        if step.get("id") == step_id:
            step["status"] = status
            if detail:
                step["detail"] = detail
            break


def _baseline_test_ready(exp_cfg: dict[str, Any], test_dataset: str) -> bool:
    if str(exp_cfg.get("status") or "").lower() != "completed":
        return False
    exp_id = str(exp_cfg.get("exp_id") or "").strip()
    if not exp_id or not ResultLoader.load(exp_id):
        return False
    legacy = str(exp_cfg.get("dataset") or "").strip()
    _, cfg_test = _resolve_dual_datasets(exp_cfg)
    return legacy == test_dataset or cfg_test == test_dataset


def _baseline_test_report_path(exp_id: str) -> Path:
    return ROOT / "result" / exp_id / "report_baseline_test.md"


def _baseline_report_ready(exp_id: str) -> bool:
    return _baseline_test_report_path(exp_id).is_file()


def generate_baseline_test_report(exp_id: str) -> dict[str, Any]:
    exp_cfg = MetaLoader.load("exps", exp_id) or {}
    exp_cfg["exp_id"] = exp_id
    _, test = _resolve_dual_datasets(exp_cfg)
    if not _baseline_test_ready(exp_cfg, test):
        raise RuntimeError(
            "Complete baseline test on test dataset first (status=completed)."
        )
    report_path = _generate_and_save_report(exp_id, exp_cfg, "report_baseline_test.md")
    return {
        "exp_id": exp_id,
        "report_path": report_path,
        "baseline_test_metrics": _avg_metrics(exp_id),
    }


def _generate_and_save_report(exp_id: str, exp_cfg: dict[str, Any], filename: str = "report.md") -> str:
    payload = _build_report_payload(exp_id, exp_cfg)
    report = _generate_report(payload)
    path = ROOT / "result" / exp_id / filename
    _write_text(path, report)
    return str(path)


def optimization_preflight(exp_id: str) -> dict[str, Any]:
    exp_cfg = MetaLoader.load("exps", exp_id) or {}
    exp_cfg["exp_id"] = exp_id
    tuning, test = _resolve_dual_datasets(exp_cfg)
    flow_steps = init_optimization_flow_steps()
    ready = _baseline_test_ready(exp_cfg, test)
    report_ready = _baseline_report_ready(exp_id)
    if ready:
        _set_flow_step(flow_steps, "baseline_test", "done", f"Completed on {test}")
    if report_ready:
        _set_flow_step(flow_steps, "baseline_test_report", "done", "Baseline test report ready")
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
    }


def _ensure_dataset_for_candidate(
    baseline_runner_id: str, candidate_runner_id: str, datasets: list[str]
) -> None:
    """Copy baseline dataset file to candidate graph test folder when missing."""
    dst_dir = ROOT / "tests" / candidate_runner_id
    copied: set[str] = set()
    for dataset in datasets:
        ds = str(dataset or "").strip()
        if not ds or ds in copied:
            continue
        copied.add(ds)
        src = ROOT / "tests" / baseline_runner_id / ds
        dst = dst_dir / ds
        if dst.exists() or not src.exists():
            continue
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _run_experiment(exp_cfg: dict[str, Any]) -> None:
    _run_experiment_with_progress(exp_cfg, progress_cb=None)


def _run_experiment_with_progress(
    exp_cfg: dict[str, Any],
    progress_cb: Callable[[dict[str, Any]], None] | None = None,
    *,
    progress_base: int = 0,
    progress_span: int = 100,
    meta: dict[str, Any] | None = None,
) -> None:
    runner_id = exp_cfg["runner_id"]
    exp_id = exp_cfg["exp_id"]
    dataset = exp_cfg["dataset"]
    rows = _load_rows(runner_id, dataset)
    runner = RunnerLoader.load(runner_id)
    if runner is None:
        raise RuntimeError(f"Runner not found: {runner_id}")

    total = len(rows)
    meta = dict(meta or {})

    def _emit_sample(completed: int, *, running_idx: int | None = None) -> None:
        if not progress_cb:
            return
        done = min(max(completed, 0), total)
        pct = progress_base + (
            int(done / max(1, total) * progress_span) if total else progress_span
        )
        msg_parts: list[str] = []
        if meta.get("round_index") and meta.get("round_total"):
            msg_parts.append(f"Round {meta['round_index']}/{meta['round_total']}")
        if meta.get("phase"):
            msg_parts.append(str(meta["phase"]))
        if running_idx is not None:
            msg_parts.append(f"Sample {running_idx}/{total}")
        elif done < total:
            msg_parts.append(f"Sample {done + 1}/{total}")
        else:
            msg_parts.append(f"Sample {done}/{total}")
        progress_cb(
            {
                "progress": min(progress_base + progress_span, pct),
                "stage": meta.get("stage", "run_experiment"),
                "message": ": ".join(msg_parts),
                "sample_index": running_idx or done,
                "sample_total": total,
                "completed_samples": done,
                "round_index": meta.get("round_index"),
                "round_total": meta.get("round_total"),
            }
        )

    for idx, row in enumerate(rows, start=1):
        _emit_sample(idx - 1, running_idx=idx)
        config: RunnableConfig = {"configurable": {"thread_id": f"{exp_id}_{idx}"}}
        payload = dict(row)
        if hasattr(runner, "compiled_graph"):
            runner.compiled_graph.invoke(payload, config=config)
        else:
            runner.invoke(payload, config=config)

        # Persist every 10 articles to avoid data loss on interrupt.
        if idx % 10 == 0 or idx == total:
            RunnerLoader.persistence(exp_cfg)

    exp_cfg["status"] = "completed"
    exp_cfg["progress"] = 100
    exp_cfg["samples"] = total
    MetaLoader.dump("exps", exp_id, exp_cfg)
    # Ensure final persistence run covers everything
    RunnerLoader.persistence(exp_cfg)
    _emit_sample(total)


def _load_report_agents(graphs_cfg: dict[str, dict]) -> dict[str, dict]:
    agents: dict[str, dict] = {}
    for graph in graphs_cfg.values():
        GraphMetaLoader.load_agents_by_graph(graph, agents)
    return agents


def _build_report_payload(exp_id: str, exp_cfg: dict[str, Any]) -> dict[str, Any]:
    runner_id = exp_cfg.get("runner_id")
    graphs_cfg: dict[str, dict] = {}
    if runner_id:
        graphs_cfg = GraphMetaLoader.load(runner_id) or {}
    agents_cfg = _load_report_agents(graphs_cfg)
    agent_versions = resolve_report_agent_versions(
        graphs_cfg, agents_cfg, root_graph_id=str(runner_id or "")
    )
    raw_states = ResultLoader.load(exp_id) or {}
    states = build_report_payload_states(raw_states, exp_id=exp_id)
    return {
        "exp_id": exp_id,
        "experiment": exp_cfg,
        "graphs": graphs_cfg,
        "agents": agents_cfg,
        "agent_versions": agent_versions,
        "states": states,
    }


def _generate_report(payload: dict[str, Any]) -> str:
    agent = AgentLoader.load("report_experiment")
    if agent is None:
        raise RuntimeError("Agent 'report_experiment' not found")
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            raw = agent.invoke(
                {"text": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}
            )
            return str(raw.get("text", "")).strip()
        except Exception as ex:
            last_err = ex
            msg = str(ex).lower()
            if attempt >= 2 or ("connection" not in msg and "timeout" not in msg):
                raise
            time.sleep(1.5 * (attempt + 1))
    if last_err:
        raise last_err
    return ""


def _score_report_quality(
    report_text: str,
    *,
    metrics_delta: dict[str, float] | None = None,
    is_candidate: bool = False,
) -> dict[str, Any]:
    text = str(report_text or "")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    headings = [ln for ln in lines if ln.startswith("#")]
    tables = [ln for ln in lines if "|" in ln]
    bullets = [ln for ln in lines if ln.startswith("- ") or ln.startswith("* ")]
    numeric_lines = [ln for ln in lines if re.search(r"\b\d+(\.\d+)?\b", ln)]
    structure_score = 0
    if headings:
        structure_score += 2
    if len(headings) >= 3:
        structure_score += 1
    if tables:
        structure_score += 1
    if bullets:
        structure_score += 1
    if numeric_lines:
        structure_score += 1

    # Effect alignment: candidate report quality must reflect actual metric outcome.
    # Range: 0..4
    effect_score = 2  # neutral baseline
    effect_note = "neutral"
    f1_delta = None
    if metrics_delta and "f1" in metrics_delta:
        try:
            f1_delta = float(metrics_delta["f1"])
        except Exception:
            f1_delta = None
    if is_candidate and f1_delta is not None:
        if f1_delta > 0.01:
            effect_score = 4
            effect_note = "f1 improved clearly"
        elif f1_delta > 0:
            effect_score = 3
            effect_note = "f1 improved slightly"
        elif f1_delta == 0:
            effect_score = 2
            effect_note = "f1 unchanged"
        elif f1_delta >= -0.01:
            effect_score = 1
            effect_note = "f1 degraded slightly"
        else:
            effect_score = 0
            effect_note = "f1 degraded"

    score = structure_score + effect_score
    # Hard guard: if candidate metrics worsen, quality score must be lower.
    if is_candidate and f1_delta is not None and f1_delta < 0:
        score = min(score, structure_score + 1)

    return {
        "score": score,
        "max_score": 10,
        "structure_score": structure_score,
        "structure_max": 6,
        "effect_score": effect_score,
        "effect_max": 4,
        "effect_note": effect_note,
        "f1_delta": f1_delta,
    }


def _avg_metrics(exp_id: str) -> dict[str, float]:
    states = ResultLoader.load(exp_id) or {}
    keys = iter_sample_indices(states)
    if not keys:
        return {}
    totals = {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    n = 0
    for k in keys:
        item = states.get(k) or {}
        m = item.get("metrics") if isinstance(item, dict) else None
        if not isinstance(m, dict):
            continue
        if all(metric in m for metric in ("precision", "recall", "f1")):
            totals["precision"] += float(m["precision"])
            totals["recall"] += float(m["recall"])
            totals["f1"] += float(m["f1"])
            n += 1
    if n == 0:
        return {}
    return {k: v / n for k, v in totals.items()}


def _agent_prompt_excerpts(agents_cfg: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Compact prompt/process excerpts for refiner diffing."""
    out: dict[str, dict[str, str]] = {}
    if not isinstance(agents_cfg, dict):
        return out
    for agent_id, meta in agents_cfg.items():
        if not isinstance(meta, dict):
            continue
        pt = meta.get("prompt_template") or {}
        out[str(agent_id)] = {
            "system": str(pt.get("system") or "")[:800],
            "human": str(pt.get("human") or "")[:1600],
            "process": str(meta.get("process") or "")[:1200],
        }
    return out


def _run_refiner(
    baseline_report: str, baseline_payload: dict[str, Any], max_updates: int
) -> list[dict[str, Any]]:
    agent = AgentLoader.load("agent_refiner")
    if agent is None:
        raise RuntimeError("Agent 'agent_refiner' not found")
    agents_cfg = baseline_payload.get("agents") if isinstance(baseline_payload, dict) else {}
    if not isinstance(agents_cfg, dict):
        agents_cfg = {}
    text = json.dumps(
        {
            "baseline_report": baseline_report,
            "baseline_payload": baseline_payload,
            "agent_prompt_excerpts": _agent_prompt_excerpts(agents_cfg),
            "constraints": {"max_updates": max_updates},
        },
        ensure_ascii=False,
        indent=2,
    )
    raw = agent.invoke({"text": text}).get("plan_json", "")
    parsed = _safe_json_loads(str(raw))
    if isinstance(parsed, dict):
        parsed = parsed.get("modifications", [])
    if not isinstance(parsed, list):
        return []
    mods = [x for x in parsed if isinstance(x, dict)]
    kept, _rejected = filter_disallowed_modifications(mods, agents_cfg=agents_cfg)
    return kept


def _apply_modifications(
    modifications: list[dict[str, Any]],
    *,
    max_updates: int,
    change_note_prefix: str,
) -> tuple[dict[str, str], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    store = AgentVersionStore()
    version_map: dict[str, str] = {}
    originals: dict[str, dict[str, Any]] = {}
    pending: dict[str, dict[str, Any]] = {}
    selected: list[dict[str, Any]] = []
    selected_agents: set[str] = set()

    # select modifications by unique target_agent_id
    for mod in modifications:
        agent_id = str(mod.get("target_agent_id") or "").strip()
        if not agent_id:
            continue
        if agent_id not in selected_agents and len(selected_agents) >= max_updates:
            continue
        meta = pending.get(agent_id) or MetaLoader.load("agents", agent_id)
        if not meta:
            continue
        if agent_id not in originals:
            originals[agent_id] = deepcopy(meta)
            pending[agent_id] = deepcopy(meta)
            selected_agents.add(agent_id)
        selected.append(mod)

    changed_agents: set[str] = set()

    def apply_one(meta: dict[str, Any], mod: dict[str, Any]) -> bool:
        changed = False
        prompt = dict(meta.get("prompt_template") or {})

        append_sys = str(mod.get("prompt_system_append") or "").strip()
        if append_sys:
            old = str(prompt.get("system") or "")
            merged = (old + "\n\n" + append_sys).strip() if old else append_sys
            if len(merged) > MAX_SYSTEM_CHARS:
                # Over budget: force replace via compaction.
                prompt["system"] = _compact_prompt_text(
                    merged, max_chars=MAX_SYSTEM_CHARS
                )
            else:
                prompt["system"] = merged
            changed = True
        replace_sys = str(mod.get("prompt_system_replace") or "").strip()
        if replace_sys:
            prompt["system"] = _compact_prompt_text(
                replace_sys, max_chars=MAX_SYSTEM_CHARS
            )
            changed = True

        append_human = str(mod.get("prompt_human_append") or "").strip()
        if append_human:
            old = str(prompt.get("human") or "")
            merged = (old + "\n\n" + append_human).strip() if old else append_human
            if len(merged) > MAX_HUMAN_CHARS:
                # Over budget: force replace via compaction.
                prompt["human"] = _compact_prompt_text(
                    merged, max_chars=MAX_HUMAN_CHARS
                )
            else:
                prompt["human"] = merged
            changed = True
        replace_human = str(mod.get("prompt_human_replace") or "").strip()
        if replace_human:
            prompt["human"] = _compact_prompt_text(
                replace_human, max_chars=MAX_HUMAN_CHARS
            )
            changed = True

        # Remove specific numbered rules
        sys_remove = mod.get("prompt_system_remove_rules") or []
        if isinstance(sys_remove, list) and sys_remove:
            old_sys = str(prompt.get("system") or "")
            from service.tools.analysis_tools import _remove_numbered_rules
            new_sys = _remove_numbered_rules(old_sys, sys_remove)
            if new_sys != old_sys:
                prompt["system"] = new_sys
                changed = True
        human_remove = mod.get("prompt_human_remove_rules") or []
        if isinstance(human_remove, list) and human_remove:
            old_human = str(prompt.get("human") or "")
            from service.tools.analysis_tools import _remove_numbered_rules
            new_human = _remove_numbered_rules(old_human, human_remove)
            if new_human != old_human:
                prompt["human"] = new_human
                changed = True

        if prompt:
            if "system" in prompt:
                prompt["system"] = _compact_prompt_text(
                    str(prompt.get("system") or ""), max_chars=MAX_SYSTEM_CHARS
                )
            if "human" in prompt:
                prompt["human"] = _compact_prompt_text(
                    str(prompt.get("human") or ""), max_chars=MAX_HUMAN_CHARS
                )
            meta["prompt_template"] = prompt

        # PGM process patch support
        proc_append = str(mod.get("process_append") or "").strip()
        if proc_append:
            old = str(meta.get("process") or "")
            meta["process"] = (old + "\n\n" + proc_append).strip() if old else proc_append
            changed = True
        proc_replace = str(mod.get("process_replace") or "").strip()
        if proc_replace:
            meta["process"] = proc_replace
            changed = True

        set_model = str(mod.get("set_model") or "").strip()
        if set_model:
            meta["model"] = set_model
            changed = True

        add_tools = mod.get("add_tools") or []
        if isinstance(add_tools, list) and add_tools:
            tools = list(meta.get("tools") or [])
            for t in add_tools:
                t = str(t).strip()
                if t and t not in tools:
                    tools.append(t)
                    changed = True
            meta["tools"] = tools

        remove_tools = mod.get("remove_tools") or []
        if isinstance(remove_tools, list) and remove_tools:
            tools = list(meta.get("tools") or [])
            old_len = len(tools)
            rm = {str(t).strip() for t in remove_tools if str(t).strip()}
            tools = [t for t in tools if t not in rm]
            if len(tools) != old_len:
                changed = True
            meta["tools"] = tools

        return changed

    for mod in selected:
        agent_id = str(mod.get("target_agent_id") or "").strip()
        meta = pending.get(agent_id)
        if not meta:
            continue
        if apply_one(meta, mod):
            changed_agents.add(agent_id)

    if not changed_agents:
        return version_map, originals, {}

    # apply modified agent configs first; defer snapshot/version creation until metrics pass
    try:
        for agent_id in changed_agents:
            meta = pending[agent_id]
            MetaLoader.dump("agents", agent_id, meta)
    except Exception as ex:
        # rollback to originals (atomic behavior), do not create rollback snapshots
        for aid in changed_agents:
            origin = originals.get(aid)
            if not origin:
                continue
            MetaLoader.dump("agents", aid, deepcopy(origin))
        raise RuntimeError(f"apply modifications transaction failed: {ex}")

    applied = {aid: deepcopy(pending[aid]) for aid in changed_agents}
    return version_map, originals, applied


def _snapshot_accepted_modifications(
    applied: dict[str, dict[str, Any]],
    modifications: list[dict[str, Any]],
    *,
    max_updates: int,
    change_note_prefix: str,
) -> dict[str, str]:
    """Create version snapshots only for accepted (non-degraded) modifications."""
    if not applied:
        return {}
    store = AgentVersionStore()
    version_map: dict[str, str] = {}
    for agent_id, meta in applied.items():
        note = ""
        for mod in modifications[:max_updates]:
            if str(mod.get("target_agent_id") or "").strip() != agent_id:
                continue
            rationale = str(mod.get("rationale") or "").strip()
            if rationale:
                note = rationale
                break
        snap = store.save_snapshot(
            agent_id,
            meta,
            change_note=f"{change_note_prefix}: {note}"[:300],
            created_by="optimize_loop",
            source="optimize_loop",
        )
        version = snap.get("version")
        if version:
            version_map[agent_id] = version
    return version_map


def _restore_agents_after_negative_delta(
    originals: dict[str, dict[str, Any]], *, reason: str
) -> list[str]:
    """Restore modified agent meta back to originals without new version snapshots."""
    restored: list[str] = []
    for agent_id, original_meta in (originals or {}).items():
        if not isinstance(original_meta, dict):
            continue
        MetaLoader.dump("agents", agent_id, deepcopy(original_meta))
        restored.append(agent_id)
    return restored


def _create_candidate_graph(
    baseline_runner_id: str,
    version_map: dict[str, str],
    candidate_graph_id: str,
    datasets: list[str] | None = None,
) -> str:
    graph = MetaLoader.load("graphs", baseline_runner_id)
    if not graph:
        raise RuntimeError(f"Graph not found: {baseline_runner_id}")
    candidate = deepcopy(graph)
    candidate["name"] = f"{graph.get('name', baseline_runner_id)} [optimized]"
    av = dict(candidate.get("agentVersions") or {})
    av.update(version_map)
    candidate["agentVersions"] = av
    MetaLoader.dump("graphs", candidate_graph_id, candidate)
    if datasets:
        _ensure_dataset_for_candidate(baseline_runner_id, candidate_graph_id, datasets)
    return candidate_graph_id


def _write_text(path: Path | str, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _compare_reports_with_llm(payload: dict[str, Any]) -> str:
    agent = AgentLoader.load("report_comparator")
    if agent is None:
        return ""
    raw = agent.invoke({"text": json.dumps(payload, ensure_ascii=False, indent=2)})
    return str(raw.get("text", "")).strip()


def _build_exp_cfg(
    *,
    exp_id: str,
    runner_id: str,
    dataset: str,
    tuning_dataset: str = "",
    test_dataset: str = "",
    runner_type: str = "graph",
) -> dict[str, Any]:
    tuning = str(tuning_dataset or "").strip() or str(dataset or "").strip()
    test = str(test_dataset or "").strip() or str(dataset or "").strip()
    return {
        "exp_id": exp_id,
        "name": f"{runner_id}_{dataset}_{exp_id}",
        "runner_type": runner_type,
        "runner_id": runner_id,
        "runner_display": runner_id,
        "dataset": dataset,
        "tuning_dataset": tuning,
        "test_dataset": test,
        "samples": 0,
        "status": "running",
        "progress": 0,
        "created_at": datetime.now().isoformat(),
    }


def run_optimize_loop_by_exp(
    exp_id: str,
    *,
    max_agent_updates: int = 3,
    candidate_graph_id: str = "",
    tuning_dataset: str = "",
    test_dataset: str = "",
) -> dict[str, Any]:
    # max_agent_updates is kept for backward compatibility but no longer used as loop control.
    return run_optimize_loop_by_exp_with_progress(
        exp_id,
        max_agent_updates=max_agent_updates,
        candidate_graph_id=candidate_graph_id,
        tuning_dataset=tuning_dataset,
        test_dataset=test_dataset,
        progress_cb=None,
    )


def run_optimize_loop_by_exp_with_progress(
    exp_id: str,
    *,
    max_agent_updates: int = 3,
    candidate_graph_id: str = "",
    tuning_dataset: str = "",
    test_dataset: str = "",
    progress_cb: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    flow_steps = init_optimization_flow_steps()

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

    baseline_cfg = MetaLoader.load("exps", exp_id)
    if not baseline_cfg:
        raise RuntimeError(f"Experiment not found: {exp_id}")
    baseline_cfg["exp_id"] = exp_id
    cfg_tuning, cfg_test = _resolve_dual_datasets(baseline_cfg)
    active_tuning_dataset = str(tuning_dataset or "").strip() or cfg_tuning
    active_test_dataset = str(test_dataset or "").strip() or cfg_test
    if not active_tuning_dataset or not active_test_dataset:
        raise RuntimeError("Optimize requires tuning_dataset and test_dataset (or legacy dataset).")
    baseline_cfg["tuning_dataset"] = active_tuning_dataset
    baseline_cfg["test_dataset"] = active_test_dataset
    if not baseline_cfg.get("dataset"):
        baseline_cfg["dataset"] = active_test_dataset

    if not _baseline_test_ready(baseline_cfg, active_test_dataset):
        raise RuntimeError(
            "Complete baseline test on Configure tab first (test dataset, status=completed), "
            "then start Optimization."
        )

    baseline_test_exp_id = exp_id
    _set_flow_step(flow_steps, "baseline_test", "done", f"Reusing exp {exp_id} on {active_test_dataset}")
    emit(
        5,
        "baseline_test_ready",
        "Reusing completed baseline test run (not re-running test)",
        flow_step="baseline_test",
        flow_status="done",
    )

    emit(
        8,
        "baseline_test_report",
        "Generating baseline test report from test results",
        flow_step="baseline_test_report",
        flow_status="running",
    )
    baseline_test_report_file = _baseline_test_report_path(baseline_test_exp_id)
    if baseline_test_report_file.is_file():
        baseline_test_report_path = str(baseline_test_report_file)
        emit(
            12,
            "baseline_test_report_done",
            "Reusing existing baseline test report",
            flow_step="baseline_test_report",
            flow_status="done",
            flow_detail=baseline_test_report_path,
        )
    else:
        baseline_test_report_path = _generate_and_save_report(
            baseline_test_exp_id, baseline_cfg, "report_baseline_test.md"
        )
        emit(
            12,
            "baseline_test_report_done",
            "Baseline test report ready",
            flow_step="baseline_test_report",
            flow_status="done",
            flow_detail=baseline_test_report_path,
        )

    baseline_tune_exp_id = f"opt_base_tune_{uuid.uuid4().hex[:8]}"
    baseline_tune_cfg = _build_exp_cfg(
        exp_id=baseline_tune_exp_id,
        runner_id=str(baseline_cfg.get("runner_id") or ""),
        dataset=active_tuning_dataset,
        tuning_dataset=active_tuning_dataset,
        test_dataset=active_test_dataset,
        runner_type=str(baseline_cfg.get("runner_type") or "graph"),
    )
    MetaLoader.dump("exps", baseline_tune_exp_id, baseline_tune_cfg)
    emit(
        18,
        "baseline_tuning_run",
        "Running baseline on tuning dataset",
        flow_step="baseline_tuning",
        flow_status="running",
    )
    _run_experiment(baseline_tune_cfg)
    emit(
        22,
        "baseline_tuning_done",
        "Tuning baseline run completed",
        flow_step="baseline_tuning",
        flow_status="done",
    )

    tag = _now_tag()
    emit(
        25,
        "baseline_tuning_report",
        "Generating tuning report for refinement",
        flow_step="baseline_tuning_report",
        flow_status="running",
    )
    baseline_payload = _build_report_payload(baseline_tune_exp_id, baseline_tune_cfg)
    baseline_report = _generate_report(baseline_payload)
    baseline_tuning_report_path = ROOT / "result" / baseline_tune_exp_id / "report_tuning_baseline.md"
    _write_text(baseline_tuning_report_path, baseline_report)
    _write_text(ROOT / "result" / baseline_tune_exp_id / "report.md", baseline_report)

    emit(35, "refine_plan", "Generating agent refinement plan from tuning report")
    raw_modifications = _run_refiner(
        baseline_report,
        baseline_payload,
        max_updates=max(10, max_agent_updates),
    )
    agents_cfg = baseline_payload.get("agents") if isinstance(baseline_payload, dict) else {}
    if not isinstance(agents_cfg, dict):
        agents_cfg = {}
    modifications, filtered_modifications = filter_disallowed_modifications(
        [
            m
            for m in raw_modifications
            if isinstance(m, dict) and str(m.get("target_agent_id") or "").strip()
        ],
        agents_cfg=agents_cfg,
    )
    emit(
        38,
        "baseline_tuning_report_done",
        f"Refinement plan: {len(modifications)} suggestion(s)"
        + (
            f" ({len(filtered_modifications)} filtered)"
            if filtered_modifications
            else ""
        ),
        flow_step="baseline_tuning_report",
        flow_status="done",
    )

    base_runner = str(baseline_cfg.get("runner_id") or "")
    if not base_runner:
        raise RuntimeError("Baseline experiment missing runner_id")

    current_best_exp_id = baseline_tune_exp_id
    current_best_report = baseline_report
    current_best_metrics = _avg_metrics(baseline_tune_exp_id)
    current_best_report_score = _score_report_quality(
        baseline_report, metrics_delta=None, is_candidate=False
    )
    cumulative_version_map: dict[str, str] = {}
    rounds: list[dict[str, Any]] = []

    total_rounds = len(modifications)
    if total_rounds == 0:
        emit(
            40,
            "no_suggestion",
            "No agent suggestions found in tuning report",
            flow_step="optimize_rounds",
            flow_status="done",
            flow_detail="No suggestions",
        )
    else:
        _set_flow_step(flow_steps, "optimize_rounds", "running", f"0 / {total_rounds} rounds")
        emit(
            40,
            "optimize_rounds_start",
            f"Starting {total_rounds} optimize round(s) on tuning dataset",
            flow_step="optimize_rounds",
            flow_status="running",
        )

    for idx, mod in enumerate(modifications, start=1):
        target_agent = str(mod.get("target_agent_id") or "").strip()
        prev_best_exp_id = current_best_exp_id
        prev_best_report = current_best_report
        prev_best_metrics = dict(current_best_metrics)
        prev_best_report_score = dict(current_best_report_score)
        emit(
            40 + int((idx - 1) * 50 / max(1, total_rounds)),
            "round_apply",
            f"Round {idx}/{total_rounds}: applying suggestion for {target_agent}",
            flow_step="optimize_rounds",
            flow_status="running",
            flow_detail=f"Round {idx}/{total_rounds}: {target_agent}",
        )
        _vmap, originals, applied = _apply_modifications(
            [mod],
            max_updates=1,
            change_note_prefix=f"opt_loop {tag} r{idx}",
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
            dataset=active_tuning_dataset,
            tuning_dataset=active_tuning_dataset,
            test_dataset=active_test_dataset,
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
                    applied,
                    [mod],
                    max_updates=1,
                    change_note_prefix=f"opt_loop {tag} r{idx}",
                )
                cumulative_version_map.update(version_map)
                if version_map:
                    try:
                        round_graph_id = f"{base_runner}_opt_{tag}_r{idx}"
                        display_graph_id = _create_candidate_graph(
                            base_runner,
                            cumulative_version_map,
                            round_graph_id,
                            datasets=[active_tuning_dataset, active_test_dataset],
                        )
                        pinned_exp_id = f"opt_pinned_{tag}_r{idx}_{uuid.uuid4().hex[:8]}"
                        pinned_cfg = _build_exp_cfg(
                            exp_id=pinned_exp_id,
                            runner_id=display_graph_id,
                            dataset=active_tuning_dataset,
                            tuning_dataset=active_tuning_dataset,
                            test_dataset=active_test_dataset,
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
                originals,
                reason=f"round failed: {round_ex}",
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
            emit(
                40 + int(idx * 50 / max(1, total_rounds)),
                "round_failed",
                f"Round {idx}/{total_rounds} skipped: {round_ex}",
                flow_step="optimize_rounds",
                flow_status="running",
                flow_detail=f"Round {idx} failed — continuing",
            )
            continue

    if total_rounds > 0:
        accepted_total = sum(1 for r in rounds if r.get("accepted"))
        emit(
            92,
            "optimize_rounds_done",
            f"Optimize rounds finished ({accepted_total} accepted)",
            flow_step="optimize_rounds",
            flow_status="done",
            flow_detail=f"{accepted_total} accepted of {total_rounds}",
        )

    final_graph_id = ""
    optimized_test_exp_id = ""
    optimized_test_report_path = ""
    if cumulative_version_map:
        cid = candidate_graph_id or f"{base_runner}_opt_{tag}"
        emit(96, "candidate_graph", "Creating cumulative optimized graph")
        final_graph_id = _create_candidate_graph(
            base_runner,
            cumulative_version_map,
            cid,
            datasets=[active_tuning_dataset, active_test_dataset],
        )
        try:
            final_exp_id = f"opt_best_{tag}_{uuid.uuid4().hex[:8]}"
            final_cfg = _build_exp_cfg(
                exp_id=final_exp_id,
                runner_id=final_graph_id,
                dataset=active_test_dataset,
                tuning_dataset=active_tuning_dataset,
                test_dataset=active_test_dataset,
                runner_type=str(baseline_cfg.get("runner_type") or "graph"),
            )
            MetaLoader.dump("exps", final_exp_id, final_cfg)
            emit(
                94,
                "final_test_run",
                "Running optimized workflow on test dataset",
                flow_step="final_test",
                flow_status="running",
            )
            _run_experiment(final_cfg)
            optimized_test_exp_id = final_exp_id
            emit(
                96,
                "final_test_done",
                "Optimized test run completed",
                flow_step="final_test",
                flow_status="done",
            )
            emit(
                98,
                "final_test_report",
                "Generating optimized test report",
                flow_step="final_test_report",
                flow_status="running",
            )
            optimized_test_report_path = _generate_and_save_report(
                final_exp_id, final_cfg, "report_optimized_test.md"
            )
            final_report = Path(optimized_test_report_path).read_text(encoding="utf-8")
            _write_text(ROOT / "result" / final_exp_id / "report.md", final_report)
            current_best_exp_id = final_exp_id
            current_best_metrics = _avg_metrics(final_exp_id) or dict(current_best_metrics)
            current_best_report = final_report
            current_best_report_score = _score_report_quality(
                final_report, metrics_delta=None, is_candidate=True
            )
            emit(
                99,
                "final_test_report_done",
                "Baseline vs optimized test reports ready",
                flow_step="final_test_report",
                flow_status="done",
            )
        except Exception:
            pass
    else:
        _set_flow_step(flow_steps, "final_test", "skipped", "No accepted agent changes")
        _set_flow_step(flow_steps, "final_test_report", "skipped", "No optimized test report")

    summary = {
        "source_exp_id": exp_id,
        "baseline_exp_id": baseline_test_exp_id,
        "baseline_tuning_exp_id": baseline_tune_exp_id,
        "baseline_runner_id": base_runner,
        "tuning_dataset": active_tuning_dataset,
        "test_dataset": active_test_dataset,
        "baseline_test_metrics": _avg_metrics(baseline_test_exp_id),
        "baseline_test_report_path": baseline_test_report_path,
        "baseline_tuning_report_path": str(baseline_tuning_report_path),
        "optimized_test_exp_id": optimized_test_exp_id,
        "optimized_test_report_path": optimized_test_report_path,
        "flow_steps": flow_steps,
        "suggestion_count": total_rounds,
        "rounds": rounds,
        "modifications": modifications,
        "filtered_modifications": filtered_modifications,
        "accepted_version_map": cumulative_version_map,
        "final_best_exp_id": current_best_exp_id,
        "final_best_metrics": current_best_metrics,
        "final_test_metrics": _avg_metrics(current_best_exp_id),
        "final_best_report_score": current_best_report_score,
        "final_graph_id": final_graph_id,
    }
    compare_path = ROOT / "result" / f"opt_compare_{tag}.json"
    _write_text(compare_path, json.dumps(summary, ensure_ascii=False, indent=2))
    summary["compare_path"] = str(compare_path)
    emit(100, "done", "Optimization completed", flow_step="final_test_report", flow_status="done")
    return summary
