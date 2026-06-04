"""Normalize CID relation lines to MeSH-style IDs using input entity annotations."""

from __future__ import annotations

import json
import re
from typing import Any

_MESH_ID_RE = re.compile(r"^(?:MESH:)?([DC]\d+)$", re.IGNORECASE)
_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")


def _norm_text(value: str) -> str:
    return str(value or "").strip().lower()


def _tokens(value: str) -> set[str]:
    return {t for t in _TOKEN_SPLIT_RE.split(_norm_text(value)) if len(t) >= 3}


def canonical_mesh_id(raw: str) -> str:
    """Normalize 'MESH:D003556' / 'd003556' -> 'D003556'; leave plain text unchanged."""
    s = str(raw or "").strip()
    if not s:
        return ""
    m = _MESH_ID_RE.match(s)
    if m:
        return m.group(1).upper()
    return s


def is_mesh_id(value: str) -> bool:
    return bool(_MESH_ID_RE.match(str(value or "").strip()))


def parse_entities_raw(entities: Any) -> list[dict[str, Any]]:
    if not entities:
        return []
    if isinstance(entities, str):
        try:
            parsed = json.loads(entities)
        except json.JSONDecodeError:
            return []
        return parse_entities_raw(parsed)
    if isinstance(entities, list):
        return [e for e in entities if isinstance(e, dict)]
    return []


def build_entity_id_lookup(entities: Any) -> dict[str, str]:
    """
    Map lowercase entity surface form -> canonical MeSH id (D/C prefix).

    Multiple synonyms (CM, contrast media) share the same id when present in entities.
    """
    lookup: dict[str, str] = {}
    for ent in parse_entities_raw(entities):
        text = str(ent.get("text") or ent.get("name") or "").strip()
        ent_id = canonical_mesh_id(str(ent.get("id") or ent.get("identifier") or ""))
        if not text or not ent_id:
            continue
        lookup[_norm_text(text)] = ent_id
        if is_mesh_id(text):
            lookup[_norm_text(ent_id)] = ent_id
    return lookup


def resolve_entity_side(name: str, lookup: dict[str, str]) -> str:
    """Resolve one relation endpoint to MeSH id when possible, else lowercase text."""
    raw = str(name or "").strip()
    if not raw:
        return ""
    if is_mesh_id(raw):
        return canonical_mesh_id(raw)
    key = _norm_text(raw)
    if key in lookup:
        return lookup[key]
    # Substring fallback: e.g. 'diabetes mellitus type 1' ~ '(insulin-dependent) diabetes mellitus'
    if len(key) >= 5:
        hits: set[str] = set()
        for text_key, ent_id in lookup.items():
            if len(text_key) < 4:
                continue
            if text_key in key or key in text_key:
                hits.add(ent_id)
        if len(hits) == 1:
            return hits.pop()
    query_toks = _tokens(key)
    if len(query_toks) >= 2:
        token_hits: set[str] = set()
        for text_key, ent_id in lookup.items():
            overlap = query_toks & _tokens(text_key)
            if len(overlap) >= 2:
                token_hits.add(ent_id)
        if len(token_hits) == 1:
            return token_hits.pop()
    return key


def parse_cid_line(line: str) -> tuple[str, str, str] | None:
    parts = [p.strip() for p in str(line or "").split("|")]
    if len(parts) < 2:
        return None
    if len(parts) >= 3:
        head, rel, tail = parts[0], parts[1], parts[-1]
    else:
        head, rel, tail = parts[0], "", parts[1]
    if not head or not tail:
        return None
    return head, rel, tail


def normalize_cid_relation_lines(
    relations: Any,
    entities: Any,
    *,
    output_format: str = "id",
) -> list[str]:
    """
    Normalize relation lines using input `entities` (not gold).

    Args:
        relations: list[str] like 'Head | CID | Tail' or a multiline string.
        entities: JSON list [{text, id, label}] or JSON string thereof.
        output_format: 'id' -> prefer MeSH ids; 'text' -> lowercase surface forms.

    Returns:
        Deduped list of 'head | CID | tail' lines.
    """
    lookup = build_entity_id_lookup(entities)
    lines: list[str] = []
    if isinstance(relations, str):
        lines = [ln.strip() for ln in relations.splitlines() if ln.strip()]
    elif isinstance(relations, list):
        for item in relations:
            if isinstance(item, str):
                lines.extend(ln.strip() for ln in item.splitlines() if ln.strip())
    else:
        return []

    out: list[str] = []
    seen: set[tuple[str, str]] = set()
    for line in lines:
        parsed = parse_cid_line(line)
        if not parsed:
            continue
        head, _rel, tail = parsed
        if output_format == "text":
            h = resolve_entity_side(head, lookup)
            t = resolve_entity_side(tail, lookup)
            if not is_mesh_id(h):
                h = _norm_text(h)
            if not is_mesh_id(t):
                t = _norm_text(t)
        else:
            h = resolve_entity_side(head, lookup)
            t = resolve_entity_side(tail, lookup)
        key = (_norm_text(h), _norm_text(t))
        if key in seen:
            continue
        seen.add(key)
        out.append(f"{h} | CID | {t}")
    return out


def normalize_relation_pair_key(head: str, tail: str, lookup: dict[str, str]) -> tuple[str, str]:
    """Pair key for metrics after ID normalization (lowercase for set compare)."""
    h = resolve_entity_side(head, lookup)
    t = resolve_entity_side(tail, lookup)
    return _norm_text(h), _norm_text(t)
