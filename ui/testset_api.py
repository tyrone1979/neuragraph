# testset_api.py
from flask import Blueprint, render_template, request, jsonify, abort, redirect
from pathlib import Path
from ui.components.paginated_api import get_paginated_data
from service.entity.test import TestLoader, TEST_DIR
testset_bp = Blueprint('testset', __name__, url_prefix='/testset')



@testset_bp.route('/')
def list_tests():
    all_tests = TestLoader.loads()
    # 用工具分页 + 搜索（agent_id 和 name）
    # 分页 + 搜索 + 排序
    page_tests_raw, page, per_page, total, search = get_paginated_data(
        all_tests,
        per_page=20,
        search_fields=['agent_id', 'name']
    )
    page_tests = []
    for t in page_tests_raw:
        test_dict = {
            'agent_id': t['agent_id'],
            'name': t['name'],
            'count': t['count'],
            'fields_display': ', '.join(t['inputs'].keys()) if t['inputs'] else 'N/A',
            'actions_html': f'''
                        <form action="/testset/delete/{t['agent_id']}/{t['name']}"
                              method="post" style="display:inline;">
                            <button type="submit" class="btn btn-sm btn-danger" 
                                    onclick="return confirm('Sure to delete?')">Delete</button>
                        </form>
                    '''
        }
        page_tests.append(test_dict)
    return render_template("testset_list.html",
                           tests=page_tests,
                           page=page,
                           per_page=per_page,
                           total=total,
                           active_page='testset')


# API 路由
@testset_bp.route('/api', methods=['GET'])
def api_list():
    """获取所有测试数据集（API）"""
    tests = TestLoader.loads()
    agent_id = request.args.get('agent_id')
    if agent_id:
        tests = TestLoader.get_by_agent(agent_id)
    return jsonify(tests)


@testset_bp.route('/api/<agent_id>/<test_id>', methods=['GET'])
def api_get(agent_id, test_id):
    """获取单个测试数据集"""
    test = TestLoader.get_one(agent_id, test_id)
    if not test:
        abort(404)
    return jsonify(test)


@testset_bp.route('/api', methods=['POST'])
def api_create():
    """创建测试数据集"""
    data = request.json

    # 验证必要字段
    if not data.get("name"):
        return jsonify({"error": "Test name is required"}), 400

    if not data.get("agent_id"):
        return jsonify({"error": "Agent ID is required"}), 400

    # 生成test_id（使用名称，但替换空格和特殊字符）
    test_id = data["name"].replace(" ", "_").replace("/", "_").replace("\\", "_")

    # 检查是否已存在
    existing_test = TestLoader.get_one(data["agent_id"], test_id)
    if existing_test:
        return jsonify({"error": f"Test dataset '{data['name']}' already exists for this runner"}), 409

    # 保存测试数据
    TestLoader.save(data["agent_id"], test_id, data)

    return jsonify({
        "success": True,
        "id": test_id,
        "agent_id": data["agent_id"],
        "message": "Test dataset created successfully"
    })


@testset_bp.route('/api/<agent_id>/<test_id>', methods=['PUT'])
def api_update(agent_id, test_id):
    """更新测试数据集"""
    data = request.json

    if not TestLoader.get_one(agent_id, test_id):
        return jsonify({"error": "Test dataset not found"}), 404

    # 确保ID一致
    if data.get("id") and data["id"] != test_id:
        return jsonify({"error": "Test ID cannot be changed"}), 400

    if data.get("agent_id") and data["agent_id"] != agent_id:
        return jsonify({"error": "Agent ID cannot be changed"}), 400

    # 验证必要字段
    if not data.get("name"):
        return jsonify({"error": "Test name is required"}), 400

    # 保存更新
    TestLoader.save(agent_id, test_id, data)

    return jsonify({
        "success": True,
        "message": "Test dataset updated successfully"
    })


@testset_bp.route('/api/<agent_id>/<test_id>', methods=['DELETE'])
def api_delete(agent_id, test_id):
    if TestLoader.delete(agent_id, test_id):
        return jsonify({
            "success": True,
            "message": "Test dataset deleted successfully"
        })

    return jsonify({"error": "Test dataset not found"}), 404


@testset_bp.route('/api/by_agent/<agent_id>', methods=['GET'])
def api_get_by_agent(agent_id):
    """根据Agent ID获取相关测试数据集"""
    tests = TestLoader.get_by_agent(agent_id)
    return jsonify(tests)

@testset_bp.route('/api/preview/<runner_id>/<filename>', methods=['GET'])
def api_testset_preview(runner_id, filename):
    """
    返回指定 testset 文件的分页数据，用于 experiment.html 预览
    支持 ?page= & per_page= & search=
    """
    # 1. 加载文件数据
    fields, raw_data = TestLoader.load_by_id_file(runner_id, filename)  # 你现有的函数，返回 fields list + data list[dict]

    if not raw_data:
        return jsonify({
            'fields': [],
            'items': [],
            'pagination': {'total': 0, 'page': 1, 'per_page': 20, 'total_pages': 0}
        })

    # 2. 分页 + 搜索（复用工具）
    page_items, page, per_page, total, search = get_paginated_data(
        raw_data,
        per_page=int(request.args.get('per_page', 20)),
        search_fields=fields  # 支持所有字段搜索
    )

    # 3. 返回标准结构
    return jsonify({
        'fields': fields,
        'items': page_items,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'has_prev': page > 1,
            'has_next': page * per_page < total
        }
    })

ALLOWED_EXT = {'.txt', '.csv', '.json'}


@testset_bp.route('/upload', methods=['POST'])
def upload_testset():
    runner_id = request.form['runner_id']
    file = request.files['file']

    if not file or file.filename == '':
        return "No file", 400

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        return "Invalid file type", 400

    dir_path = TEST_DIR / runner_id
    dir_path.mkdir(parents=True, exist_ok=True)
    file.save(dir_path / file.filename)

    return redirect('/testset/')