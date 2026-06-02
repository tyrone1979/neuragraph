# agent_api.py
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify, abort
from langchain_core.runnables import RunnableConfig
from service.entity.test import TestLoader
from service.entity.runner import RunnerLoader
from service.meta.loader import MetaLoader
from service.meta.agent_version import AgentVersionStore
from utils.graphutils import count_agent_workflow_references

agent_bp = Blueprint('runner', __name__, url_prefix='/agents')
version_store = AgentVersionStore()


def _save_agent_with_version(agent_id: str, data: dict, change_note: str = "", source: str = "save"):
    ok = MetaLoader.dump("agents", agent_id, data)
    if not ok:
        return {"success": False, "error": "failed to save agent"}
    saved = MetaLoader.load("agents", agent_id) or dict(data)
    snapshot = version_store.save_snapshot(
        agent_id,
        saved,
        change_note=change_note,
        source=source,
        created_by="ui",
    )
    return {"success": True, "id": agent_id, "version": snapshot.get("version"), "version_created": snapshot.get("created", False)}


@agent_bp.route('/')
def list_agents():
    agents = MetaLoader.loads("agents")
    return render_template("agent_list.html", agents=agents, active_page='runner')


@agent_bp.route('/new')
def new_agent():
    return render_template("agent_form.html", agent=None, test_sets=None,action="create", active_page='runner')


@agent_bp.route('/<agent_id>/edit')
def edit_agent(agent_id):
    agent = MetaLoader.load("agents",agent_id)
    test_sets=TestLoader.load_by_id(agent_id)
    if not agent:
        abort(404)
    agent["id"] = agent_id
    workflow_ref_counts = count_agent_workflow_references()
    versions = version_store.list_versions(agent_id)
    agent["workflow_ref_count"] = workflow_ref_counts.get(agent_id, 0)
    agent["version_count"] = len(versions)
    return render_template("agent_form.html", agent=agent,
                           action="edit",
                           test_sets=test_sets,
                           active_page='runner')


# API
@agent_bp.route('/api/list')
def api_list():
    agents = MetaLoader.loads("agents") or []
    workflow_ref_counts = count_agent_workflow_references()
    query = request.args.get('q', '').lower()
    result = []
    for agent in agents:
        agent_id = agent.get("id", "")
        versions = version_store.list_versions(agent_id)
        item = {
            **agent,
            "version_count": len(versions),
            "latest_version": versions[0]["version"] if versions else None,
            "workflow_ref_count": workflow_ref_counts.get(agent_id, 0),
        }
        if query:
            haystack = " ".join([
                item.get("name", ""),
                agent_id,
                item.get("type", ""),
                item.get("model", ""),
                str(item.get("workflow_ref_count", 0)),
            ]).lower()
            if query not in haystack:
                continue
        result.append(item)
    return jsonify(result)


@agent_bp.route('/api/<agent_id>', methods=['GET'])
def api_get(agent_id):
    agent = MetaLoader.load("agents",agent_id)
    if not agent:
        abort(404)
    agent["id"] = agent_id
    return jsonify(agent)


@agent_bp.route('/api', methods=['PUT'])
def api_create():
    data = request.json
    agent_id = data.get("id")
    if not agent_id:
        return jsonify({"error": "Missing agent id"}), 400
    change_note = (data or {}).pop("change_note", "")
    result = _save_agent_with_version(agent_id, data, change_note=change_note, source="create")
    code = 200 if result.get("success") else 500
    return jsonify(result), code


@agent_bp.route('/api/<agent_id>', methods=['PUT'])
def api_update(agent_id):
    data = request.json
    change_note = (data or {}).pop("change_note", "")
    result = _save_agent_with_version(agent_id, data, change_note=change_note, source="update")
    code = 200 if result.get("success") else 500
    return jsonify(result), code


@agent_bp.route('/api/save', methods=['POST'])
def api_save():
    """Save agent changes from visual editor"""
    data = request.json
    agent_id = data.get("id")
    if not agent_id:
        return jsonify({"error": "Missing agent id"}), 400
    change_note = data.pop("change_note", "")
    result = _save_agent_with_version(agent_id, data, change_note=change_note, source="save")
    code = 200 if result.get("success") else 500
    return jsonify(result), code


@agent_bp.route('/api/<agent_id>', methods=['DELETE'])
def api_delete(agent_id):
    if MetaLoader.delete("agents",agent_id):
        try:
            version_store.delete_all(agent_id)
        except Exception:
            pass
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404


@agent_bp.route('/api/<agent_id>/copy', methods=['POST'])
def api_copy_agent(agent_id):
    source = MetaLoader.load("agents", agent_id)
    if not source:
        return jsonify({"error": f"Agent '{agent_id}' not found"}), 404
    data = request.get_json(silent=True) or {}
    new_id = (data.get("id") or "").strip()
    if not new_id:
        return jsonify({"error": "Missing target id"}), 400
    if MetaLoader.exists("agents", new_id):
        return jsonify({"error": f"Agent '{new_id}' already exists"}), 409

    copied = dict(source)
    copied["name"] = data.get("name") or f"{source.get('name', agent_id)} (copy)"
    copied.pop("id", None)
    MetaLoader.dump("agents", new_id, copied)
    version_store.save_snapshot(
        new_id,
        copied,
        change_note=f"copied from {agent_id}",
        source="copy",
        created_by="ui",
    )
    return jsonify({"success": True, "id": new_id})


@agent_bp.route('/api/<agent_id>/versions', methods=['GET'])
def api_versions(agent_id):
    versions = version_store.list_versions(agent_id)
    return jsonify({"agent_id": agent_id, "versions": versions})


@agent_bp.route('/api/<agent_id>/versions/<version>', methods=['GET'])
def api_get_version(agent_id, version):
    payload = version_store.load_version(agent_id, version)
    if not payload:
        return jsonify({"error": "Version not found"}), 404
    return jsonify(payload)


@agent_bp.route('/api/<agent_id>/compare', methods=['POST'])
def api_compare_versions(agent_id):
    data = request.json or {}
    left = data.get("left")
    right = data.get("right")
    if not left or not right:
        return jsonify({"error": "left and right version are required"}), 400
    result = version_store.compare(agent_id, left, right)
    if not result:
        return jsonify({"error": "Unable to compare versions"}), 404
    return jsonify(result)


@agent_bp.route('/api/<agent_id>/test', methods=['POST'])
def api_test_agent(agent_id):
    """Run agent invoke once; return structured state (no SSE reasoning noise)."""
    data = request.json or {}
    inputs = dict(data.get("inputs") or {})
    runner = RunnerLoader.load(agent_id)
    if runner is None:
        return jsonify({"success": False, "error": f"Agent '{agent_id}' not found"}), 404
    config: RunnableConfig = {
        "configurable": {"thread_id": f"ui_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"}
    }
    try:
        result = runner.invoke(inputs, config=config)
        return jsonify({"success": True, "result": result})
    except Exception as ex:
        return jsonify({"success": False, "error": str(ex)}), 500


@agent_bp.route('/api/<agent_id>/rollback', methods=['POST'])
def api_rollback(agent_id):
    data = request.json or {}
    version = data.get("version")
    if not version:
        return jsonify({"error": "version is required"}), 400
    rollback = version_store.rollback(
        agent_id,
        version,
        change_note=data.get("change_note", ""),
        created_by="ui",
    )
    if not rollback:
        return jsonify({"error": "Version not found"}), 404
    MetaLoader.dump("agents", agent_id, rollback["content"])
    return jsonify(
        {
            "success": True,
            "id": agent_id,
            "rolled_back_to": version,
            "new_version": rollback["snapshot"].get("version"),
            "version_created": rollback["snapshot"].get("created", False),
        }
    )

