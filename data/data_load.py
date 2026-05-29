from data.data_parser import CIDParser, ChemDisGeneParser



from pathlib import Path



DATA_ROOT = Path('./data')  # 根目录

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_UPLOAD_DATASET = 'raw'

RAW_DIR = DATA_ROOT / 'raw'

# Backward compat: old URLs used dataset=_gold

RAW_GOLD_DATASET = RAW_UPLOAD_DATASET





def has_tsv_in_tree(root: Path) -> bool:

    """root 目录（含子目录）里只要有 ≥1 个 .tsv 就返回 True"""

    for p in root.rglob('*.tsv'):

        return True

    return False





def load_parser(dataset: str, file_name: str):

    if dataset in (RAW_UPLOAD_DATASET, '_gold'):

        txt_path = RAW_DIR / file_name

        if txt_path.exists():

            return CIDParser(txt_path.read_text(encoding='utf-8'))

        return None

    base_dir = DATA_ROOT / dataset

    txt_path = base_dir / file_name

    if not base_dir.exists():

        return None

    if has_tsv_in_tree(base_dir):

        tsv_files = sorted(base_dir.rglob('*.tsv'))

        parser = ChemDisGeneParser(txt_path.read_text(encoding='utf-8'), tsv_files)

        return parser

    if txt_path.exists():

        parser = CIDParser(txt_path.read_text(encoding='utf-8'))

        return parser

    return None





def load_datasets():

    """

    返回 dict:

      {

        'dataset_name': ['file1.txt', 'file2.txt', ...],

        ...

      }

    """

    datasets = {}

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    raw_files = sorted([p.name for p in RAW_DIR.glob('*.txt')])

    if raw_files:

        datasets[RAW_UPLOAD_DATASET] = raw_files

    for ds_dir in DATA_ROOT.iterdir():

        if not ds_dir.is_dir() or ds_dir.name == RAW_UPLOAD_DATASET:

            continue

        txt_files = sorted([p.name for p in ds_dir.glob('*.txt')])

        if txt_files:

            datasets[ds_dir.name] = txt_files

    return datasets





def count_dataset():

    return len(list(DATA_ROOT.iterdir()))

