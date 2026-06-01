# tool_api.py
from flask import Blueprint, render_template, abort, request, jsonify
import json
from service.meta.loader import MetaLoader
from service.meta.tool_version import ToolVersionStore
from plugin.plugin_loader import get_plugin

tool_bp = Blueprint('tool', __name__, url_prefix='/tools')
version_store = ToolVersionStore()


def _save_tool_with_version(tool_id: str, data: dict, change_note: str = "", source: str = "save"):
    ok = MetaLoader.dump("tools", tool_id, data)
    if not ok:
        return {"success": False, "error": "failed to save tool"}
    saved = MetaLoader.load("tools", tool_id) or dict(data)
    snapshot = version_store.save_snapshot(
        tool_id,
        saved,
        change_note=change_note,
        source=source,
        created_by="ui",
    )
    return {"success": True, "id": tool_id, "version": snapshot.get("version"), "version_created": snapshot.get("created", False)}


@tool_bp.route('/')
def tool_list():
    tools = MetaLoader.loads("tools") or []
    tools.sort(key=lambda x: x.get('id', ''))
    return render_template("tool_list.html", tools=tools, active_page='tool')


@tool_bp.route('/api/list')
def tool_load_all():
    all_tools = MetaLoader.loads("tools") or []
    query = request.args.get('q', '').lower()
    tools = []
    for info in all_tools:
        tool_id = info.get("id", "")
        versions = version_store.list_versions(tool_id)
        item = {
            "id": tool_id,
            "name": info.get("name"),
            "description": info.get("description", ""),
            "version_count": len(versions),
            "latest_version": versions[0]["version"] if versions else None,
        }
        if query:
            haystack = " ".join([item.get("name", ""), tool_id, item.get("description", "")]).lower()
            if query not in haystack:
                continue
        tools.append(item)
    tools.sort(key=lambda x: x.get("id", ""))
    return jsonify(tools)


@tool_bp.route('/<tool_id>')
def tool_form(tool_id):
    tool = MetaLoader.load("tools", tool_id)
    if not tool:
        abort(404, description=f"Tool '{tool_id}' not found")
    return render_template("tool_form.html", tool=tool, tool_id=tool_id)


@tool_bp.route('/api/run_tool', methods=['POST'])
def run_tool():
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Invalid JSON payload"), 400

    tool_id = data.get('tool_id')
    inputs = data.get('inputs', {})

    tool_def = MetaLoader.load("tools", tool_id)
    if not tool_def:
        return jsonify(error="Tool not found"), 404

    code = tool_def.get('code')
    if not code:
        return jsonify(error="No executable code defined in tool"), 400

    local_ns = {}
    try:
        exec(code, globals(), local_ns)
        func = local_ns.get('func')
        if not callable(func):
            return jsonify(error="Code must define a callable named 'func'"), 400

        result = func(**inputs)

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

    change_note = tool_def.pop("change_note", "") if isinstance(tool_def, dict) else ""
    result = _save_tool_with_version(tool_id, tool_def, change_note=change_note, source="save")
    code = 200 if result.get("success") else 500
    return jsonify(result), code


@tool_bp.route('/api/<tool_id>', methods=['DELETE'])
def api_delete_tool(tool_id):
    if MetaLoader.delete("tools", tool_id):
        try:
            version_store.delete_all(tool_id)
        except Exception:
            pass
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404


@tool_bp.route('/api/<tool_id>/copy', methods=['POST'])
def api_copy_tool(tool_id):
    source = MetaLoader.load("tools", tool_id)
    if not source:
        return jsonify({"error": f"Tool '{tool_id}' not found"}), 404
    data = request.get_json(silent=True) or {}
    new_id = (data.get("id") or "").strip()
    if not new_id:
        return jsonify({"error": "Missing target id"}), 400
    if MetaLoader.exists("tools", new_id):
        return jsonify({"error": f"Tool '{new_id}' already exists"}), 409

    copied = dict(source)
    copied["name"] = data.get("name") or f"{source.get('name', tool_id)} (copy)"
    copied["description"] = data.get("description") or source.get("description", "")
    copied.pop("id", None)
    MetaLoader.dump("tools", new_id, copied)
    version_store.save_snapshot(
        new_id,
        copied,
        change_note=f"copied from {tool_id}",
        source="copy",
        created_by="ui",
    )
    return jsonify({"success": True, "id": new_id})


@tool_bp.route('/api/<tool_id>/versions', methods=['GET'])
def api_tool_versions(tool_id):
    versions = version_store.list_versions(tool_id)
    return jsonify({"tool_id": tool_id, "versions": versions})


@tool_bp.route('/api/<tool_id>/compare', methods=['POST'])
def api_compare_tool_versions(tool_id):
    data = request.json or {}
    left = data.get("left")
    right = data.get("right")
    if not left or not right:
        return jsonify({"error": "left and right version are required"}), 400
    result = version_store.compare(tool_id, left, right)
    if not result:
        return jsonify({"error": "Unable to compare versions"}), 404
    return jsonify(result)


@tool_bp.route('/del/<tool_id>')
def tool_del(tool_id):
    MetaLoader.delete("tools", tool_id)
    try:
        version_store.delete_all(tool_id)
    except Exception:
        pass
    tools = MetaLoader.loads("tools") or []
    tools.sort(key=lambda x: x.get('id', ''))
    return render_template("tool_list.html", tools=tools, active_page='tool')
