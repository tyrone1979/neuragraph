"""Compare experiment predictions to gold columns in the test dataset."""
from __future__ import annotations

import json
from ast import literal_eval
from typing import Any, Dict, Optional

from plugin.plugin_loader import get_plugin


def _parse_field(val: Any) -> Any:
    if val is None or val == "":
        return None
    if isinstance(val, (dict, list)):
        return val
    s = str(val).strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        return literal_eval(s)
    except (ValueError, SyntaxError):
        return s


def _predicted_entities(state: Dict[str, Any]) -> Any:
    ent = state.get("entities")
    if ent is None:
        return {}
    if isinstance(ent, str):
        return _parse_field(ent) or {}
    return ent


def _predicted_relations(state: Dict[str, Any]) -> Any:
    rel = state.get("relations")
    if rel is None:
        return []
    if isinstance(rel, str):
        lines = [ln.strip() for ln in rel.splitlines() if ln.strip()]
        pairs = []
        for ln in lines:
            parts = [p.strip() for p in ln.split("|")]
            if len(parts) >= 3:
                pairs.append((parts[0].lower(), parts[1].lower(), parts[2].lower()))
        return pairs
    return rel


def _set_prf(gold_set: set, pred_set: set) -> Dict[str, float]:
    tp = len(gold_set & pred_set)
    fp = len(pred_set - gold_set)
    fn = len(gold_set - pred_set)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {
        "precision": float(prec),
        "recall": float(rec),
        "f1": float(f1),
        "tp": float(tp),
        "fp": float(fp),
        "fn": float(fn),
    }


def _entity_pairs(doc: Any) -> set:
    pairs = set()
    if isinstance(doc, dict):
        for lbl, ents in doc.items():
            for ent in ents or []:
                pairs.add((str(ent).lower(), str(lbl).lower()))
    elif isinstance(doc, list):
        for item in doc:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                pairs.add((str(item[0]).lower(), str(item[1]).lower()))
    return pairs


def _safe_calculate(gold: Any, pred: Any) -> Dict[str, float]:
    calc = get_plugin("MetricsCalculation")
    if calc is not None:
        try:
            return calc.calculate(gold, pred)
        except Exception:
            pass
    if isinstance(gold, dict) or isinstance(pred, dict):
        return _set_prf(_entity_pairs(gold), _entity_pairs(pred))
    g = set(gold) if isinstance(gold, (list, tuple)) else set()
    p = set(pred) if isinstance(pred, (list, tuple)) else set()
    return _set_prf(g, p)


def evaluate_sample(row: Dict[str, Any], state: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Return per-sample metrics dict (precision/recall/f1/tp/fp/fn) when gold columns exist."""
    gold_ent = row.get("gold_entities")
    gold_rel = row.get("gold_relations")
    if not gold_ent and not gold_rel:
        return None

    combined: Dict[str, float] = {}
    if gold_ent:
        m = _safe_calculate(_parse_field(gold_ent), _predicted_entities(state))
        for k, v in m.items():
            if isinstance(v, (int, float)):
                combined[f"entities_{k}" if k in ("tp", "fp", "fn") else k] = float(v)

    if gold_rel:
        gold_pairs = _parse_field(gold_rel)
        if isinstance(gold_pairs, str):
            gold_pairs = _predicted_relations({"relations": gold_pairs})
        pred_pairs = _predicted_relations(state)
        if isinstance(gold_pairs, list) and gold_pairs and isinstance(gold_pairs[0], str):
            gold_pairs = _predicted_relations({"relations": "\n".join(gold_pairs)})
        m = _safe_calculate(gold_pairs, pred_pairs)
        for k, v in m.items():
            if isinstance(v, (int, float)):
                combined[f"relations_{k}" if k in ("tp", "fp", "fn") else f"rel_{k}"] = float(v)

    if not combined:
        return None

    # Top-level scores for report aggregation (prefer entities, else relations).
    for prefix in ("", "rel_"):
        for metric in ("precision", "recall", "f1"):
            key = f"{prefix}{metric}" if prefix else metric
            if key in combined:
                combined.setdefault(metric, combined[key])
    if "f1" not in combined and combined:
        vals = [v for k, v in combined.items() if k.endswith("_f1")]
        if vals:
            combined["f1"] = sum(vals) / len(vals)
    return combined
