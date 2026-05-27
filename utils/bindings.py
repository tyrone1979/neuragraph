"""Resolve graph node bindings ({{ START.field }}, {{ node.field }}) at runtime."""
from __future__ import annotations

import json
import re
from typing import Any

_START = re.compile(r"^\{\{\s*START\.(\w+)\s*\}\}$")
_NODE = re.compile(r"^\{\{\s*(\w+)\.(\w+)\s*\}\}$")
_SIMPLE = re.compile(r"^\{\{\s*(\w+)\s*\}\}$")


def resolve_binding_expr(expr: Any, state: dict[str, Any]) -> Any:
    """Resolve one binding value; literals pass through unchanged."""
    if not isinstance(expr, str):
        return expr
    raw = expr.strip()
    if not raw.startswith("{{"):
        return expr

    m = _START.match(raw)
    if m:
        return state.get(m.group(1))

    m = _NODE.match(raw)
    if m:
        _node, field = m.group(1), m.group(2)
        return state.get(field)

    m = _SIMPLE.match(raw)
    if m:
        return state.get(m.group(1))

    return expr


def apply_node_bindings(
    state: dict[str, Any],
    node_id: str,
    bindings_map: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    """Merge resolved bindings into a copy of state for agent invocation."""
    merged = dict(state)
    node_bindings = (bindings_map or {}).get(node_id) or {}
    for field, expr in node_bindings.items():
        val = resolve_binding_expr(expr, state)
        if val is not None:
            merged[field] = val
    return merged


def resolve_loop_items(array_expr: str, state: dict[str, Any]) -> list[Any]:
    val = resolve_binding_expr(array_expr, state)
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        stripped = val.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        return [val]
    if isinstance(val, tuple):
        return list(val)
    return [val]


def merge_loop_values(prev: Any, new: Any) -> Any:
    if new is None:
        return prev
    if prev is None:
        return new
    if isinstance(prev, dict) and isinstance(new, dict):
        out = dict(prev)
        for k, v in new.items():
            out[k] = merge_loop_values(out.get(k), v)
        return out
    if isinstance(prev, list) and isinstance(new, list):
        return prev + new
    if isinstance(new, tuple):
        base = list(prev) if isinstance(prev, list) else ([] if prev is None else [prev])
        base.append(new)
        return base
    return new


def inject_loop_item(state: dict[str, Any], item: Any) -> dict[str, Any]:
    s = dict(state)
    if isinstance(item, dict):
        s.update(item)
        return s
    if isinstance(item, str):
        s.setdefault("sentence", item)
        s.setdefault("text", item)
        return s
    s["item"] = item
    return s
