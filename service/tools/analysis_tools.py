from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _to_obj(data: Any) -> Any:
    if isinstance(data, (dict, list)):
        return data
    if not isinstance(data, str):
        return {}
    text = data.strip()
    if not text:
        return {}
    p = Path(text)
    if p.exists():
        if p.suffix.lower() == ".jsonl":
            out = []
            for ln in p.read_text(encoding="utf-8").splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                out.append(json.loads(ln))
            return out
        return json.loads(p.read_text(encoding="utf-8"))
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _state_items(states: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    if not isinstance(states, dict):
        return []

    def _key(k: str) -> tuple[int, str]:
        return (int(k), k) if str(k).isdigit() else (10**9, str(k))

    out = []
    for k in sorted(states.keys(), key=_key):
        v = states.get(k)
        if isinstance(v, dict):
            out.append((str(k), v))
    return out


def _avg_metrics(states: dict[str, Any]) -> dict[str, float]:
    items = _state_items(states)
    totals = {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    n = 0
    for _, item in items:
        m = item.get("metrics")
        if not isinstance(m, dict):
            continue
        if all(x in m for x in ("precision", "recall", "f1")):
            totals["precision"] += float(m["precision"])
            totals["recall"] += float(m["recall"])
            totals["f1"] += float(m["f1"])
            n += 1
    if n == 0:
        return {}
    return {k: v / n for k, v in totals.items()}


def metrics_delta_compare(
    baseline_states: dict | str,
    candidate_states: dict | str,
    sample_drop_threshold: float = -0.05,
) -> dict[str, Any]:
    base = _to_obj(baseline_states) or {}
    cand = _to_obj(candidate_states) or {}
    base_avg = _avg_metrics(base)
    cand_avg = _avg_metrics(cand)
    delta: dict[str, float] = {}
    for key in ("precision", "recall", "f1"):
        if key in base_avg and key in cand_avg:
            delta[key] = cand_avg[key] - base_avg[key]

    degraded = []
    for sid, b in _state_items(base):
        c = cand.get(sid)
        if not isinstance(c, dict):
            continue
        bm = b.get("metrics") or {}
        cm = c.get("metrics") or {}
        if "f1" not in bm or "f1" not in cm:
            continue
        df1 = float(cm["f1"]) - float(bm["f1"])
        if df1 <= sample_drop_threshold:
            degraded.append(
                {
                    "sample_id": sid,
                    "baseline_f1": float(bm["f1"]),
                    "candidate_f1": float(cm["f1"]),
                    "delta_f1": df1,
                    "baseline_precision": float(bm.get("precision", 0)),
                    "candidate_precision": float(cm.get("precision", 0)),
                    "baseline_recall": float(bm.get("recall", 0)),
                    "candidate_recall": float(cm.get("recall", 0)),
                }
            )
    degraded.sort(key=lambda x: x["delta_f1"])
    return {
        "baseline_avg": base_avg,
        "candidate_avg": cand_avg,
        "delta": delta,
        "significant_drop_threshold": sample_drop_threshold,
        "significantly_degraded_samples": degraded,
        "decision_hint": "retain baseline" if delta.get("f1", 0) <= 0 else "keep candidate",
    }


def _norm_rel_item(x: Any) -> dict[str, str]:
    if isinstance(x, dict):
        h = str(x.get("head") or x.get("head_text") or x.get("h") or "").strip()
        t = str(x.get("tail") or x.get("tail_text") or x.get("t") or "").strip()
        r = str(x.get("relation") or x.get("label") or x.get("type") or "$").strip()
        ht = str(x.get("head_type") or x.get("h_type") or "").strip()
        tt = str(x.get("tail_type") or x.get("t_type") or "").strip()
        return {"head": h, "tail": t, "relation": r, "head_type": ht, "tail_type": tt}
    if isinstance(x, (list, tuple)) and len(x) >= 2:
        h, t = str(x[0]).strip(), str(x[1]).strip()
        r = str(x[2]).strip() if len(x) >= 3 else "$"
        return {"head": h, "tail": t, "relation": r, "head_type": "", "tail_type": ""}
    s = str(x).strip()
    if "|" in s:
        parts = [p.strip() for p in s.split("|")]
        if len(parts) >= 2:
            return {
                "head": parts[0],
                "tail": parts[1],
                "relation": parts[2] if len(parts) >= 3 else "$",
                "head_type": "",
                "tail_type": "",
            }
    return {"head": "", "tail": "", "relation": "$", "head_type": "", "tail_type": ""}


def _rel_key(r: dict[str, str]) -> tuple[str, str, str]:
    return (r["head"].lower(), r["tail"].lower(), r["relation"].lower())


def _pair_key(r: dict[str, str]) -> tuple[str, str]:
    return (r["head"].lower(), r["tail"].lower())


def fn_fp_bucket_analyzer(
    predicted: list | dict | str,
    gold: list | dict | str,
    text: str = "",
) -> dict[str, Any]:
    pred_obj = _to_obj(predicted)
    gold_obj = _to_obj(gold)
    pred_list = pred_obj if isinstance(pred_obj, list) else pred_obj.get("relations", []) if isinstance(pred_obj, dict) else []
    gold_list = gold_obj if isinstance(gold_obj, list) else gold_obj.get("relations", []) if isinstance(gold_obj, dict) else []
    preds = [_norm_rel_item(x) for x in pred_list]
    golds = [_norm_rel_item(x) for x in gold_list]

    pred_exact = {_rel_key(x): x for x in preds if x["head"] and x["tail"]}
    gold_exact = {_rel_key(x): x for x in golds if x["head"] and x["tail"]}

    pred_pairs = defaultdict(list)
    gold_pairs = defaultdict(list)
    for p in preds:
        if p["head"] and p["tail"]:
            pred_pairs[_pair_key(p)].append(p)
    for g in golds:
        if g["head"] and g["tail"]:
            gold_pairs[_pair_key(g)].append(g)

    fp = [x for k, x in pred_exact.items() if k not in gold_exact]
    fn = [x for k, x in gold_exact.items() if k not in pred_exact]

    fp_buckets = Counter()
    fn_buckets = Counter()
    fp_examples: dict[str, list[dict[str, str]]] = defaultdict(list)
    fn_examples: dict[str, list[dict[str, str]]] = defaultdict(list)

    def _push(bucket_counter: Counter, ex_map: dict[str, list], bucket: str, item: dict[str, str]) -> None:
        bucket_counter[bucket] += 1
        if len(ex_map[bucket]) < 5:
            ex_map[bucket].append(item)

    for item in fp:
        pair = _pair_key(item)
        if pair in gold_pairs:
            g0 = gold_pairs[pair][0]
            if item["relation"].lower() != g0["relation"].lower():
                bucket = "relation_error"
            elif (item["head_type"], item["tail_type"]) != (g0["head_type"], g0["tail_type"]):
                bucket = "type_error"
            else:
                bucket = "boundary_error"
        else:
            bucket = "spurious_relation"
        _push(fp_buckets, fp_examples, bucket, item)

    for item in fn:
        pair = _pair_key(item)
        if pair in pred_pairs:
            p0 = pred_pairs[pair][0]
            if item["relation"].lower() != p0["relation"].lower():
                bucket = "relation_error"
            elif (item["head_type"], item["tail_type"]) != (p0["head_type"], p0["tail_type"]):
                bucket = "type_error"
            else:
                bucket = "boundary_error"
        else:
            bucket = "missed_recall"
        _push(fn_buckets, fn_examples, bucket, item)

    return {
        "text_length": len(text or ""),
        "fp_total": len(fp),
        "fn_total": len(fn),
        "fp_buckets": dict(fp_buckets),
        "fn_buckets": dict(fn_buckets),
        "fp_examples": dict(fp_examples),
        "fn_examples": dict(fn_examples),
    }


def _extract_rel_set(state_item: dict[str, Any]) -> set[str]:
    for key in ("relations", "predicted_relations", "predictions", "result"):
        value = state_item.get(key)
        if isinstance(value, list):
            out = set()
            for one in value:
                r = _norm_rel_item(one)
                if r["head"] and r["tail"]:
                    out.add("|".join(_rel_key(r)))
            if out:
                return out
    return set()


def agent_change_impact_trace(
    version_map: dict | str,
    baseline_states: dict | str,
    candidate_states: dict | str,
) -> dict[str, Any]:
    vm = _to_obj(version_map) or {}
    vm = vm if isinstance(vm, dict) else {}
    base = _to_obj(baseline_states) or {}
    cand = _to_obj(candidate_states) or {}
    base_avg = _avg_metrics(base)
    cand_avg = _avg_metrics(cand)
    delta = {
        k: float(cand_avg.get(k, 0)) - float(base_avg.get(k, 0))
        for k in ("precision", "recall", "f1")
        if k in base_avg and k in cand_avg
    }

    changed_agents = sorted(vm.keys())
    n = max(1, len(changed_agents))
    changed_samples = []
    for sid, b in _state_items(base):
        c = cand.get(sid)
        if not isinstance(c, dict):
            continue
        if _extract_rel_set(b) != _extract_rel_set(c):
            changed_samples.append(sid)

    by_agent = []
    for aid in changed_agents:
        by_agent.append(
            {
                "agent_id": aid,
                "version": vm.get(aid),
                "estimated_delta_precision": delta.get("precision", 0.0) / n,
                "estimated_delta_recall": delta.get("recall", 0.0) / n,
                "estimated_delta_f1": delta.get("f1", 0.0) / n,
                "confidence": "medium" if len(changed_agents) == 1 else "low",
                "assumption": "equal-share attribution across changed agents",
            }
        )
    return {
        "overall_delta": delta,
        "changed_agents": changed_agents,
        "changed_sample_ids": changed_samples,
        "agent_contributions": by_agent,
        "method_note": "Estimated attribution without full ablation; use one-agent-per-round experiments for stronger causality.",
    }


def _dedupe_lines(text: str) -> str:
    out = []
    seen = set()
    for ln in (text or "").replace("\r\n", "\n").split("\n"):
        key = re.sub(r"\s+", " ", ln.strip().lower())
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(ln.rstrip())
    return "\n".join(out).strip()


def _extract_placeholders(s: str) -> set[str]:
    return set(re.findall(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})", s or ""))


def prompt_patch_apply_safe(
    original_prompt: dict | str,
    patch: dict | str,
    max_system_chars: int = 1200,
    max_human_chars: int = 1800,
    allowed_placeholders: list | None = None,
) -> dict[str, Any]:
    try:
        max_system_chars = int(max_system_chars) if max_system_chars is not None else 1200
    except Exception:
        max_system_chars = 1200
    try:
        max_human_chars = int(max_human_chars) if max_human_chars is not None else 1800
    except Exception:
        max_human_chars = 1800
    if max_system_chars <= 0:
        max_system_chars = 1200
    if max_human_chars <= 0:
        max_human_chars = 1800

    src = _to_obj(original_prompt)
    if isinstance(src, str):
        src = {"system": "", "human": src}
    if not isinstance(src, dict):
        src = {}
    p = _to_obj(patch)
    p = p if isinstance(p, dict) else {}

    system = str(src.get("system") or "")
    human = str(src.get("human") or "")

    rs = str(p.get("prompt_system_replace") or p.get("system_replace") or "").strip()
    rh = str(p.get("prompt_human_replace") or p.get("human_replace") or "").strip()
    if rs:
        system = rs
    if rh:
        human = rh

    asys = str(p.get("prompt_system_append") or p.get("system_append") or "").strip()
    ah = str(p.get("prompt_human_append") or p.get("human_append") or "").strip()
    if asys:
        system = (system + "\n\n" + asys).strip() if system else asys
    if ah:
        human = (human + "\n\n" + ah).strip() if human else ah

    system = _dedupe_lines(system)
    human = _dedupe_lines(human)

    errors = []
    warnings = []
    if len(system) > max_system_chars:
        errors.append(f"system exceeds max chars: {len(system)} > {max_system_chars}")
    if len(human) > max_human_chars:
        errors.append(f"human exceeds max chars: {len(human)} > {max_human_chars}")

    if re.search(r'(?<!\{)\{(?=\s*")', system) or re.search(r'(?<!\{)\{(?=\s*")', human):
        warnings.append("JSON literal braces detected; use double braces {{...}} for ChatPromptTemplate safety.")

    placeholders = sorted(_extract_placeholders(system) | _extract_placeholders(human))
    if allowed_placeholders:
        allowed = {str(x).strip() for x in allowed_placeholders if str(x).strip()}
        unknown = [x for x in placeholders if x not in allowed]
        if unknown:
            errors.append(f"unknown placeholders: {unknown}")

    return {
        "prompt_template": {"system": system, "human": human},
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "placeholders": placeholders,
        "char_count": {"system": len(system), "human": len(human)},
    }


def report_quality_scorer(report_text: str, context: dict | str | None = None) -> dict[str, Any]:
    txt = (report_text or "").lower()
    ctx = _to_obj(context) if context is not None else {}
    context_keys = set(ctx.keys()) if isinstance(ctx, dict) else set()

    evidence = 0
    if "metrics" in txt:
        evidence += 2
    if "fn" in txt or "fp" in txt:
        evidence += 1
    if re.search(r"\b\d+(\.\d+)?\b", txt):
        evidence += 1
    if "sample" in txt or "evidence" in txt:
        evidence += 1
    evidence = min(5, evidence)

    executable = 0
    for kw in ("target agent", "what to change", "prompt", "process", "tool", "expected impact"):
        if kw in txt:
            executable += 1
    executable = min(5, executable)

    traceable = 0
    for kw in ("version", "graph", "agent id", "baseline", "candidate"):
        if kw in txt:
            traceable += 1
    if {"agent_versions", "graphs", "states"} & context_keys:
        traceable += 1
    traceable = min(5, traceable)

    total = evidence + executable + traceable
    return {
        "total_score": total,
        "max_score": 15,
        "evidence_score": evidence,
        "executable_score": executable,
        "traceability_score": traceable,
        "level": "high" if total >= 12 else "medium" if total >= 8 else "low",
    }


def _parse_rel_count(row: dict[str, Any]) -> int:
    for key in ("gold_relations", "relations", "labels", "expected_relations"):
        value = row.get(key)
        if isinstance(value, list):
            return len(value)
        if isinstance(value, str) and value.strip():
            try:
                obj = json.loads(value)
                if isinstance(obj, list):
                    return len(obj)
            except json.JSONDecodeError:
                return len([x for x in value.split(";") if x.strip()])
    return 0


def _parse_entity_count(row: dict[str, Any]) -> int:
    value = row.get("entities")
    if isinstance(value, list):
        return len(value)
    if isinstance(value, str) and value.strip():
        try:
            obj = json.loads(value)
            if isinstance(obj, list):
                return len(obj)
        except json.JSONDecodeError:
            return len([x for x in value.splitlines() if x.strip()])
    return 0


def _load_dataset(dataset: list | dict | str) -> list[dict[str, Any]]:
    obj = _to_obj(dataset)
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        rows = obj.get("rows")
        if isinstance(rows, list):
            return [x for x in rows if isinstance(x, dict)]
    if isinstance(dataset, str):
        p = Path(dataset)
        if p.exists() and p.suffix.lower() == ".csv":
            with p.open("r", encoding="utf-8", newline="") as f:
                return [dict(r) for r in csv.DictReader(f)]
    return []


def dataset_sampler_stratified(
    dataset: list | dict | str,
    sample_size: int = 20,
    text_field: str = "text",
) -> dict[str, Any]:
    rows = _load_dataset(dataset)
    n = len(rows)
    if n == 0 or sample_size <= 0:
        return {"sampled_rows": [], "selected_indices": [], "distribution": {}}

    feats = []
    for i, row in enumerate(rows):
        text = str(row.get(text_field) or "")
        tok = max(1, len(text.split()))
        ent = _parse_entity_count(row)
        rel = _parse_rel_count(row)
        feats.append((i, len(text), ent / tok, rel))

    lengths = sorted([x[1] for x in feats])
    dens = sorted([x[2] for x in feats])
    rels = sorted([x[3] for x in feats])
    q = lambda arr, p: arr[min(len(arr) - 1, max(0, int((len(arr) - 1) * p)))]
    l1, l2 = q(lengths, 0.33), q(lengths, 0.66)
    d1, d2 = q(dens, 0.33), q(dens, 0.66)
    r1, r2 = q(rels, 0.33), q(rels, 0.66)

    def _bin(v: float, a: float, b: float) -> int:
        return 0 if v <= a else 1 if v <= b else 2

    strata = defaultdict(list)
    for i, ln, den, rel in feats:
        key = (_bin(ln, l1, l2), _bin(den, d1, d2), _bin(rel, r1, r2))
        strata[key].append(i)

    wanted = min(sample_size, n)
    selected = []
    keys = sorted(strata.keys())
    while len(selected) < wanted and keys:
        next_keys = []
        for k in keys:
            if strata[k] and len(selected) < wanted:
                selected.append(strata[k].pop(0))
            if strata[k]:
                next_keys.append(k)
        keys = next_keys

    sampled = [rows[i] for i in selected]
    dist = Counter()
    for i in selected:
        ln = len(str(rows[i].get(text_field) or ""))
        den = _parse_entity_count(rows[i]) / max(1, len(str(rows[i].get(text_field) or "").split()))
        rel = _parse_rel_count(rows[i])
        dist[str((_bin(ln, l1, l2), _bin(den, d1, d2), _bin(rel, r1, r2)))] += 1

    return {
        "sampled_rows": sampled,
        "selected_indices": selected,
        "distribution": dict(dist),
        "sample_size": wanted,
        "total_rows": n,
    }


def error_case_exporter(states: dict | str, worst_k: int = 10) -> dict[str, Any]:
    obj = _to_obj(states) or {}
    rows = []
    for sid, item in _state_items(obj):
        m = item.get("metrics") or {}
        fp = float(m.get("fp", m.get("FP", 0)) or 0)
        fn = float(m.get("fn", m.get("FN", 0)) or 0)
        f1 = float(m.get("f1", 0) or 0)
        score = f1 - 0.01 * (fp + fn)
        rows.append((score, sid, item))
    rows.sort(key=lambda x: x[0])
    picked = rows[: max(1, int(worst_k))]

    cases = []
    md_lines = ["# Worst Error Cases", ""]
    for _, sid, item in picked:
        m = item.get("metrics") or {}
        case = {
            "sample_id": sid,
            "metrics": m,
            "text": item.get("text", ""),
            "predicted": item.get("relations") or item.get("predicted_relations") or item.get("result"),
            "gold": item.get("gold_relations") or item.get("labels"),
        }
        cases.append(case)
        md_lines.append(f"## Sample {sid}")
        md_lines.append(
            f"- Precision: {m.get('precision', 0)} | Recall: {m.get('recall', 0)} | F1: {m.get('f1', 0)} | FP: {m.get('fp', 0)} | FN: {m.get('fn', 0)}"
        )
        if case["text"]:
            md_lines.append(f"- Text: {str(case['text'])[:300]}")
        md_lines.append("")

    jsonl = "\n".join(json.dumps(x, ensure_ascii=False) for x in cases)
    return {
        "cases": cases,
        "markdown": "\n".join(md_lines).strip(),
        "jsonl": jsonl,
        "count": len(cases),
    }


def agent_version_guard(metrics_delta: dict | str, policy: dict | str | None = None) -> dict[str, Any]:
    d = _to_obj(metrics_delta) or {}
    p = _to_obj(policy) if policy is not None else {}
    if not isinstance(p, dict):
        p = {}

    min_f1_delta = float(p.get("min_f1_delta", 0.0))
    max_p_drop = float(p.get("max_precision_drop", 0.03))
    max_r_drop = float(p.get("max_recall_drop", 0.03))
    max_f1_drop = float(p.get("max_f1_drop", 0.0))
    warn_p_drop = float(p.get("warn_precision_drop", 0.01))
    warn_r_drop = float(p.get("warn_recall_drop", 0.01))

    precision = float(d.get("precision", 0.0))
    recall = float(d.get("recall", 0.0))
    f1 = float(d.get("f1", 0.0))

    hard = []
    warn = []
    if f1 < min_f1_delta:
        hard.append(f"f1 delta {f1:.6f} < min_f1_delta {min_f1_delta:.6f}")
    if precision < -max_p_drop:
        hard.append(f"precision drop {precision:.6f} exceeds {-max_p_drop:.6f}")
    elif precision < -warn_p_drop:
        warn.append(f"precision drop warning {precision:.6f}")
    if recall < -max_r_drop:
        hard.append(f"recall drop {recall:.6f} exceeds {-max_r_drop:.6f}")
    elif recall < -warn_r_drop:
        warn.append(f"recall drop warning {recall:.6f}")
    if f1 < -max_f1_drop:
        hard.append(f"f1 drop {f1:.6f} exceeds {-max_f1_drop:.6f}")

    if hard:
        action = "rollback"
    elif warn:
        action = "keep_with_alert"
    else:
        action = "keep"

    return {
        "action": action,
        "hard_violations": hard,
        "warnings": warn,
        "metrics_delta": {"precision": precision, "recall": recall, "f1": f1},
        "policy": {
            "min_f1_delta": min_f1_delta,
            "max_precision_drop": max_p_drop,
            "max_recall_drop": max_r_drop,
            "max_f1_drop": max_f1_drop,
            "warn_precision_drop": warn_p_drop,
            "warn_recall_drop": warn_r_drop,
        },
    }

