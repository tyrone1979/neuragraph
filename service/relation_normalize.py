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


def build_entity_id_lookup(entities: Any, *, label: str | None = None) -> dict[str, str]:
    """
    Map lowercase entity surface form -> canonical id (MeSH or group id).

    Multiple synonyms sharing the same id are all registered to that id.
    When label is set, only entities with that label are included.
    """
    lookup: dict[str, str] = {}
    by_mesh: dict[str, list[str]] = {}
    for ent in parse_entities_raw(entities):
        ent_label = str(ent.get("label") or ent.get("type") or ent.get("etype") or "").strip()
        if label and ent_label and ent_label != label:
            continue
        text = str(ent.get("text") or ent.get("name") or "").strip()
        ent_id = canonical_mesh_id(
            str(ent.get("id") or ent.get("identifier") or ent.get("mesh") or "")
        )
        if not text:
            continue
        if ent_id:
            by_mesh.setdefault(ent_id, []).append(text)
        else:
            lookup[_norm_text(text)] = _norm_text(text)
    for ent_id, texts in by_mesh.items():
        for text in texts:
            lookup[_norm_text(text)] = ent_id
        lookup[_norm_text(ent_id)] = ent_id
        for text in texts:
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
    chem_lookup = build_entity_id_lookup(entities, label="Chemical")
    dis_lookup = build_entity_id_lookup(entities, label="Disease")
    lines: list[str] = []
    if isinstance(relations, str):
        lines = [ln.strip() for ln in relations.splitlines() if ln.strip()]
    elif isinstance(relations, list):
        for item in relations:
            if isinstance(item, str):
                lines.extend(ln.strip() for ln in item.splitlines() if ln.strip())
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                head = str(item[0]).strip()
                tail = str(item[-1]).strip()
                if head and tail:
                    lines.append(f"{head} | CID | {tail}")
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
            h = resolve_entity_side(head, chem_lookup)
            t = resolve_entity_side(tail, dis_lookup)
            if not is_mesh_id(h):
                h = _norm_text(h)
            if not is_mesh_id(t):
                t = _norm_text(t)
        else:
            h = resolve_entity_side(head, chem_lookup)
            t = resolve_entity_side(tail, dis_lookup)
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


def _strip_induced_suffix(text: str) -> str:
    t = str(text or "").strip()
    if t.lower().endswith("-induced"):
        base = t[: -len("-induced")].strip()
        if base:
            return base
    return t


def assign_e2e_group_ids(source_entities: Any, groups: Any) -> list[dict[str, Any]]:
    """
    Expand LLM synonym groups into rows that share numeric ids per label (1, 2, ...).
    Example: CYP + cyclophosphamide -> both id '1' (Chemical); cystitis -> id '1' (Disease).
    """
    passthrough = parse_entities_raw(source_entities)
    group_rows = parse_entities_raw(groups)
    passthrough = [
        {**e, "text": _strip_induced_suffix(e.get("text") or "")} for e in passthrough if e.get("text")
    ]
    group_rows = [
        {
            **g,
            "text": _strip_induced_suffix(g.get("text") or ""),
            "id": _strip_induced_suffix(g.get("id") or g.get("text") or ""),
        }
        for g in group_rows
        if g.get("text") or g.get("id")
    ]
    if not group_rows:
        return passthrough

    out: list[dict[str, Any]] = []
    chem_n, dis_n = 1, 1

    # Bucket LLM rows by (label, cluster key) so shared id → one numeric id (MeSH-like cluster).
    from collections import OrderedDict

    clusters: OrderedDict[tuple[str, str], list[dict[str, Any]]] = OrderedDict()
    for g in group_rows:
        lbl = str(g.get("label") or g.get("type") or "").strip()
        if lbl not in ("Chemical", "Disease"):
            continue
        canonical = str(g.get("id") or g.get("text") or "").strip()
        rep = str(g.get("text") or canonical).strip()
        if not canonical and not rep:
            continue
        if not canonical:
            canonical = rep
        if canonical.upper().startswith("MESH:") or is_mesh_id(canonical):
            canonical = rep or canonical
        key = (lbl, canonical.lower())
        clusters.setdefault(key, []).append(g)

    for (lbl, _cluster_key), rows in clusters.items():
        nid = str(chem_n if lbl == "Chemical" else dis_n)
        if lbl == "Chemical":
            chem_n += 1
        else:
            dis_n += 1

        forms: set[str] = set()
        for g in rows:
            canonical = str(g.get("id") or g.get("text") or "").strip()
            rep = str(g.get("text") or canonical).strip()
            if not canonical:
                canonical = rep
            if canonical.upper().startswith("MESH:") or is_mesh_id(canonical):
                canonical = rep or canonical
            if rep:
                forms.add(rep)
            if canonical:
                forms.add(canonical)

        refs = [r.lower() for r in forms if r]
        for p in passthrough:
            if str(p.get("label") or p.get("type") or "").strip() != lbl:
                continue
            pt = str(p.get("text") or "").strip()
            if not pt:
                continue
            pl = pt.lower()
            if pl in {f.lower() for f in forms}:
                forms.add(pt)
                continue
            if any(pl == rl or (len(pl) >= 2 and (pl in rl or rl in pl)) for rl in refs):
                forms.add(pt)

        for text in sorted(forms, key=lambda s: (len(s), s.lower())):
            out.append({"text": text, "id": nid, "label": lbl})

    assigned: set[tuple[str, str]] = {
        (str(e.get("label") or "").strip(), str(e.get("text") or "").strip().lower())
        for e in out
        if e.get("text") and e.get("label")
    }
    for p in passthrough:
        lbl = str(p.get("label") or p.get("type") or "").strip()
        if lbl not in ("Chemical", "Disease"):
            continue
        pt = str(p.get("text") or "").strip()
        if not pt or (lbl, pt.lower()) in assigned:
            continue
        nid = str(chem_n if lbl == "Chemical" else dis_n)
        if lbl == "Chemical":
            chem_n += 1
        else:
            dis_n += 1
        out.append({"text": pt, "id": nid, "label": lbl})
        assigned.add((lbl, pt.lower()))

    return out
