import os
from pathlib import Path

from service.meta.loader import MetaLoader, GraphMetaLoader
from utils.graphutils import compute_states, compute_graph_global_inputs
from service.entity.test import TestLoader
from flask import render_template, Blueprint, request, jsonify

_UI_ROOT = Path(__file__).resolve().parent


graph_bp = Blueprint('graph', __name__, url_prefix='/graph')


def _editor_template_ctx():
    """Cache-bust static assets from file mtime (avoids stale JS/CSS after edits)."""
    js = _UI_ROOT / 'static' / 'js' / 'graph_visual_editor.js'
    css = _UI_ROOT / 'static' / 'css' / 'graph.css'
    try:
        editor_asset_ver = str(int(js.stat().st_mtime))
    except OSError:
        editor_asset_ver = '0'
    try:
        graph_css_ver = str(int(css.stat().st_mtime))
    except OSError:
        graph_css_ver = '0'
    return {'editor_asset_ver': editor_asset_ver, 'graph_css_ver': graph_css_ver}


def load_graph_by_id(graph_id: str):
    graphs = GraphMetaLoader.load(graph_id)
    test_sets = {}
    agents = {}
    for id, graph in graphs.items():
        test_sets = TestLoader.load_by_graph(graph, test_sets)
        agents = GraphMetaLoader.load_agents_by_graph(graph, agents)

    displayers = []
    flow_nodes = graphs[graph_id].get('flowNodes') or {}
    for node in graphs[graph_id]['nodes']:
        if node in flow_nodes:
            fk = flow_nodes[node].get('kind', 'flow')
            display = {
                'type': fk,
                'id': node,
                'display': f"{flow_nodes[node].get('name', node)} ({node}) - {fk.title()}",
            }
        elif node in agents:
            type = agents[node]['type']
            display = {
                'type': type,
                'id': node,
                'display': f"{agents[node]['name']} ({node}) - Agent" if type == 'agent' else
                f"{agents[node]['name']} ({node}) - Workflow"
            }
        else:
            display = {
                'type': "UNKNOWN",
                'id': node,
                'display': "UNKNOWN"
            }

        displayers.append(display)

    graphs['state'] = compute_states(graph_id)
    graphs['inputs'] = compute_graph_global_inputs(graph_id)
    return graphs, agents, test_sets, displayers

@graph_bp.route('/')
def list_graph():
    graphs = MetaLoader.loads("graphs")
    return render_template("graph_list.html", graphs=graphs, active_page='graph')

@graph_bp.route('/api/list')
def api_list_graphs():
    graphs = MetaLoader.loads("graphs")
    result = []
    for g in graphs:
        result.append({
            'id': g.get('id', ''),
            'name': g.get('name', g.get('id', '')),
            'description': g.get('description', ''),
            'nodes': g.get('nodes', []),
            'edges': g.get('edges', [])
        })
    return jsonify(result)


@graph_bp.route('/<graph_id>/edit', methods=['GET'])
def edit_graph(graph_id):
    graphs,agents,test_sets,displayers=load_graph_by_id(graph_id)
    return render_template(
        "graph.html",
        graphs=graphs,
        agents=agents,
        current=graph_id,
        test_sets=test_sets,
        is_edit=True,
        runner_displayers=displayers,
        active_page='graph',
        **_editor_template_ctx(),
    )

@graph_bp.route('/new', methods=['GET'])
def new_graph():
    return render_template(
        "graph.html",
        graphs={},
        agents={},
        current=None,
        test_sets={},
        is_new=True,
        active_page='graph',
        **_editor_template_ctx(),
    )


@graph_bp.route('/api/save', methods=['POST'])
def api_save_graph():
    """
    保存或更新一个 workflow 的配置
    前端预期发送的 JSON 示例：
    {
        "id": "my_graph",
        "name": "My Workflow",
        "description": "optional description",
        "nodes": ["START", "agent1", "sub_re", "agent2", "END"],
        "edges": [["START", "agent1"], ["agent1", "sub_re"], ["sub_re", "agent2"], ["agent2", "END"]]
    }
    """
    graph = request.get_json()
    if not graph:
        return jsonify({"error": "No JSON data provided"}), 400

    graph_id = graph.get("id")
    if not graph_id:
        return jsonify({"error": "Missing 'id' field"}), 400

    # 基本字段校验
    required = {"name", "nodes", "edges"}
    if not all(field in graph for field in required):
        missing = required - set(graph.keys())
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    # 额外轻量校验
    if not isinstance(graph["nodes"], list) or not isinstance(graph["edges"], list):
        return jsonify({"error": "nodes and edges must be lists"}), 400

    MetaLoader.dump("graphs",graph_id,graph)

    return jsonify({
        "success": True,
        "message": f"Graph '{graph_id}' saved successfully",
        "id": graph_id
    })


@graph_bp.route('/api/search_agent')
def search_agent():
    q = request.args.get('q', '').lower().strip()
    if not q:
        return jsonify({'results': []})

    agents = MetaLoader.loads("agents")
    graphs = MetaLoader.loads("graphs")
    results = []
    ids=[]
    # 搜索 graphs
    for g in graphs:
        gid = g.get('id', '')
        if q in g.get('name', '').lower() or q in gid.lower():
            ids.append(gid)
            graph_graphs, graph_agents, test_sets, _ = load_graph_by_id(gid)
            if MetaLoader.exists("graphs",gid):
                graph_agents[gid] = MetaLoader.load("agents",gid)
            results.append({
                'type': 'graph',
                'id': gid,
                'display': f"{g.get('name', gid)} ({gid}) - Workflow",
                'object':{
                    'graphs': graph_graphs,
                    'agents': graph_agents,
                    'test_sets': test_sets
                }
            })
    # 搜索 agents
    for agent in agents:
        if q in (agent.get('name', '') or '').lower() or q in agent['id'].lower():
            if agent['id'] in ids:
                continue
            if 'tools' in agent and agent['tools']:
                continue #The runner with tool cannot be in graph.
            test_sets=TestLoader.load_by_id(agent['id'])
            results.append({
                'type': 'agents',
                'id': agent['id'],
                'display': f"{agent.get('name', agent['id'])} ({agent['id']}) - Agent",
                'object': {
                    'agent': agent,
                    'test_sets':test_sets
                }
            })



    # 按相关度简单排序（匹配开头优先）
    results.sort(key=lambda x: 0 if x['id'].lower().startswith(q) or x['display'].lower().startswith(q) else 1)
    return jsonify({'results': results[:20]})  # 最多20条防刷


# ============= New Visual Editor API Endpoints =============

@graph_bp.route('/api/list')
def api_list_all_graphs():
    """List all graphs for the visual editor (subgraphs)"""
    graphs = MetaLoader.loads("graphs")
    result = []
    for g in graphs:
        graph_data = dict(g)
        graph_data['id'] = graph_data.get('id', '')
        result.append(graph_data)
    return jsonify(result)