"""Backup, diff, and discovery for workflow graph JSON under meta/graphs/."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
GRAPHS = ROOT / "meta" / "graphs"
BACKUP = ROOT / "meta" / "graphs_backup"

SKIP_KEYS = frozenset({"created_at", "id"})
# Editor saveGraph() adds these as {}; backups often omit them — treat as equivalent.
OPTIONAL_OBJECT_KEYS = frozenset({"agentVersions", "flowNodes"})

# Legacy fallbacks when tests/<graph_id>/*.csv is missing (see graph_run_params).
LEGACY_GRAPH_INPUTS: dict[str, dict[str, Any]] = {
    "wf_cid_ner_llm_eval": {
        "text": "Aspirin may reduce the risk of heart disease.",
        "labels": "Chemical,Disease",
        "expected_entities": json.dumps({"Chemical": ["Aspirin"], "Disease": ["heart disease"]}),
    },
    "wf_cid_ner_flair_eval": {
        "text": "Aspirin may reduce the risk of heart disease.",
        "labels": "Chemical,Disease",
        "expected_entities": json.dumps({"Chemical": ["Aspirin"], "Disease": ["heart disease"]}),
    },
    "wf_cid_re_llm_linear": {
        "text": "Aspirin may cause headache.",
        "labels": "Chemical,Disease",
    },
    "wf_cid_re_llm_linear_opt_20260529_143039_r2": {
        "text": "Aspirin may cause headache.",
        "labels": "Chemical,Disease",
    },
    "wf_cid_re_branch": {
        "text": "Aspirin may cause headache.",
        "labels": "Chemical,Disease",
    },
    "wf_doc_ner_llm_eval": {
        "text": "Aspirin may reduce the risk of heart disease.",
        "labels": "Chemical, Disease",
        "expected_entities": json.dumps({"Chemical": ["Aspirin"], "Disease": ["heart disease"]}),
    },
    "wf_doc_ner_flair_eval": {
        "text": "Aspirin may reduce the risk of heart disease.",
        "labels": "Chemical,Disease",
        "expected_entities": json.dumps({"Chemical": ["Aspirin"], "Disease": ["heart disease"]}),
    },
    "wf_doc_ner_loop_branch": {
        "text": "Aspirin treats pain. Metformin treats diabetes.",
        "labels": "Chemical,Disease",
        "expected_entities": json.dumps({"Chemical": ["Aspirin", "Metformin"]}),
    },
    "wf_doc_re_nested_branch": {
        "text": "Aspirin may reduce the risk of heart disease.",
        "labels": "Chemical,Disease",
    },
    "wf_general_report_linear": {"text": "Aspirin is used to treat pain and inflammation."},
    "wf_kg_llm_full": {
        "text": "Aspirin may reduce the risk of heart disease.",
        "labels": "Chemical,Disease",
    },
    "wf_kg_flair_full": {
        "text": "Aspirin may reduce the risk of heart disease.",
        "labels": "Chemical,Disease",
    },
    "wf_kg_syntax_loop": {"text": "Aspirin treats pain.", "doc_id": "sample1"},
    "wf_re_verify_llm_loop": {
        "text": "Aspirin may cause headache.",
        "expected_entities": json.dumps({"Chemical": ["Aspirin"], "Disease": ["headache"]}),
        "expected_relations": "Aspirin|causes|headache",
        "entity_link": json.dumps({"Aspirin": "Aspirin", "headache": "headache"}),
    },
    "wf_word_seg_llm_eval": {
        "text": "Biomedical text mining.",
        "expected": "Biomedical| |text| |mining| |.",
    },
    "sg_ner_flair_sent": {"sentence": "Aspirin treats pain.", "labels": "Chemical,Disease"},
    "sg_ner_llm_tree": {"sentence": "Aspirin treats pain.", "labels": "Chemical,Disease"},
    "sg_re_tree": {"sentence": "Aspirin treats pain."},
    "sg_cid_re_verify": {
        "text": "Aspirin may reduce the risk of heart disease.",
        "head": "Aspirin",
        "tail": "heart disease",
        "head_id": "D001241",
        "tail_id": "D006331",
    },
    "sg_relation_verify": {
        "text": "Aspirin may cause headache.",
        "head": "Aspirin",
        "tail": "headache",
        "entity_link": json.dumps({"Aspirin": "Aspirin", "headache": "headache"}),
    },
    "sg_preprocess_inner": {"text": "Sample line."},
    "sg_re_preprocess": {"text": "Aspirin treats pain."},
}

DEFAULT_GRAPH_INPUT: dict[str, Any] = {
    "text": "Aspirin may reduce the risk of heart disease.",
    "labels": "Chemical,Disease",
}

LLM_GRAPH_TIMEOUT = 420
FAST_GRAPH_TIMEOUT = 90


def discover_graph_ids(*, from_backup: bool = False) -> list[str]:
    """All workflow JSON ids under meta/graphs or meta/graphs_backup."""
    return list_graph_ids(from_backup=from_backup)


def _project_graphutils():
    """Load utils/graphutils.py without conflicting with ui_tests.utils."""
    import importlib.util

    path = ROOT / "utils" / "graphutils.py"
    spec = importlib.util.spec_from_file_location("project_graphutils", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load graphutils from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def graph_ids_for_testing(*, from_backup: bool = False) -> list[str]:
    """One graph id per workflow family (highest version), for suites and pruning."""
    gu = _project_graphutils()
    return gu.select_representative_graph_ids(discover_graph_ids(from_backup=from_backup))


def graph_run_params(graph_id: str) -> dict[str, Any]:
    """Stream test payload: tests/<id>/*.csv first, then legacy map, then default."""
    from service.entity.test import TestLoader

    row = TestLoader.workflow_test_input(graph_id)
    if row:
        return row
    legacy = LEGACY_GRAPH_INPUTS.get(graph_id)
    if legacy:
        return dict(legacy)
    return dict(DEFAULT_GRAPH_INPUT)


def graph_run_params_for_query(graph_id: str) -> dict[str, str]:
    """GET /stream/test query params: JSON-encode list/dict (not Python repr)."""
    row = graph_run_params(graph_id)
    out: dict[str, str] = {}
    for key, val in row.items():
        if isinstance(val, (list, dict)):
            out[key] = json.dumps(val, ensure_ascii=False)
        elif val is None:
            continue
        else:
            out[key] = str(val)
    return out


def estimate_cid_verify_pairs(params: dict[str, Any]) -> int | None:
    """Upper-bound C–D pairs after cid_pair_generate (unique MeSH ids per label)."""
    entities = params.get("entities")
    if isinstance(entities, str):
        try:
            entities = json.loads(entities)
        except json.JSONDecodeError:
            return None
    if not isinstance(entities, list):
        return None
    chem: set[str] = set()
    dis: set[str] = set()
    for ent in entities:
        if not isinstance(ent, dict):
            continue
        lbl = ent.get("label") or ent.get("type") or ""
        eid = ent.get("id") or ent.get("mesh") or ""
        if not eid:
            continue
        if lbl == "Chemical":
            chem.add(eid)
        elif lbl == "Disease":
            dis.add(eid)
    return len(chem) * len(dis)


def graph_run_cost_hint(graph_id: str, params: dict[str, Any]) -> str:
    """Human-readable note before G4 stream (why a graph may take minutes)."""
    if graph_id == "wf_cid_re_llm_linear":
        n = estimate_cid_verify_pairs(params)
        if n is None:
            return "1× hypernym LLM + N× loop verify (sg_cid_re_verify, each = 1× relation_verify LLM)"
        return (
            f"1× ontology_hypernym_filter LLM + up to {n}× loop verify "
            f"(sg_cid_re_verify → relation_verify_llm); SSE may be silent until each node finishes"
        )
    if graph_id.startswith("wf_") and "llm" in graph_id:
        return "multi-node workflow with real LLM calls; stream may buffer until subgraph steps complete"
    if graph_id.startswith("sg_"):
        return "single subgraph; usually finishes in under a minute if LLM/API healthy"
    return ""


def graph_run_timeout(graph_id: str) -> int:
    if graph_id.startswith("sg_"):
        return FAST_GRAPH_TIMEOUT
    return LLM_GRAPH_TIMEOUT


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
    for key in OPTIONAL_OBJECT_KEYS:
        val = out.get(key)
        if val is None or (isinstance(val, dict) and len(val) == 0):
            out.pop(key, None)
        elif isinstance(val, dict):
            out[key] = dict(sorted(val.items()))
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


def branch_nodes_with_min_conditions(graph_id: str, *, min_conditions: int = 3) -> list[tuple[str, int]]:
    """Return [(flow_node_id, condition_count), ...] for branch flow nodes."""
    try:
        data = load_graph_json(graph_id, from_backup=False)
    except FileNotFoundError:
        return []
    out: list[tuple[str, int]] = []
    for node_id, fn in (data.get("flowNodes") or {}).items():
        if not isinstance(fn, dict) or fn.get("kind") != "branch":
            continue
        n = len(fn.get("conditions") or [])
        if n >= min_conditions:
            out.append((node_id, n))
    return out


if __name__ == "__main__":
    backup_graphs(force=True)
    ids = discover_graph_ids(from_backup=True)
    print(f"Backed up {len(ids)} graphs to {BACKUP}")
