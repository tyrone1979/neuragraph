# tool_api.py
from flask import Blueprint, render_template, abort, request, jsonify
import json
from service.meta.loader import MetaLoader
from plugin.plugin_loader import get_plugin

tool_bp = Blueprint('tool', __name__, url_prefix='/tools')


# ==================== 工具列表页 ====================
@tool_bp.route('/')
def tool_list():
    """渲染 tool_list.html，列出所有工具"""
    tools = MetaLoader.loads("tools")
    # 按文件名排序，便于查看
    tools.sort(key=lambda x: x['id'])
    return render_template("tool_list.html", tools=tools, active_page='tool')

@tool_bp.route('/api/list')
def tool_load_all():
    all_tools =MetaLoader.loads("tools")
    tools = [
        {
            "id": info['id'],
            "name": info.get("name"),
            "description": info.get("description", "")
        }
        for info in all_tools
    ]
    return jsonify(tools)

# ==================== 单个工具表单页 ====================
@tool_bp.route('/<tool_id>')
def tool_form(tool_id):
    """渲染 tool_form.html"""
    tool = MetaLoader.load("tools",tool_id)
    if not tool:
        abort(404, description=f"Tool '{tool_id}' not found")
    return render_template("tool_form.html", tool=tool, tool_id=tool_id)

# ==================== API：运行工具 ====================
@tool_bp.route('/api/run_tool', methods=['POST'])
def run_tool():
    """接收前端数据，动态执行工具代码"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Invalid JSON payload"), 400

    tool_id = data.get('tool_id')
    inputs = data.get('inputs', {})

    tool_def = MetaLoader.load("tools",tool_id)
    if not tool_def:
        return jsonify(error="Tool not found"), 404

    code = tool_def.get('code')
    if not code:
        return jsonify(error="No executable code defined in tool"), 400

    local_ns = {}
    try:
        # 注意：exec 只在完全可信环境使用！
        exec(code, globals(), local_ns)
        func = local_ns.get('func')
        if not callable(func):
            return jsonify(error="Code must define a callable named 'func'"), 400

        result = func(**inputs)

        # 美化返回结果
        if isinstance(result, (dict, list)):
            result_str = json.dumps(result, ensure_ascii=False, indent=2)
        else:
            result_str = str(result)

        return jsonify(result=result_str)

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[Tool Exec Error] {tool_id}: {tb}")
        return jsonify(error=str(e)), 500


@tool_bp.route('/new')
def tool_new():
    # 新建模式：传一个空的 tool 模板
    empty_tool = {
        "id": "",
        "name": "",
        "description": "",
        "parameters": {
            "properties": {},
            "required": []
        },
        "code": "def func(**kwargs):\n    # Your code here\n    return kwargs"
    }
    return render_template("tool_form.html", tool=empty_tool, tool_id="")



@tool_bp.route('/api/save_tool', methods=['POST'])
def save_tool():
    data = request.get_json()
    tool_id = data.get('tool_id')
    tool_def = data.get('tool_def')

    if not tool_id or not isinstance(tool_def, dict):
        return jsonify(error="Invalid tool_id or tool_def"), 400

    try:
        MetaLoader.dump("tools", tool_id,tool_def)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(error=str(e)), 500

@tool_bp.route('/del/<tool_id>')
def tool_del(tool_id):
    # 新建模式：传一个空的 tool 模板
    MetaLoader.delete("tools",tool_id)
    tools = MetaLoader.loads("tools")
    tools.sort(key=lambda x: x['id'])
    return render_template("tool_list.html", tools=tools, active_page='tool')
