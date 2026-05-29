# testset_api.py

from flask import Blueprint, render_template, request, jsonify, abort, redirect, url_for

from pathlib import Path

from ui.components.paginated_api import get_paginated_data

from service.entity.test import TestLoader, TEST_DIR

from service.dataset_cid import (
    DEFAULT_RE_RUNNER,
    build_tuning_dataset,
    list_raw_sources,
    list_split_outputs,
    sample_agent_csv_dataset,
)

testset_bp = Blueprint('testset', __name__, url_prefix='/testset')





@testset_bp.route('/')

def list_tests():

    runner_id = request.args.get('runner_id', DEFAULT_RE_RUNNER)

    all_tests = TestLoader.loads()

    if runner_id:

        all_tests = [t for t in all_tests if t.get('agent_id') == runner_id]



    page_tests_raw, page, per_page, total, search = get_paginated_data(

        all_tests,

        per_page=20,

        search_fields=['agent_id', 'name'],

    )



    page_tests = []

    for t in page_tests_raw:

        csv_path = TEST_DIR / t['agent_id'] / t['name']

        view_btn = ''

        if csv_path.is_file():

            view_btn = (

                f'<a href="{url_for("testset.view_structured", runner_id=t["agent_id"], filename=t["name"])}" '

                f'class="btn btn-sm btn-outline-primary">View</a> '

            )

        page_tests.append({

            'agent_id': t['agent_id'],

            'name': t['name'],

            'count': t['count'],

            'fields_display': ', '.join(t['inputs'].keys()) if t['inputs'] else 'N/A',

            'actions_html': f'''

                {view_btn}

                <form action="/testset/delete/{t['agent_id']}/{t['name']}"

                      method="post" style="display:inline;">

                    <button type="submit" class="btn btn-sm btn-danger"

                            onclick="return confirm('Sure to delete?')">Delete</button>

                </form>

            ''',

        })



    raw_sources = list_raw_sources()
    split_outputs = list_split_outputs(runner_id)
    agent_datasets = [
        {"name": t["name"], "count": t.get("count", 0)}
        for t in TestLoader.get_by_agent(runner_id)
        if (TEST_DIR / runner_id / t["name"]).is_file() and str(t["name"]).lower().endswith(".csv")
    ]

    return render_template(
        'testset_list.html',
        tests=page_tests,
        page=page,
        per_page=per_page,
        total=total,
        search=search,
        raw_sources=raw_sources,
        split_outputs=split_outputs,
        agent_datasets=agent_datasets,
        default_runner=runner_id,
        active_page='testset',
    )





@testset_bp.route('/api', methods=['GET'])

def api_list():

    tests = TestLoader.loads()

    agent_id = request.args.get('agent_id')

    if agent_id:

        tests = TestLoader.get_by_agent(agent_id)

    return jsonify(tests)





@testset_bp.route('/api/<agent_id>/<test_id>', methods=['GET'])

def api_get(agent_id, test_id):

    test = TestLoader.get_one(agent_id, test_id)

    if not test:

        abort(404)

    return jsonify(test)





@testset_bp.route('/api/<agent_id>/<test_id>', methods=['PUT'])

def api_update(agent_id, test_id):

    data = request.json

    if not TestLoader.get_one(agent_id, test_id):

        return jsonify({"error": "Test dataset not found"}), 404

    if not data.get("name"):

        return jsonify({"error": "Test name is required"}), 400

    TestLoader.save(agent_id, test_id, data)

    return jsonify({"success": True, "message": "Test dataset updated successfully"})





@testset_bp.route('/api/<agent_id>/<test_id>', methods=['DELETE'])

def api_delete(agent_id, test_id):

    if TestLoader.delete(agent_id, test_id):

        return jsonify({"success": True, "message": "Test dataset deleted successfully"})

    return jsonify({"error": "Test dataset not found"}), 404





@testset_bp.route('/api/by_agent/<agent_id>', methods=['GET'])

def api_get_by_agent(agent_id):

    return jsonify(TestLoader.get_by_agent(agent_id))





@testset_bp.route('/api/preview/<runner_id>/<filename>', methods=['GET'])

def api_testset_preview(runner_id, filename):

    fields, raw_data = TestLoader.load_by_id_file(runner_id, filename)

    if not raw_data:

        return jsonify({

            'fields': [],

            'items': [],

            'pagination': {'total': 0, 'page': 1, 'per_page': 20, 'total_pages': 0},

        })



    page_items, page, per_page, total, search = get_paginated_data(

        raw_data,

        per_page=int(request.args.get('per_page', 20)),

        search_fields=fields,

    )

    return jsonify({

        'fields': fields,

        'items': page_items,

        'pagination': {

            'page': page,

            'per_page': per_page,

            'total': total,

            'has_prev': page > 1,

            'has_next': page * per_page < total,

        },

    })





ALLOWED_EXT = {'.txt', '.csv', '.json'}





@testset_bp.route('/upload', methods=['POST'])

def upload_testset():

    runner_id = request.form['runner_id']

    file = request.files['file']

    if not file or file.filename == '':

        return redirect(url_for('testset.list_tests', runner_id=runner_id))

    ext = Path(file.filename).suffix.lower()

    if ext not in ALLOWED_EXT:

        return redirect(url_for('testset.list_tests', runner_id=runner_id))

    dir_path = TEST_DIR / runner_id

    dir_path.mkdir(parents=True, exist_ok=True)

    file.save(dir_path / file.filename)

    return redirect(url_for('testset.list_tests', runner_id=runner_id))





@testset_bp.route('/delete/<agent_id>/<path:filename>', methods=['POST'])

def delete_testset(agent_id, filename):

    csv_path = TEST_DIR / agent_id / filename

    if csv_path.is_file():

        csv_path.unlink()

    return redirect(url_for('testset.list_tests', runner_id=agent_id))





@testset_bp.route('/view/<runner_id>/<path:filename>')

def view_structured(runner_id, filename):

    csv_path = TEST_DIR / runner_id / filename

    if not csv_path.is_file():

        abort(404, description=f"Dataset file not found: {filename}")

    fields, raw_data = TestLoader.load_by_id_file(runner_id, filename)

    if not raw_data:

        abort(404)

    page_items, page, per_page, total, search = get_paginated_data(

        raw_data,

        per_page=int(request.args.get('per_page', 10)),

        search_fields=fields,

    )

    return render_template(

        'testset_view.html',

        runner_id=runner_id,

        filename=filename,

        fields=fields,

        items=page_items,

        page=page,

        per_page=per_page,

        total=total,

        search=search,

        active_page='testset',

    )





@testset_bp.route('/api/split', methods=['POST'])

def api_split_raw():

    """Split a raw PubTator source into tuning + test CSV for a runner."""

    data = request.get_json(silent=True) or {}

    runner_id = str(data.get('runner_id') or DEFAULT_RE_RUNNER).strip()

    source = str(data.get('source') or 'data/raw/dev.txt').strip()

    try:

        size = int(data.get('size') or 20)

    except ValueError:

        size = 20

    write_test_remain = bool(data.get('write_test_remain', True))

    stem = Path(source).stem.replace('.', '_')

    tuning_out = str(data.get('tuning_out') or f'{stem}_tuning.csv').strip()

    test_out = str(data.get('test_out') or f'{stem}_test.csv').strip()

    try:

        result = build_tuning_dataset(

            runner_id,

            source=source,

            size=size,

            tuning_out=tuning_out,

            test_out=test_out,

            write_test_remain=write_test_remain,

        )

        return jsonify({"success": True, "result": result})

    except Exception as ex:

        return jsonify({"success": False, "error": str(ex)}), 400


@testset_bp.route('/api/sample', methods=['POST'])
def api_sample_csv():
    """Randomly sample N rows from an existing agent CSV test dataset."""
    data = request.get_json(silent=True) or {}
    runner_id = str(data.get('runner_id') or DEFAULT_RE_RUNNER).strip()
    source_file = str(data.get('source') or data.get('source_file') or '').strip()
    if not source_file:
        return jsonify({"success": False, "error": "source test dataset is required"}), 400
    try:
        size = int(data.get('size') or data.get('count') or 5)
    except ValueError:
        size = 5
    try:
        seed = int(data.get('seed') or 42)
    except ValueError:
        seed = 42
    stem = Path(source_file).stem
    output_file = str(data.get('output') or data.get('output_file') or f'{stem}_sample_{size}_s{seed}.csv').strip()
    try:
        result = sample_agent_csv_dataset(
            runner_id,
            source_file,
            output_file,
            size=size,
            seed=seed,
        )
        return jsonify({"success": True, "result": result})
    except Exception as ex:
        return jsonify({"success": False, "error": str(ex)}), 400

