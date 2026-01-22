# agent_api.py
from flask import Blueprint, render_template, request, jsonify, abort
from service.entity.test import TestLoader
from service.meta.loader import MetaLoader

agent_bp = Blueprint('runner', __name__, url_prefix='/agents')


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
    return render_template("agent_form.html", agent=agent,
                           action="edit",
                           test_sets=test_sets,
                           active_page='runner')


# API
@agent_bp.route('/api/list')
def api_list():
    agents = MetaLoader.loads("agents")
    query = request.args.get('q', '').lower()
    if query:
        agents = [a for a in agents if query in a.get("name", "").lower() or query in a["id"]]
    return jsonify(agents)


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
    MetaLoader.dump("agents",agent_id, data)
    return jsonify({"success": True, "id": agent_id})


@agent_bp.route('/api/<agent_id>', methods=['PUT'])
def api_update(agent_id):
    data = request.json
    MetaLoader.dump("agents",agent_id, data)
    return jsonify({"success": True})


@agent_bp.route('/api/<agent_id>', methods=['DELETE'])
def api_delete(agent_id):
    if MetaLoader.delete("agents",agent_id):
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404

