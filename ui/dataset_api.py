from flask import Blueprint, request, jsonify, render_template, redirect, url_for

import html as html_lib

from pathlib import Path

from data.data_load import load_parser, load_datasets, RAW_UPLOAD_DATASET, RAW_DIR

from service.dataset_cid import DEFAULT_RE_RUNNER



ENTITY_CSS_MAP = {

    'Chemical': 'ent-chem',

    'Disease':  'ent-dis',

    'Gene':     'ent-gene',

    'Protein':  'ent-protein',

}



PER_PAGE = 20

dataset_bp = Blueprint('dataset', __name__, url_prefix='/dataset')





def _dataset_label(name: str) -> str:
    if name == RAW_UPLOAD_DATASET:
        return 'Raw (data/raw)'
    return name





@dataset_bp.route('/')

def dataset_hub():

    return redirect(url_for('testset.list_tests'))





@dataset_bp.route('/raw')

def dataset_list_view():

    datasets = load_datasets()

    dataset = request.args.get('dataset', next(iter(datasets.keys()), ''))

    curr_file = request.args.get('file', (datasets.get(dataset, [''])[0] if datasets.get(dataset) else ''))

    search = request.args.get('search', '').strip()



    parser = load_parser(dataset, curr_file)

    if parser is None:

        return render_template(

            'dataset_list.html',

            datasets=datasets,

            curr_dataset=dataset,

            curr_file=curr_file,

            arts=[],

            page=1,

            max_page=1,

            search=search,

            active_page='dataset',

            dataset_label=_dataset_label(dataset),

            error='Dataset file not found',

        )



    articles = parser.get_articles()

    if search:

        articles = [

            a for a in articles

            if search.lower() in a.pmid.lower() or search.lower() in a.title.lower()

        ]



    total = len(articles)

    max_page = max(1, (total + PER_PAGE - 1) // PER_PAGE)

    page = max(1, min(int(request.args.get('page', 1)), max_page))

    offset = (page - 1) * PER_PAGE

    page_arts = articles[offset: offset + PER_PAGE]



    if request.args.get('format') == 'json':

        return jsonify({

            'dataset': dataset,

            'file': curr_file,

            'page': page,

            'max_page': max_page,

            'search': search,

            'data': [{

                'pmid': a.pmid,

                'title': a.title,

                'entities_cnt': len(a.entities),

                'relations_cnt': len(getattr(a, 'res', []) or []),

            } for a in page_arts],

        })



    return render_template(

        'dataset_list.html',

        datasets=datasets,

        curr_dataset=dataset,

        curr_file=curr_file,

        arts=page_arts,

        page=page,

        max_page=max_page,

        search=search,

        active_page='dataset',

        dataset_label=_dataset_label(dataset),

    )





@dataset_bp.route('/upload_raw', methods=['POST'])

def upload_raw():

    file = request.files.get('file')

    if not file or not file.filename:

        return redirect(url_for('testset.list_tests'))

    if not file.filename.lower().endswith('.txt'):

        return redirect(url_for('testset.list_tests'))

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    file.save(RAW_DIR / Path(file.filename).name)

    return redirect(url_for('testset.list_tests'))





@dataset_bp.route('/detail/<pmid>')

def dataset_get_doc(pmid):

    dataset = request.args.get('dataset')

    file_name = request.args.get('file')

    parser = load_parser(dataset, file_name)

    if parser is None:

        return 'Document not found', 404

    doc = parser.get(pmid)

    if not doc:

        return 'Document not found', 404



    full_text = doc['title'] + ' ' + doc['abstract']

    doc['highlight'] = highlight_entities(full_text, doc['entities'])

    return render_template(

        'dataset_detail.html',

        doc=doc,

        curr_dataset=dataset,

        curr_file=file_name,

    )





def highlight_entities(abstract: str, entities: list) -> str:

    if not abstract:

        return ''

    inserts = []

    for e in entities:

        start, end = map(int, e['position'].split(':'))

        cls = ENTITY_CSS_MAP.get(e['type'], 'ent-default')

        span = f'<span class="ent {cls}" title="MESH:{e["mesh"]}">{html_lib.escape(e["text"])}</span>'

        inserts.append((start, end, span))

    inserts.sort(key=lambda x: x[0], reverse=True)



    out = abstract

    for start, end, span in inserts:

        out = out[:start] + span + out[end:]

    return out

