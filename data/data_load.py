from data.data_parser import CIDParser,ChemDisGeneParser

from pathlib import Path

DATA_ROOT = Path('./data')  # 根目录
def has_tsv_in_tree(root: Path) -> bool:
    """root 目录（含子目录）里只要有 ≥1 个 .tsv 就返回 True"""
    for p in root.rglob('*.tsv'):
        return True
    return False

def load_parser(dataset: str, file_name: str):
    base_dir = DATA_ROOT / dataset
    txt_path = base_dir / file_name
    if not base_dir.exists():
        return None
    # 1. 整个数据集目录里只要出现任意 .tsv → 走关系解析
    if has_tsv_in_tree(base_dir):
        # 可以一次性把目录里所有 tsv 合并解析
        tsv_files = sorted(base_dir.rglob('*.tsv'))
        parser=ChemDisGeneParser(txt_path.read_text(encoding='utf-8'),tsv_files)
        return parser
    # 2. 没有 tsv → 原 txt 解析
    if txt_path.exists():
        parser=CIDParser(txt_path.read_text(encoding='utf-8'))
        return parser
    return None

def load_datasets():
    """
    返回 dict:
      {
        'dataset_name': ['dataset_name/xxx.txt', 'dataset_name/yyy.txt', ...],
        ...
      }
    """
    datasets = {}
    for ds_dir in DATA_ROOT.iterdir():
        if ds_dir.is_dir():
            # 相对路径字符串，排序
            datasets[ds_dir.name] = sorted([
                p.name for p in ds_dir.glob('*.txt')
            ])
    return datasets



def count_dataset():
    return len(list(DATA_ROOT.iterdir()))

