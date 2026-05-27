"""Backup and normalize workflow graph JSON for round-trip tests."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
GRAPHS = ROOT / "meta" / "graphs"
BACKUP = ROOT / "meta" / "graphs_backup"

SKIP_KEYS = frozenset({"created_at", "id"})

WF_IDS = [
    "wf_cid_ner_flair_eval",
    "wf_cid_ner_llm_eval",
    "wf_cid_re_branch",
    "wf_cid_re_llm_linear",
    "wf_doc_ner_flair_eval",
    "wf_doc_ner_llm_eval",
    "wf_doc_ner_loop_branch",
    "wf_doc_re_nested_branch",
    "wf_general_report_linear",
    "wf_kg_flair_full",
    "wf_kg_llm_full",
    "wf_kg_syntax_loop",
    "wf_re_verify_llm_loop",
    "wf_word_seg_llm_eval",
]
SG_IDS = [
    "sg_ner_flair_sent",
    "sg_ner_llm_tree",
    "sg_preprocess_inner",
    "sg_re_preprocess",
    "sg_re_tree",
    "sg_relation_verify",
]
ALL_GRAPH_IDS = WF_IDS + SG_IDS


def backup_graphs(force: bool = False) -> Path:
    """Copy meta/graphs/*.json → meta/graphs_backup/."""
    BACKUP.mkdir(parents=True, exist_ok=True)
    if not force and any(BACKUP.glob("*.json")):
        return BACKUP
    for p in GRAPHS.glob("*.json"):
        shutil.copy2(p, BACKUP / p.name)
    return BACKUP


def delete_all_graphs() -> int:
    """Remove all workflow JSON from meta/graphs/ (backup untouched)."""
    n = 0
    for p in GRAPHS.glob("*.json"):
        p.unlink()
        n += 1
    return n


def ensure_backup() -> Path:
    """Use existing backup or create from current graphs."""
    BACKUP.mkdir(parents=True, exist_ok=True)
    if any(BACKUP.glob("*.json")):
        return BACKUP
    return backup_graphs(force=True)


def restore_graph(graph_id: str) -> None:
    src = BACKUP / f"{graph_id}.json"
    if not src.is_file():
        raise FileNotFoundError(f"Backup missing: {src}")
    shutil.copy2(src, GRAPHS / f"{graph_id}.json")


def restore_all_graphs() -> None:
    for p in BACKUP.glob("*.json"):
        shutil.copy2(p, GRAPHS / p.name)


def _sort_edge(e: list) -> tuple:
    if isinstance(e[0], list):
        s = tuple(_sort_edge(x)[0] if isinstance(x, list) else x for x in e[0])
    else:
        s = e[0]
    if isinstance(e[1], list):
        t = tuple(_sort_edge(x)[0] if isinstance(x, list) else x for x in e[1])
    else:
        t = e[1]
    return (json.dumps(s, sort_keys=True), json.dumps(t, sort_keys=True))


def normalize_graph(data: dict[str, Any]) -> dict[str, Any]:
    """Drop volatile keys; sort nodes/edges for stable comparison."""
    out = json.loads(json.dumps(data, ensure_ascii=False))
    for k in list(out.keys()):
        if k in SKIP_KEYS:
            out.pop(k, None)
    if isinstance(out.get("nodes"), list):
        nodes = [n for n in out["nodes"] if n not in ("START", "END")]
        nodes.sort()
        out["nodes"] = ["START"] + nodes + ["END"]
    if isinstance(out.get("edges"), list):
        edges = [list(e) for e in out["edges"]]
        edges.sort(key=_sort_edge)
        out["edges"] = edges
    if isinstance(out.get("bindings"), dict):
        out["bindings"] = dict(sorted(out["bindings"].items()))
    elif out.get("bindings") is None:
        out.pop("bindings", None)
    if not out.get("bindings"):
        out.pop("bindings", None)
    if isinstance(out.get("flowNodes"), dict):
        out["flowNodes"] = dict(sorted(out["flowNodes"].items()))
    return out


def graph_diff(a: dict, b: dict) -> str:
    na, nb = normalize_graph(a), normalize_graph(b)
    if na == nb:
        return ""
    keys = sorted(set(na.keys()) | set(nb.keys()))
    parts = []
    for k in keys:
        if na.get(k) != nb.get(k):
            parts.append(
                f"{k}: backup={json.dumps(na.get(k), ensure_ascii=False)[:120]} "
                f"!= saved={json.dumps(nb.get(k), ensure_ascii=False)[:120]}"
            )
    return "; ".join(parts[:8])


def graph_diff_canvas(backup: dict, canvas: dict) -> str:
    """Compare backup JSON to extractCanvasTopology() result (WYSIWYG)."""
    if not canvas:
        return "canvas topology missing"
    nb = normalize_graph(backup)
    nc = {
        "nodes": canvas.get("nodes") or [],
        "edges": canvas.get("edges") or [],
    }
    if isinstance(nc.get("nodes"), list):
        nodes = [n for n in nc["nodes"] if n not in ("START", "END")]
        nodes.sort()
        nc["nodes"] = ["START"] + nodes + ["END"]
    if isinstance(nc.get("edges"), list):
        edges = [list(e) for e in nc["edges"]]
        edges.sort(key=_sort_edge)
        nc["edges"] = edges
    parts = []
    if nb.get("nodes") != nc.get("nodes"):
        parts.append(
            f"nodes: backup={json.dumps(nb.get('nodes'), ensure_ascii=False)[:120]} "
            f"!= canvas={json.dumps(nc.get('nodes'), ensure_ascii=False)[:120]}"
        )
    if nb.get("edges") != nc.get("edges"):
        parts.append(
            f"edges: backup={json.dumps(nb.get('edges'), ensure_ascii=False)[:120]} "
            f"!= canvas={json.dumps(nc.get('edges'), ensure_ascii=False)[:120]}"
        )
    return "; ".join(parts[:4])


def load_graph_json(graph_id: str, *, from_backup: bool = False) -> dict:
    base = BACKUP if from_backup else GRAPHS
    return json.loads((base / f"{graph_id}.json").read_text(encoding="utf-8"))


def list_graph_ids(*, from_backup: bool = False) -> list[str]:
    base = BACKUP if from_backup else GRAPHS
    return sorted(p.stem for p in base.glob("*.json"))


if __name__ == "__main__":
    backup_graphs(force=True)
    ids = list_graph_ids(from_backup=True)
    print(f"Backed up {len(ids)} graphs to {BACKUP}")
