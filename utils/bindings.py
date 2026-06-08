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
    if isinstance(val, dict):
        if "head" in val and "tail" in val:
            return [val]
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
    if isinstance(new, dict) and not new and prev is None:
        return {}
    if isinstance(new, list) and not new:
        return prev
    if prev is None:
        return new
    if isinstance(new, str) and new.strip():
        base = list(prev) if isinstance(prev, list) else ([prev] if prev else [])
        if new not in base:
            base.append(new)
        return base
    if isinstance(prev, str) and isinstance(new, str):
        base = [prev]
        if new not in base:
            base.append(new)
        return base
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


def normalize_loop_item(item: Any) -> dict[str, Any] | None:
    """Parse a foreach loop element into a dict (e.g. Chemical–Disease pair)."""
    if isinstance(item, str):
        stripped = item.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                item = json.loads(stripped)
            except json.JSONDecodeError:
                return None
        else:
            return None
    return item if isinstance(item, dict) else None


def item_binding_scalar_targets(item_bindings: dict[str, Any] | None) -> list[str]:
    """Fields bound via {{ field }} from the current foreach element."""
    if not item_bindings:
        return []
    targets: list[str] = []
    for field, expr in item_bindings.items():
        if not isinstance(expr, str):
            continue
        m = _SIMPLE.match(expr.strip())
        if m and m.group(1) == field:
            targets.append(field)
    return targets


def loop_item_context(
    accum: dict[str, Any],
    item: Any,
    item_bindings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """State used to resolve loop itemBindings: workflow accum + current item fields."""
    ctx = dict(accum)
    pair = normalize_loop_item(item)
    if pair is not None:
        ctx.update(pair)
    elif isinstance(item, str):
        targets = item_binding_scalar_targets(item_bindings)
        for field in targets:
            ctx.setdefault(field, item)
        if not targets:
            ctx.setdefault("item", item)
    else:
        ctx["item"] = item
    return ctx


def apply_loop_item_bindings(
    accum: dict[str, Any],
    item: Any,
    item_bindings: dict[str, Any] | None,
    scalar_fields: list[str] | None = None,
) -> dict[str, Any]:
    """Build per-iteration subgraph input from loopConfig.itemBindings."""
    base = inject_loop_item(dict(accum), item, item_bindings, scalar_fields)
    if not item_bindings:
        return base
    ctx = loop_item_context(accum, item, item_bindings)
    for field, expr in item_bindings.items():
        val = resolve_binding_expr(expr, ctx)
        if val is not None:
            base[field] = val
    return base


def inject_loop_item(
    state: dict[str, Any],
    item: Any,
    item_bindings: dict[str, Any] | None = None,
    scalar_fields: list[str] | None = None,
) -> dict[str, Any]:
    pair = normalize_loop_item(item)
    if pair is not None:
        s = dict(state)
        s.update(pair)
        return s
    s = dict(state)
    if isinstance(item, str):
        targets = item_binding_scalar_targets(item_bindings) or list(scalar_fields or [])
        if targets:
            for field in targets:
                s[field] = item
        else:
            s["item"] = item
        return s
    s["item"] = item
    return s
