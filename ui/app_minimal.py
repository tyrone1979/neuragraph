#!/usr/bin/env python3
"""
NeuraGraph Minimal Flask - API layer without langchain/langgraph dependencies.
Uses run_workflow.py for execution (hand-rolled DAG executor).
"""

import json
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from run_workflow import STORE, GraphRunner, ConfigStore

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

META_DIR = Path(__file__).parent.parent / "meta"

# ── Load configs on startup ──
STORE.load(META_DIR)


# ── Health ──
@app.route("/api/stats")
def api_stats():
    return jsonify({
        "agents_count": len(STORE.agents),
        "graph_count": len(STORE.graphs),
        "tool_count": len(STORE.tools),
        "llms_count": len(STORE.llms),
        "exp_count": 0,
        "data_count": 0,
    })


# ── Agents ──
@app.route("/agents/api/list")
def agents_list():
    return jsonify(list(STORE.agents.values()))

@app.route("/agents/api/<id>")
def agents_get(id):
    return jsonify(STORE.agents.get(id) or {})

@app.route("/agents/api", methods=["POST"])
def agents_create():
    data = request.get_json() or {}
    cid = data.get("id")
    if cid:
        path = META_DIR / "agents" / f"{cid}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        STORE.agents[cid] = data
    return jsonify({"success": True, "id": cid})

@app.route("/agents/api/<id>", methods=["PUT"])
def agents_update(id):
    data = request.get_json() or {}
    path = META_DIR / "agents" / f"{id}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    STORE.agents[id] = data
    return jsonify({"success": True})

@app.route("/agents/api/<id>", methods=["DELETE"])
def agents_delete(id):
    path = META_DIR / "agents" / f"{id}.json"
    if path.exists():
        path.unlink()
    STORE.agents.pop(id, None)
    return jsonify({"success": True})


# ── Graphs ──
@app.route("/graph/api/list")
def graphs_list():
    return jsonify(list(STORE.graphs.values()))

@app.route("/graph/api/<id>")
def graphs_get(id):
    return jsonify(STORE.graphs.get(id) or {})

@app.route("/graph/api/save", methods=["POST"])
def graphs_save():
    data = request.get_json() or {}
    cid = data.get("id")
    if cid:
        path = META_DIR / "graphs" / f"{cid}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        STORE.graphs[cid] = data
    return jsonify({"success": True, "id": cid})

@app.route("/graph/api/delete/<id>", methods=["POST"])
def graphs_delete(id):
    path = META_DIR / "graphs" / f"{id}.json"
    if path.exists():
        path.unlink()
    STORE.graphs.pop(id, None)
    return jsonify({"success": True})


# ── LLMs ──
@app.route("/llms/api/list")
def llms_list():
    return jsonify(list(STORE.llms.values()))

@app.route("/llms/api", methods=["POST"])
def llms_create():
    data = request.get_json() or {}
    cid = data.get("id")
    if cid:
        path = META_DIR / "llms" / f"{cid}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        STORE.llms[cid] = data
    return jsonify({"success": True, "id": cid})

@app.route("/llms/api/<id>", methods=["PUT"])
def llms_update(id):
    data = request.get_json() or {}
    path = META_DIR / "llms" / f"{id}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    STORE.llms[id] = data
    return jsonify({"success": True})

@app.route("/llms/api/<id>", methods=["DELETE"])
def llms_delete(id):
    path = META_DIR / "llms" / f"{id}.json"
    if path.exists():
        path.unlink()
    STORE.llms.pop(id, None)
    return jsonify({"success": True})

@app.route("/llms/api/test", methods=["POST"])
def llms_test():
    data = request.get_json() or {}
    return jsonify({"success": True, "message": "LLM config saved (test skipped in minimal mode)"})


# ── Tools ──
@app.route("/tools/api/list")
def tools_list():
    return jsonify(list(STORE.tools.values()))

@app.route("/tools/api/save_tool", methods=["POST"])
def tools_save():
    data = request.get_json() or {}
    tool_id = data.get("tool_id")
    tool_def = data.get("tool_def", {})
    if tool_id:
        tool_def["id"] = tool_id
        path = META_DIR / "tools" / f"{tool_id}.json"
        path.write_text(json.dumps(tool_def, indent=2, ensure_ascii=False))
        STORE.tools[tool_id] = tool_def
    return jsonify({"success": True})

@app.route("/tools/del/<id>", methods=["POST"])
def tools_delete(id):
    path = META_DIR / "tools" / f"{id}.json"
    if path.exists():
        path.unlink()
    STORE.tools.pop(id, None)
    return jsonify({"success": True})


# ── Execute Workflow ──
@app.route("/api/execute/<graph_id>", methods=["POST"])
def execute_workflow(graph_id):
    inputs = request.get_json() or {}
    try:
        STORE.load(META_DIR)  # Reload configs
        runner = GraphRunner(graph_id, verbose=False)
        result = runner.run(inputs)
        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    print("=" * 60)
    print(" NeuraGraph Flask (Minimal)")
    print(f" Meta dir: {META_DIR}")
    print(f" Agents: {len(STORE.agents)}, Graphs: {len(STORE.graphs)}")
    print(f" LLMs: {len(STORE.llms)}, Tools: {len(STORE.tools)}")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5001, debug=False)
