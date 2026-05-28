# exp_api.py
from flask import Blueprint,  render_template, request, jsonify, Response
import uuid
import json
import time
import threading
from datetime import datetime
from ui.components.paginated_api import get_paginated_data
from service.result.loader import ResultLoader
from dataclasses import is_dataclass,asdict
from langchain_core.runnables import RunnableConfig

from service.entity.test import TestLoader
from service.meta.loader import MetaLoader
from service.entity.runner import RunnerLoader
from service.experiment_optimize import (
    run_optimize_loop_by_exp,
    run_optimize_loop_by_exp_with_progress,
)
exp_bp = Blueprint('exp', __name__, url_prefix='/exp')

_optimize_tasks: dict[str, dict] = {}
_optimize_lock = threading.Lock()

def render_list(search='',page=1,per_page=20):
    all_history = MetaLoader.loads("exps")  # 你的函数，返回 list of dict
    all_history.sort(key=lambda d: d.get("created_at") or "1970-01-01T00:00:00", reverse=True)
    # 搜索：runner 或 dataset
    if search:
        search_lower = search.lower()
        all_history = [e for e in all_history
                       if search_lower in e.get('config', {}).get('runner', '').lower()
                       or search_lower in e.get('config', {}).get('dataset', '').lower()]

    total = len(all_history)
    start = (page - 1) * per_page
    end = start + per_page
    page_history = all_history[start:end]

    # 预处理显示字段
    processed = []
    for e in page_history:
        item = {
            'name': f'<a href="/exp/{e["exp_id"]}" class="text-decoration-none fw-bold">{e["name"] or "Untitled"}</a>',
            'runner': f'<code class="small text-muted">{e.get("runner_id", "N/A")}</code>',
            'type': f'<span class="badge text-bg-secondary">{e["runner_type"].upper()}</span>',
            'dataset_file': f'<span class="text-monospace small">{e["dataset"]}</span>',
            'samples': f'<strong>{e["samples"]:,}</strong>',  # 千分位分隔，数字好看
            'created_at': f'<span class="text-muted small">{e["created_at"][:19].replace("T", " ")}</span>',
            'status': {
                'completed': '<span class="badge text-bg-success">Completed</span>',
                'running': '<span class="badge text-bg-primary">Running</span>',
                'pending': '<span class="badge text-bg-warning">Pending</span>',
                'failed': '<span class="badge text-bg-danger">Failed</span>',
            }.get(e.get('status', 'unknown').lower(), '<span class="badge text-bg-secondary">Unknown</span>'),
            'actions': f'''
                <a href="/exp/delete/{e["exp_id"]}" class="btn btn-outline-danger" title="Delete" 
                       onclick="return confirm('Please confirm to delete.')">
                        <i class="fas fa-trash"></i>
                </a>
            '''
        }
        processed.append(item)

    return render_template(
        'experiment_list.html',
        history=processed,
        page=page,
        per_page=per_page,
        total=total,
        search=search,
        active_page='exp'
    )

def render_html(template, runner_id,test_file,runner_type,runner_display, progress,exp_id,**extra_context):
    graphs = MetaLoader.loads("graphs")  # 或你原来的加载方式，返回 dict
    agents = MetaLoader.loads("agents")

    preview_page = 1
    preview_per_page = 10
    preview_total = 0
    fields=[]
    preview_items=[]
    tests=[]
    snapshots={}

    if runner_id and test_file:
        tests = TestLoader.get_by_agent(runner_id)
        fields, raw_data = TestLoader.load_by_id_file(runner_id, test_file)

        # 分页
        page_items, preview_page, preview_per_page, preview_total, _ = get_paginated_data(
                raw_data,
                per_page=preview_per_page,
                search_fields=fields
            )
        results=ResultLoader.load(exp_id)
        for idx, item in enumerate(page_items, start=(preview_page - 1) * preview_per_page + 1):
            if is_dataclass(item):
                # 如果是 dataclass，使用 asdict() 转换为字典
                item_dict = asdict(item)
            else:
                item_dict = dict(item)  # 转 dict 方便加字段
            item_dict['#'] = idx  # 第一列序号
            idx_str=str(idx)
            if results and idx_str in results:
                item_dict['status'] = '<span class="badge text-bg-success">Completed</span>'
                item_dict['actions'] = f'''<a class="btn btn-outline-info btn-replay" title="Replay" data-index='{idx}'>
                                                                                              <i class="fas fa-play"></i></a>'''
                # Keep inline JSON small (full state can be MB for long CID articles).
                row_result = results[idx_str]
                if isinstance(row_result, dict) and "metrics" in row_result:
                    snapshots[idx] = {"metrics": row_result["metrics"]}
                else:
                    snapshots[idx] = row_result
            else:
                item_dict['status'] = '<span class="badge text-bg-warning">Pending</span>'
                item_dict['actions'] = ''
            preview_items.append(item_dict)

    display_fields=['#']+fields+['status','actions']
    # 构建extra_params字典
    extra_params = {}
    if runner_id:
        extra_params['runner_id'] = runner_id
    if runner_type:
        extra_params['runner_type'] = runner_type
    if runner_display:
        extra_params['runner_display'] = runner_display
    if test_file:
        extra_params['filename'] = test_file


    # Client JS only needs filenames + counts (full row payloads break inline JSON / bloat DOM).
    dataset_options = [{"name": t["name"], "count": t["count"]} for t in tests]
    base_context = {
        'datasets': dataset_options,
        'active_page': 'exp',
        'runner_type': runner_type,
        'runner_id': runner_id,
        'runner_display': runner_display,
        'filename': test_file,
        'preview_tests': preview_items,
        'preview_page': preview_page,
        'preview_per_page': preview_per_page,
        'preview_total': preview_total,
        'preview_fields': display_fields,
        'extra_params': extra_params,
        'graphs' : graphs,
        'agents' : agents,
        'progress' : progress,
        'exp_id': exp_id,
        'snapshots':snapshots
    }
    # 合并额外传进来的参数（比如 exp_id, exp_name 等）
    base_context.update(extra_context)
    return render_template(template,**base_context)


@exp_bp.route('/new')
def experiment_new():
    runner_id = request.args.get('runner_id', '').strip()
    runner_type=request.args.get('runner_type','').strip()
    runner_display=request.args.get('runner_display','').strip()
    test_file = request.args.get('filename', '').strip()

    return render_html(
        'experiment.html',
        runner_id=runner_id,
        test_file=test_file,
        runner_type=runner_type,
        runner_display=runner_display,
        progress=0,
        exp_id=''
    )

@exp_bp.route('/delete/<exp_id>',methods=["GET"])
def experiment_delete(exp_id):
    MetaLoader.delete("exps",exp_id)
    return render_list()


@exp_bp.route('/')
def experiment_list():
    page = int(request.args.get('page', 1))
    per_page = 20
    search = request.args.get('search', '').strip()
    return render_list(search,page,per_page)

@exp_bp.route('/api/list')
def api_list_experiments():
    all_history = MetaLoader.loads("exps")
    all_history.sort(key=lambda d: d.get("created_at") or "1970-01-01T00:00:00", reverse=True)
    result = []
    for e in all_history:
        result.append({
            'id': e.get('exp_id', ''),
            'name': e.get('name', 'Untitled'),
            'status': e.get('status', 'unknown'),
            'progress': e.get('progress', 0),
            'runner_id': e.get('runner_id', ''),
            'runner_type': e.get('runner_type', ''),
            'dataset': e.get('dataset', ''),
            'samples': e.get('samples', 0),
            'created_at': e.get('created_at', '')
        })
    return jsonify(result)

@exp_bp.route('/<exp_id>')
def experiment_detail(exp_id):
    exp_cfg=MetaLoader.load("exps",exp_id)
    runner_id=exp_cfg['runner_id']
    runner_type=exp_cfg['runner_type']
    runner_display=exp_cfg['runner_display']
    test_file=exp_cfg['dataset']
    return render_html(
        'experiment.html',
        runner_id=runner_id,
        test_file=test_file,
        runner_type=runner_type,
        runner_display=runner_display,
        exp_id=exp_cfg['exp_id'],
        progress=exp_cfg['progress']
    )

@exp_bp.route('/api/<exp_id>')
def api_experiment_detail(exp_id):
    """Return experiment details as JSON."""
    try:
        exp_cfg = MetaLoader.load("exps", exp_id)
        return jsonify({
            'id': exp_cfg.get('exp_id', exp_id),
            'name': exp_cfg.get('name', 'Untitled'),
            'status': exp_cfg.get('status', 'unknown'),
            'progress': exp_cfg.get('progress', 0),
            'runner_id': exp_cfg.get('runner_id', ''),
            'runner_type': exp_cfg.get('runner_type', ''),
            'runner_display': exp_cfg.get('runner_display', ''),
            'dataset': exp_cfg.get('dataset', ''),
            'samples': exp_cfg.get('samples', 0),
            'model': exp_cfg.get('model', ''),
            'prompt_template': exp_cfg.get('prompt_template', {}),
            'created_at': exp_cfg.get('created_at', ''),
            'updated_at': exp_cfg.get('updated_at', ''),
            'history': exp_cfg.get('history', [])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@exp_bp.route('/api/save', methods=['POST'])
def experiment_save():
    try:
        data = request.get_json(force=True)  # force=True 防止 Content-Type 不对时报错

        if not data:
            return jsonify({"success": False, "error": "No JSON data received"}), 400

        # 必要字段校验
        required = ['runner_type', 'runner_id', 'dataset']
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({"success": False, "error": f"Missing fields: {', '.join(missing)}"}), 400

        if not 'exp_id' in data or not data['exp_id']:
            data['exp_id'] = str(uuid.uuid4())
            data["name"]= f"{data['runner_id']}_{data['dataset']}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            data['status']="pending"  # 后续可以改成 running/completed/failed
            data["progress"]=0
            MetaLoader.dump("exps", data['exp_id'], data)
        else:
            exp_id=data['exp_id']
            exp_cfg = MetaLoader.load("exps", exp_id)
            exp_cfg.update(data)
            MetaLoader.dump("exps", data['exp_id'], exp_cfg)
        # 持久化存储（你自己选方式）


        return jsonify({
            "success": True,
            "exp_id": data["exp_id"],
            "message": "Experiment config saved successfully"
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


async def _run_with_saver( exp_id, exp_cfg, dataset):
    runner_id=exp_cfg['runner_id']
    runner=RunnerLoader.aload(runner_id)
    #runner= load_graph(runner_id, saver) if exp_cfg['runner_type']=='graph' else get_agent(runner_id,saver)
    fields, data= TestLoader.load_by_id_file(runner_id,dataset)
    for idx, row in enumerate(data):
        input_dict = dict(zip(fields, row))
        config: RunnableConfig = {"configurable": {"thread_id": f'{exp_id}_{idx}'} }
        await runner.ainvoke(input_dict,config=config)


async def run_experiment_background(exp_id, exp_cfg, dataset):
        await _run_with_saver(exp_id, exp_cfg, dataset)

# 启动端点
@exp_bp.route('/api/update', methods=['POST'])
def update_exp():
    data = request.get_json(force=True)  # force=True 防止 Content-Type 不对时报错
    exp_id=data['exp_id']
    exp_cfg = MetaLoader.load("exps",exp_id)

    MetaLoader.update("exps",exp_id,data)
    if data['status']=='completed':
        #perststence state
        exp_cfg = MetaLoader.load("exps", exp_id)
        RunnerLoader.persistence(exp_cfg)
    # 立即启动后台任务
    #asyncio.create_task(run_experiment_background(exp_id, exp_cfg, dataset))

    return jsonify({
        'success': True,
        'exp_id': exp_id,
        'message': 'Experiment started in background',
    })


@exp_bp.route('/api/optimize-loop', methods=['POST'])
def optimize_loop():
    data = request.get_json(force=True) or {}
    exp_id = (data.get("exp_id") or "").strip()
    if not exp_id:
        return jsonify({"success": False, "error": "exp_id is required"}), 400
    candidate_graph_id = (data.get("candidate_graph_id") or "").strip()
    try:
        summary = run_optimize_loop_by_exp(
            exp_id,
            candidate_graph_id=candidate_graph_id,
        )
        return jsonify({"success": True, "summary": summary})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@exp_bp.route('/api/optimize-loop/start', methods=['POST'])
def optimize_loop_start():
    data = request.get_json(force=True) or {}
    exp_id = (data.get("exp_id") or "").strip()
    if not exp_id:
        return jsonify({"success": False, "error": "exp_id is required"}), 400
    candidate_graph_id = (data.get("candidate_graph_id") or "").strip()
    task_id = f"opt_{uuid.uuid4().hex}"
    task = {
        "task_id": task_id,
        "exp_id": exp_id,
        "status": "running",
        "progress": 0,
        "stage": "queued",
        "message": "Queued",
        "error": "",
        "summary": None,
        "updated_at": time.time(),
    }
    with _optimize_lock:
        _optimize_tasks[task_id] = task

    def _runner():
        def _on_progress(evt: dict):
            with _optimize_lock:
                t = _optimize_tasks.get(task_id)
                if not t:
                    return
                t["progress"] = int(evt.get("progress") or t["progress"])
                t["stage"] = evt.get("stage") or t["stage"]
                t["message"] = evt.get("message") or t["message"]
                t["updated_at"] = time.time()

        try:
            summary = run_optimize_loop_by_exp_with_progress(
                exp_id,
                candidate_graph_id=candidate_graph_id,
                progress_cb=_on_progress,
            )
            with _optimize_lock:
                t = _optimize_tasks.get(task_id)
                if t:
                    t["status"] = "completed"
                    t["progress"] = 100
                    t["stage"] = "done"
                    t["message"] = "Optimize loop completed"
                    t["summary"] = summary
                    t["updated_at"] = time.time()
        except Exception as ex:
            with _optimize_lock:
                t = _optimize_tasks.get(task_id)
                if t:
                    t["status"] = "failed"
                    t["message"] = "Optimize loop failed"
                    t["error"] = str(ex)
                    t["updated_at"] = time.time()

    threading.Thread(target=_runner, daemon=True).start()
    return jsonify({"success": True, "task_id": task_id})


@exp_bp.route('/stream/optimize-loop/<task_id>', methods=['GET'])
def optimize_loop_stream(task_id):
    def generate():
        last_payload = None
        while True:
            with _optimize_lock:
                task = dict(_optimize_tasks.get(task_id) or {})
            if not task:
                payload = {"status": "failed", "error": f"task not found: {task_id}"}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return
            payload = {
                "task_id": task_id,
                "status": task.get("status"),
                "progress": task.get("progress", 0),
                "stage": task.get("stage", ""),
                "message": task.get("message", ""),
                "error": task.get("error", ""),
            }
            if task.get("summary") is not None:
                payload["summary"] = task["summary"]

            if payload != last_payload:
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                last_payload = payload

            if task.get("status") in ("completed", "failed"):
                yield "data: [DONE]\n\n"
                return
            time.sleep(0.8)

    return Response(generate(), mimetype='text/event-stream')

