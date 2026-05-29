"""Filter optimization suggestions that use forbidden shortcuts."""
from __future__ import annotations

from typing import Any


def _mod_text_blob(mod: dict[str, Any]) -> str:
    parts = [
        str(mod.get(k) or "")
        for k in (
            "rationale",
            "process_append",
            "process_replace",
            "prompt_system_append",
            "prompt_human_append",
            "prompt_system_replace",
            "prompt_human_replace",
        )
    ]
    return " ".join(parts).lower()


def disallowed_modification_reason(mod: dict[str, Any]) -> str:
    """Reject shortcuts that leak gold labels or use naive text position only."""
    blob = _mod_text_blob(mod)
    gold_markers = (
        "filtered_entities",
        "head_type",
        "tail_type",
        "entity type guard",
        "e.get('label')",
        'e.get("label")',
        "for e in entities",
        "chemical' or tail_type",
        'chemical" or tail_type',
        "type gate",
        "entity label",
        "label types are not chemical",
    )
    if any(marker in blob for marker in gold_markers):
        return "gold entity label / filtered_entities guard not allowed"
    position_markers = (
        "head_pos",
        "tail_pos",
        "head_pos > tail_pos",
        "head appears after tail",
        "text.find(state.get('head'",
        'text.find(state.get("head"',
        "relation direction validation",
        "within 200 char",
        "char distance",
        "character position",
        "text order",
        "appears before the tail",
    )
    if any(marker in blob for marker in position_markers):
        return "position-only text-order heuristic not allowed"
    return ""


def filter_disallowed_modifications(
    modifications: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for mod in modifications:
        if not isinstance(mod, dict):
            continue
        reason = disallowed_modification_reason(mod)
        if reason:
            rejected.append({**mod, "filter_reason": reason})
        else:
            kept.append(mod)
    return kept, rejected
