"""Compute workflow evaluation metrics via MetricsCalculation plugin (graph-driven)."""
from __future__ import annotations

import re
from typing import Any

from service.meta.loader import MetaLoader, GraphMetaLoader

_BINDING = re.compile(r"^\{\{\s*(?:START\.)?([\w.]+)\s*\}\}$")

# Conventional aliases when graph JSON omits explicit field names.
_EXPECTED_ALIASES = (
    "gold_relations",
    "expected_relations",
    "ground_truth",
    "gold_entities",
    "expected_entities",
    "expected",
)
_PREDICTED_ALIASES = (
    "relations",
    "predicted_relations",
    "predicted",
    "entities",
)


def _resolve_binding_expr(expr: Any, row: dict[str, Any], state: dict[str, Any]) -> Any:
    if not isinstance(expr, str):
        return expr
    raw = expr.strip()
    m = _BINDING.match(raw)
    if not m:
        return expr
    path = m.group(1)
    if path.startswith("START."):
        key = path[6:]
        return row.get(key) if key in row else state.get(key)
    if "." in path:
        _node, field = path.split(".", 1)
        return state.get(field)
    if path in row:
        return row.get(path)
    return state.get(path)


def _first_present(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _metric_value(source: dict[str, Any], row: dict[str, Any], state: dict[str, Any]) -> Any:
    src = (source or {}).get("from", "input")
    field = source.get("field")
    if source.get("expr"):
        return _resolve_binding_expr(source["expr"], row, state)
    if not field:
        return None
    if src == "state":
        return state.get(field)
    if src == "input":
        return row.get(field) if field in row else state.get(field)
    if src == "binding":
        return _resolve_binding_expr(source.get("expr") or f"{{{{ {field} }}}}", row, state)
    return row.get(field) if field in row else state.get(field)


def infer_metrics_specs(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive metric specs from eval_* nodes and their bindings."""
    specs: list[dict[str, Any]] = []
    bindings_map = graph.get("bindings") or {}
    for node in graph.get("nodes", []):
        if node in ("START", "END"):
            continue
        agent = MetaLoader.load("agents", node)
        if not agent:
            continue
        aid = agent.get("id") or node
        binds = bindings_map.get(node) or {}
        out_name = (agent.get("outputs") or {}).get("name")
        inputs = set(agent.get("inputs") or [])

        if aid == "eval_metrics_relation" or (
            out_name == "metrics" and {"ground_truth", "relations"} <= inputs
        ):
            specs.append(
                {
                    "type": "relation_pairs",
                    "expected": {
                        "from": "binding",
                        "expr": binds.get("ground_truth")
                        or binds.get("expected")
                        or "{{ START.gold_relations }}",
                    },
                    "predicted": {
                        "from": "binding",
                        "expr": binds.get("relations")
                        or binds.get("predicted")
                        or "{{ relations }}",
                    },
                }
            )
        elif aid == "eval_metrics" or (
            out_name == "metrics" and "expected" in inputs and "predicted" in inputs
        ):
            specs.append(
                {
                    "type": "entity_dict",
                    "expected": {
                        "from": "binding",
                        "expr": binds.get("expected")
                        or "{{ START.expected_entities }}",
                    },
                    "predicted": {
                        "from": "binding",
                        "expr": binds.get("predicted") or "{{ predicted }}",
                    },
                }
            )
    return specs


def load_metrics_specs(graph_id: str) -> list[dict[str, Any]]:
    graphs = GraphMetaLoader.load(graph_id)
    graph = graphs.get(graph_id) or {}
    explicit = graph.get("metrics")
    if isinstance(explicit, list) and explicit:
        return list(explicit)
    return infer_metrics_specs(graph)


def compute_workflow_metrics(
    graph_id: str | None,
    row: dict[str, Any],
    state: dict[str, Any],
    *,
    calc: Any = None,
) -> dict[str, Any]:
    """
    Return a metrics dict (precision/recall/f1, …) from graph config + row gold + state outputs.
    Merges with metrics already present on state (e.g. from eval_metrics agent).
    """
    if not graph_id:
        return dict(state.get("metrics") or {})

    if calc is None:
        from plugin.plugin_loader import get_plugin

        calc = get_plugin("MetricsCalculation")
    if not calc:
        return dict(state.get("metrics") or {})

    specs = load_metrics_specs(graph_id)
    if not specs:
        return dict(state.get("metrics") or {})

    metrics: dict[str, Any] = dict(state.get("metrics") or {})
    row = row or {}
    state = state or {}

    for spec in specs:
        typ = (spec.get("type") or "entity_dict").lower()
        expected_src = spec.get("expected") or {}
        predicted_src = spec.get("predicted") or {}
        expected_val = _metric_value(expected_src, row, state)
        predicted_val = _metric_value(predicted_src, row, state)

        if expected_val is None:
            expected_val = _first_present(row, _EXPECTED_ALIASES) or _first_present(
                state, _EXPECTED_ALIASES
            )
        if predicted_val is None:
            predicted_val = _first_present(state, _PREDICTED_ALIASES)

        if expected_val is None or predicted_val is None:
            continue

        prefix = spec.get("prefix") or ""
        if typ == "relation_pairs":
            expected = calc.parse_relation_pairs(expected_val)
            predicted = calc.parse_relation_pairs(predicted_val)
            block = calc.calculate(expected, predicted)
            for key, val in block.items():
                out_key = f"{prefix}{key}" if prefix else key
                if key in ("tp", "fp", "fn") and not prefix:
                    out_key = f"rel_{key}"
                metrics[out_key] = val
            if not prefix:
                metrics.setdefault("rel_f1", block.get("f1", 0.0))
        else:
            block = calc.calculate(expected_val, predicted_val)
            for key, val in block.items():
                out_key = f"{prefix}{key}" if prefix else key
                metrics[out_key] = val

    return metrics
