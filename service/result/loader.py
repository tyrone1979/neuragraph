#service/result/loader.py
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict

from logging import getLogger

logger = getLogger(__name__)

# Above this count, reports use charts (not per-sample markdown tables); full text lives under samples/.
REPORT_CHART_SAMPLE_THRESHOLD = 20
# FN/FP-focused exemplars for report (targeted F1 improvement, not lowest-F1 articles).
REPORT_EXEMPLAR_TOP_FP = 10
REPORT_EXEMPLAR_TOP_FN = 10
REPORT_EXEMPLAR_MAX = 20
SAMPLES_SUBDIR = "samples"


def _get_path(name: str) -> Path:
    path = Path(__file__).resolve().parent.parent.parent / "result" / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def iter_sample_indices(results: Dict[str, Any]) -> list[str]:
    """Numeric sample keys in states.json ('1', '2', ...)."""
    return sorted((k for k in results if str(k).isdigit()), key=lambda k: int(k))


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def per_sample_metrics_list(states: Dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sid in iter_sample_indices(states):
        item = states.get(sid) or {}
        metrics = item.get("metrics") if isinstance(item, dict) else {}
        if not isinstance(metrics, dict):
            continue
        rows.append(
            {
                "sample_id": int(sid),
                "precision": _safe_float(metrics.get("precision")),
                "recall": _safe_float(metrics.get("recall")),
                "f1": _safe_float(metrics.get("f1")),
                "tp": int(_safe_float(metrics.get("tp"))),
                "fp": int(_safe_float(metrics.get("fp"))),
                "fn": int(_safe_float(metrics.get("fn"))),
                "rel_tp": int(_safe_float(metrics.get("rel_tp"))),
                "rel_fp": int(_safe_float(metrics.get("rel_fp"))),
                "rel_fn": int(_safe_float(metrics.get("rel_fn"))),
            }
        )
    return rows


def _error_counts_from_row(row: dict[str, Any]) -> tuple[int, int, int]:
    """Per-article tp/fp/fn (entity metrics, or rel_* when present)."""
    tp = int(row.get("rel_tp") or row.get("tp") or 0)
    fp = int(row.get("rel_fp") or row.get("fp") or 0)
    fn = int(row.get("rel_fn") or row.get("fn") or 0)
    return tp, fp, fn


def enrich_sample_error_row(row: dict[str, Any]) -> dict[str, Any]:
    tp, fp, fn = _error_counts_from_row(row)
    out = dict(row)
    out["tp"] = tp
    out["fp"] = fp
    out["fn"] = fn
    out["error_impact"] = fp + fn
    return out


def select_fp_fn_exemplars(
    rows: list[dict[str, Any]],
    *,
    top_fp: int = REPORT_EXEMPLAR_TOP_FP,
    top_fn: int = REPORT_EXEMPLAR_TOP_FN,
    max_total: int = REPORT_EXEMPLAR_MAX,
) -> dict[str, Any]:
    """
    Pick articles with the largest per-article FP and FN counts (micro-F1 levers).
    Returns ranked lists plus ordered unique sample_id strings for examples_detail.
    """
    enriched = [enrich_sample_error_row(r) for r in rows if r.get("sample_id") is not None]
    if not enriched:
        return {"high_fp": [], "high_fn": [], "sample_ids": [], "reasons": {}}

    reasons: dict[str, list[str]] = {}
    high_fp: list[dict[str, Any]] = []
    high_fn: list[dict[str, Any]] = []

    def _tag(sid: str, reason: str) -> None:
        if reason not in reasons.setdefault(sid, []):
            reasons[sid].append(reason)

    for row in sorted(enriched, key=lambda r: (r["fp"], r["error_impact"]), reverse=True):
        if row["fp"] <= 0 or len(high_fp) >= top_fp:
            break
        sid = str(row["sample_id"])
        _tag(sid, "top_fp")
        high_fp.append({**row, "selection_reasons": list(reasons[sid])})

    fn_slots = 0
    for row in sorted(enriched, key=lambda r: (r["fn"], r["error_impact"]), reverse=True):
        if row["fn"] <= 0 or fn_slots >= top_fn:
            break
        sid = str(row["sample_id"])
        _tag(sid, "top_fn")
        high_fn.append({**row, "selection_reasons": list(reasons[sid])})
        fn_slots += 1

    order: list[str] = []
    for row in high_fp:
        sid = str(row["sample_id"])
        if sid not in order:
            order.append(sid)
    for row in high_fn:
        sid = str(row["sample_id"])
        if sid not in order:
            order.append(sid)

    if len(order) < max_total:
        for row in sorted(enriched, key=lambda r: r["error_impact"], reverse=True):
            if row["error_impact"] <= 0:
                break
            sid = str(row["sample_id"])
            if sid in order:
                continue
            _tag(sid, "top_error_impact")
            order.append(sid)
            if len(order) >= max_total:
                break

    for bucket in (high_fp, high_fn):
        for i, row in enumerate(bucket):
            sid = str(row["sample_id"])
            bucket[i] = {**row, "selection_reasons": list(reasons.get(sid, []))}

    return {
        "high_fp": high_fp,
        "high_fn": high_fn,
        "sample_ids": order[:max_total],
        "reasons": reasons,
    }


def summarize_experiment_metrics(states: Dict[str, Any]) -> dict[str, Any]:
    """Aggregate micro/macro P/R/F1 from per-sample metrics in states."""
    rows = per_sample_metrics_list(states)
    if not rows:
        return {"sample_count": 0}

    micro_tp = micro_fp = micro_fn = 0
    macro_ps: list[float] = []
    macro_rs: list[float] = []
    macro_fs: list[float] = []
    f1_vals: list[float] = []

    for row in rows:
        tp = row.get("rel_tp") or row.get("tp") or 0
        fp = row.get("rel_fp") or row.get("fp") or 0
        fn = row.get("rel_fn") or row.get("fn") or 0
        if tp + fp + fn:
            micro_tp += tp
            micro_fp += fp
            micro_fn += fn
        p, r, f1 = row["precision"], row["recall"], row["f1"]
        macro_ps.append(p)
        macro_rs.append(r)
        macro_fs.append(f1)
        f1_vals.append(f1)

    def _prf(tp: int, fp: int, fn: int) -> dict[str, float]:
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        return {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }

    micro = _prf(micro_tp, micro_fp, micro_fn) if micro_tp + micro_fp + micro_fn else None
    macro = {
        "precision": round(sum(macro_ps) / len(macro_ps), 4),
        "recall": round(sum(macro_rs) / len(macro_rs), 4),
        "f1": round(sum(macro_fs) / len(macro_fs), 4),
    }

    dist: dict[str, Any] = {}
    if f1_vals:
        mean_f1 = sum(f1_vals) / len(f1_vals)
        var = sum((x - mean_f1) ** 2 for x in f1_vals) / len(f1_vals)
        dist = {
            "f1_mean": round(mean_f1, 4),
            "f1_std": round(math.sqrt(var), 4),
            "f1_min": round(min(f1_vals), 4),
            "f1_max": round(max(f1_vals), 4),
        }

    return {
        "sample_count": len(rows),
        "micro": micro,
        "macro": macro,
        "distribution": dist,
    }


def _samples_dir(exp_id: str) -> Path:
    return _get_path(exp_id) / SAMPLES_SUBDIR


def write_sample_full(exp_id: str, sample_id: str | int, state: Any) -> Path:
    """Persist one sample at full fidelity for report FN/FP analysis."""
    sid = str(sample_id)
    d = _samples_dir(exp_id)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{sid}.json"
    path.write_text(
        json.dumps(state, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def load_sample_full(exp_id: str, sample_id: str | int) -> dict[str, Any] | None:
    path = _samples_dir(exp_id) / f"{str(sample_id)}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def load_states_for_report(exp_id: str, index_states: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Merge slim states.json index with per-sample archives (full text/entities)."""
    slim = index_states if index_states is not None else (ResultLoader.load(exp_id) or {})
    indices = iter_sample_indices(slim)
    if not indices:
        return {}
    samples_dir = _samples_dir(exp_id)
    if not samples_dir.is_dir():
        return {k: slim[k] for k in indices if k in slim}
    out: Dict[str, Any] = {}
    for sid in indices:
        full = load_sample_full(exp_id, sid)
        out[sid] = full if full is not None else (slim.get(sid) or {})
    return out


def compact_sample_for_report(state: Any) -> Any:
    """Fields sent to the report LLM — no truncation of text or entities."""
    if not isinstance(state, dict):
        return state
    compact: Dict[str, Any] = {}
    for key in (
        "metrics",
        "relations",
        "pairs",
        "text",
        "entities",
        "expected_entities",
        "gold_entities",
        "route",
        "result",
        "head",
        "tail",
        "head_id",
        "tail_id",
        "filtered_entities",
        "error",
        "_metrics_error",
    ):
        if key not in state or state[key] is None:
            continue
        compact[key] = state[key]
    return compact if compact else state


def compact_sample_for_storage(state: Any) -> Any:
    """Lightweight row in states.json for UI/charts — drops checkpoint noise only."""
    if not isinstance(state, dict):
        return state
    drop = {
        "sentences",
        "predicted",
        "sentence",
        "ner_sentence_loop",
        "pubtator_raw_relations",
    }
    return {k: v for k, v in state.items() if k not in drop and v is not None}


def compact_states_for_report(states: Dict[str, Any]) -> Dict[str, Any]:
    """Compact experiment states for LLM report payloads (avoids API timeouts)."""
    if not states:
        return {}
    indices = iter_sample_indices(states)
    n = len(indices)
    summary = summarize_experiment_metrics(states)

    if n <= REPORT_CHART_SAMPLE_THRESHOLD:
        out: Dict[str, Any] = {
            "report_mode": "table",
            "sample_count": n,
            "metrics_summary": summary,
        }
        for idx in indices:
            out[idx] = compact_sample_for_report(states[idx])
        return out

    chart_series = [enrich_sample_error_row(r) for r in per_sample_metrics_list(states)]
    exemplars = select_fp_fn_exemplars(chart_series)

    examples_detail: Dict[str, Any] = {}
    for sid in exemplars["sample_ids"]:
        if sid in states:
            detail = compact_sample_for_report(states[sid])
            if isinstance(detail, dict):
                detail["_selection_reasons"] = exemplars["reasons"].get(sid, [])
            examples_detail[sid] = detail

    return {
        "report_mode": "charts",
        "sample_count": n,
        "metrics_summary": summary,
        "chart_series": chart_series,
        "examples_high_fp": exemplars["high_fp"],
        "examples_high_fn": exemplars["high_fn"],
        "examples_detail": examples_detail,
        "exemplar_selection": {
            "strategy": "top_fp_and_top_fn",
            "top_fp": REPORT_EXEMPLAR_TOP_FP,
            "top_fn": REPORT_EXEMPLAR_TOP_FN,
            "max_articles": REPORT_EXEMPLAR_MAX,
            "reasons": exemplars["reasons"],
        },
        "_note": (
            f"{n} samples: FN/FP report focuses on {len(examples_detail)} articles with "
            "largest per-article FP/FN (examples_detail, full text). "
            "Fixing these yields the largest micro F1 gains."
        ),
    }


def build_report_payload_states(
    states: Dict[str, Any] | None = None, *, exp_id: str | None = None
) -> Dict[str, Any]:
    """Entry point for report agents and SSE report stream."""
    if exp_id:
        states = load_states_for_report(exp_id, states)
    return compact_states_for_report(states or {})


def write_states_bundle(
    exp_id: str,
    store: Dict[str, Any],
    *,
    large_threshold: int | None = None,
    touch_sample_ids: set[str] | None = None,
) -> Path:
    """Write states.json; archive full samples under samples/ when count > threshold."""
    path = _get_path(exp_id)
    path.mkdir(parents=True, exist_ok=True)
    cfg_path = path / "states.json"
    threshold = REPORT_CHART_SAMPLE_THRESHOLD if large_threshold is None else int(large_threshold)
    indices = iter_sample_indices(store)
    large = len(indices) > threshold

    if large:
        for i in indices:
            sid = str(i)
            if sid not in store:
                continue
            if touch_sample_ids is not None and sid not in touch_sample_ids:
                continue
            write_sample_full(exp_id, sid, store[sid])
        compact_store = {
            sid: compact_sample_for_storage(store[sid])
            for sid in indices
            if sid in store
        }
        cfg_path.write_text(
            json.dumps(compact_store, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    else:
        cfg_path.write_text(
            json.dumps(store, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return cfg_path


class ResultLoader:
    @staticmethod
    def load(id: str) -> Dict[str, Any] | None:
        try:
            path = _get_path(id)
            cfg_path = path / "states.json"
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            cfg["id"] = id
            return cfg
        except FileNotFoundError:
            return None

    @staticmethod
    def load_for_report(id: str) -> Dict[str, Any]:
        return build_report_payload_states(exp_id=id)

    @staticmethod
    def load_samples(id: str) -> Dict[str, Any]:
        data = ResultLoader.load(id)
        if not data:
            return {}
        return {k: data[k] for k in iter_sample_indices(data)}

    @staticmethod
    def save(id: str, idx: str | int, result: Dict[str, Any]) -> None:
        path = _get_path(id)
        path.mkdir(parents=True, exist_ok=True)
        cfg_path = path / "states.json"
        store: Dict[str, Any] = {}
        if cfg_path.exists():
            store = json.loads(cfg_path.read_text(encoding="utf-8"))
        store[str(idx)] = result
        write_states_bundle(id, store, touch_sample_ids={str(idx)})
