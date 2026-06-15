"""CSV row serializers for dataset export formats."""
from __future__ import annotations

import json
from typing import Any


def _mesh_map(art) -> dict[str, str]:
    return {e.mesh: e.text for e in art.entities}


def gold_relations_cid_mesh(art) -> str:
    return "\n".join(f"{h} | {t}" for h, t in art.expected_relations)


def gold_relations_cid_text(art, rel_label: str = "CID") -> str:
    mesh_to_text = _mesh_map(art)
    lines = []
    for head_mesh, tail_mesh in art.expected_relations:
        h = mesh_to_text.get(head_mesh, head_mesh)
        t = mesh_to_text.get(tail_mesh, tail_mesh)
        lines.append(f"{h} | {rel_label} | {t}")
    return "\n".join(lines)


def gold_relations_typed(art) -> str:
    mesh_to_text = _mesh_map(art)
    lines = []
    for rel in art.res:
        head = mesh_to_text.get(rel.head_mesh, rel.head_mesh)
        tail = mesh_to_text.get(rel.tail_mesh, rel.tail_mesh)
        lines.append(f"{head} | {rel.relation} | {tail}")
    return "\n".join(lines)


def entities_json(art) -> str:
    entities = [{"text": e.text, "id": e.mesh, "label": e.etype} for e in art.entities]
    return json.dumps(entities, ensure_ascii=False)


def row_re(art, *, relation_mode: str, rel_label: str = "CID") -> dict[str, str]:
    if relation_mode == "cid_mesh":
        gold = gold_relations_cid_mesh(art)
    elif relation_mode == "typed":
        gold = gold_relations_typed(art)
    else:
        gold = gold_relations_cid_text(art, rel_label)
    return {
        "text": art.text,
        "entities": entities_json(art),
        "gold_relations": gold,
    }


def row_ner(art, *, relation_mode: str, default_labels: str, rel_label: str = "CID") -> dict[str, str]:
    if relation_mode == "cid_mesh":
        gold = gold_relations_cid_text(art, rel_label)
    elif relation_mode == "typed":
        gold = gold_relations_typed(art)
    else:
        gold = gold_relations_cid_text(art, rel_label)
    return {
        "text": art.text,
        "labels": art.labels or default_labels,
        "gold_entities": json.dumps(art.expected_entities, ensure_ascii=False),
        "gold_relations": gold,
    }


def row_pubtator(art, *, rel_label: str = "CID") -> dict[str, str]:
    return {
        "text": art.text,
        "entities": entities_json(art),
        "pmid": str(art.pmid),
        "gold_relations": gold_relations_cid_text(art, rel_label),
    }


FORMAT_FIELDS: dict[str, list[str]] = {
    "re": ["text", "entities", "gold_relations"],
    "ner": ["text", "labels", "gold_entities", "gold_relations"],
    "pubtator": ["text", "entities", "pmid", "gold_relations"],
}

ROW_BUILDERS = {
    "re": row_re,
    "ner": row_ner,
    "pubtator": row_pubtator,
}
