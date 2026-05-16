from flask import Blueprint, request, jsonify
from service.meta.loader import MetaLoader

common_bp = Blueprint('common', __name__, url_prefix='/common')

@common_bp.route('/api/search_runners')
def search_runners():
    q = request.args.get('q', '').lower().strip()
    if not q:
        return jsonify({'results': []})

    agents = MetaLoader.loads("agents")
    graphs = MetaLoader.loads("graphs")

    results = []

    # 搜索 agents
    for agent in agents:
        if q in (agent.get('name', '') or '').lower() or q in agent['id'].lower():
            results.append({
                'type': 'runner',
                'id': agent['id'],
                'display': f"{agent.get('name', agent['id'])} ({agent['id']}) - Agent"
            })

    # 搜索 graphs
    for g in graphs:
        gid = g.get('id', '')
        if q in g.get('name', '').lower() or q in gid.lower():
            results.append({
                'type': 'graph',
                'id': gid,
                'display': f"{g.get('name', gid)} ({gid}) - Workflow"
            })

    # 按相关度简单排序（匹配开头优先）
    results.sort(key=lambda x: 0 if x['id'].lower().startswith(q) or x['display'].lower().startswith(q) else 1)

    return jsonify({'results': results[:20]})  # 最多20条防刷