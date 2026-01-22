# exp_api.py
from flask import Blueprint,  render_template, request, jsonify
import uuid
from datetime import datetime
from ui.components.paginated_api import get_paginated_data
from service.result.loader import ResultLoader
from dataclasses import is_dataclass,asdict
from langchain_core.runnables import RunnableConfig

from service.entity.test import TestLoader
from service.meta.loader import MetaLoader
from service.entity.runner import RunnerLoader
exp_bp = Blueprint('exp', __name__, url_prefix='/exp')

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
                snapshots[idx] = results[idx_str]
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


    base_context = {
        'datasets': tests,
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
async def update_exp():
    data = request.get_json(force=True)  # force=True 防止 Content-Type 不对时报错
    exp_id=data['exp_id']
    exp_cfg = MetaLoader.load("exps",exp_id)
    dataset = exp_cfg['dataset']

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

