from flask import Blueprint, request, jsonify,render_template
import html as html_lib
from data.data_load import load_parser,load_datasets


ENTITY_CSS_MAP = {
    'Chemical': 'ent-chem',
    'Disease':  'ent-dis',
    # 后续随意扩展
    'Gene':     'ent-gene',
    'Protein':  'ent-protein',
}

PER_PAGE = 20
dataset_bp = Blueprint('dataset', __name__, url_prefix='/dataset')
# ---------- 列表 + 搜索 + 分页 ----------
@dataset_bp.route('/')
def dataset_list_view():
    """支持 HTML / JSON，数据集→文件→分页"""
    # 1. 当前数据集 & 文件
    datasets=load_datasets()
    dataset = request.args.get('dataset', next(iter(datasets.keys()), ''))
    curr_file = request.args.get('file', (datasets.get(dataset, '')[0]))

    parser = load_parser(dataset, curr_file)
    articles=parser.get_articles()

    # 2. 搜索
    search = request.args.get('search', '').strip()
    if search:
        articles = [a for a in articles
                    if search.lower() in a.pmid.lower()
                    or search.lower() in a.title.lower()]

    # 3. 分页
    total = len(articles)
    max_page = (total + PER_PAGE - 1) // PER_PAGE
    page = max(1, min(int(request.args.get('page', 1)), max_page))
    offset = (page - 1) * PER_PAGE
    page_arts = articles[offset: offset + PER_PAGE]

    # 4. 输出
    if request.args.get('format') == 'json':
        return jsonify({
            'dataset': dataset,
            'file': curr_file,
            'page': page,
            'max_page': max_page,
            'search': search,
            'data': [{'pmid': a.pmid,
                      'title': a.title,
                      'entities_cnt': len(a.entities),
                      'relations_cnt': len(a.cids)} for a in page_arts]
        })

    # 5. HTML
    return render_template('dataset_list.html',
                           datasets=datasets,
                           curr_dataset=dataset,
                           curr_file=curr_file,
                           arts=page_arts,
                           page=page,
                           max_page=max_page,
                           search=search,
                           active_page='dataset')


# ---------- 详情 ----------
@dataset_bp.route('/detail/<pmid>')
def dataset_get_doc(pmid):
    dataset = request.args.get('dataset')
    file_name = request.args.get('file')
    parser = load_parser(dataset, file_name)
    doc = parser.get(pmid)
    if doc is None:
        return 'Document not found', 404

    full_text = doc['title'] + ' ' + doc['abstract']
    doc['highlight'] = highlight_entities(full_text, doc['entities'])
    return render_template('dataset_detail.html',
                           doc=doc,
                           curr_dataset=dataset,
                           curr_file=file_name)


def highlight_entities(abstract: str, entities: list) -> str:
    if not abstract:
        return ''
    # 1. 解析并排序（从后往前插，必须降序）
    inserts = []
    for e in entities:
        start, end = map(int, e['position'].split(':'))
        cls = ENTITY_CSS_MAP.get(e['type'], 'ent-default')
        span = f'<span class="ent {cls}" title="MESH:{e["mesh"]}">{html_lib.escape(e["text"])}</span>'
        inserts.append((start, end, span))
    inserts.sort(key=lambda x: x[0], reverse=True)  # 必须从后往前插！

    # 2. 从后往前插入，坐标永不漂移
    out = abstract
    for start, end, span in inserts:
        out = out[:start] + span + out[end:]
    return out
