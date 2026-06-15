"""Native dataset parser implementations (CDR, ChemDisGene, plain text)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from service.dataset.data_parser import CIDParser, ChemDisGeneParser

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_UPLOAD_DATASET = "raw"
RAW_GOLD_DATASET = RAW_UPLOAD_DATASET
RAW_DIR = DATA_ROOT / "raw"


def tsv_files_for_txt(txt_path: Path) -> list[Path]:
    """Find companion TSV gold-label files for a PubTator .txt article file."""
    if not txt_path.is_file():
        return []
    parent = txt_path.parent
    stem = txt_path.stem
    candidates = sorted(parent.glob(f"{stem}*.tsv"))
    if candidates:
        return candidates
    return sorted(parent.glob("*.tsv"))


def has_tsv_in_tree(root: Path) -> bool:
    for p in root.rglob("*.tsv"):
        return True
    return False


class CdrParser:
    """parser_cdr — BioCreative V CDR PubTator .txt with inline gold."""

    id = "parser_cdr"
    name = "CDR (PubTator)"
    relation_mode = "cid_mesh"
    rel_label = "CID"
    default_labels = "Chemical,Disease"
    description = (
        "Load BioCreative V CDR PubTator .txt articles with gold entities and CID relations."
    )

    @staticmethod
    def matches(dataset: str, txt_path: Path, base_dir: Path, tsv_files: list[Path]) -> bool:
        if not txt_path.is_file():
            return False
        if tsv_files:
            return False
        if dataset in (RAW_UPLOAD_DATASET, "_gold"):
            return True
        return base_dir.is_dir() and not has_tsv_in_tree(base_dir)

    @staticmethod
    def load_text(text: str):
        return CIDParser(text)

    @classmethod
    def load_file(cls, txt_path: Path):
        return cls.load_text(txt_path.read_text(encoding="utf-8"))


class ChemDisGeneTsvParser:
    """parser_chemdisgene — PubTator .txt with companion TSV relation trees."""

    id = "parser_chemdisgene"
    name = "ChemDisGene"
    relation_mode = "typed"
    rel_label = "CID"
    default_labels = "Chemical,Disease,Gene,Treat,Physiology,Immune"
    description = (
        "Load ChemDisGene article .txt files with companion .tsv annotation trees."
    )

    @staticmethod
    def matches(_dataset: str, txt_path: Path, _base_dir: Path, tsv_files: list[Path]) -> bool:
        return txt_path.is_file() and bool(tsv_files)

    @classmethod
    def load_file(cls, txt_path: Path, tsv_files: list[Path]):
        return ChemDisGeneParser(txt_path.read_text(encoding="utf-8"), tsv_files)


class PlainTextParser:
    """parser_plain_text — raw upload without bundled gold (PubTator layout, no TSV)."""

    id = "parser_plain_text"
    name = "Plain text (raw upload)"
    relation_mode = "cid_mesh"
    rel_label = "CID"
    default_labels = "Chemical,Disease"
    description = (
        "Load user-uploaded plain-text .txt from data/raw for batch runs without bundled gold files."
    )

    @staticmethod
    def matches(dataset: str, txt_path: Path, _base_dir: Path, tsv_files: list[Path]) -> bool:
        return dataset in (RAW_UPLOAD_DATASET, "_gold") and txt_path.is_file() and not tsv_files

    @classmethod
    def load_file(cls, txt_path: Path):
        return CIDParser(txt_path.read_text(encoding="utf-8"))


PARSER_ORDER = (ChemDisGeneTsvParser, CdrParser, PlainTextParser)


def list_parsers() -> list[dict[str, str]]:
    return [
        {"id": cls.id, "name": cls.name, "description": cls.description}
        for cls in PARSER_ORDER
    ]


def _resolve_paths(dataset: str, file_name: str) -> tuple[Path | None, Path, list[Path]]:
    if dataset in (RAW_UPLOAD_DATASET, "_gold"):
        txt_path = RAW_DIR / file_name
        base_dir = RAW_DIR
        if not txt_path.exists():
            return None, base_dir, []
        return txt_path, base_dir, tsv_files_for_txt(txt_path)

    base_dir = DATA_ROOT / dataset
    txt_path = base_dir / file_name
    if not base_dir.exists():
        return None, base_dir, []
    tsv_files = tsv_files_for_txt(txt_path) if txt_path.exists() else []
    if not tsv_files and has_tsv_in_tree(base_dir):
        tsv_files = sorted(base_dir.rglob("*.tsv"))
    return txt_path if txt_path.exists() else None, base_dir, tsv_files


def load_parser(dataset: str, file_name: str):
    txt_path, base_dir, tsv_files = _resolve_paths(dataset, file_name)
    if txt_path is None:
        return None

    for cls in PARSER_ORDER:
        if not cls.matches(dataset, txt_path, base_dir, tsv_files):
            continue
        if cls is ChemDisGeneTsvParser:
            return cls.load_file(txt_path, tsv_files)
        return cls.load_file(txt_path)
    return None


def resolve_source_path(source: str | Path) -> Path:
    """Resolve a raw gold .txt path (project-relative or absolute)."""
    raw = Path(str(source))
    if raw.is_file():
        return raw.resolve()
    candidates = [PROJECT_ROOT / raw, RAW_DIR / raw.name]
    if raw.parts and raw.parts[0] == "data":
        candidates.insert(0, PROJECT_ROOT / raw)
    if raw.name == "dev.txt":
        candidates.append(PROJECT_ROOT / "dev.txt")
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"source not found: {raw}")


def match_parser_class(txt_path: Path) -> type | None:
    if not txt_path.is_file():
        return None
    base_dir = txt_path.parent
    tsv_files = tsv_files_for_txt(txt_path)
    for cls in PARSER_ORDER:
        if cls.matches(RAW_UPLOAD_DATASET, txt_path, base_dir, tsv_files):
            return cls
    return None


def row_options_for_source(source: str | Path) -> dict[str, str]:
    path = resolve_source_path(source)
    cls = match_parser_class(path)
    if cls is None:
        return {
            "relation_mode": "cid_mesh",
            "rel_label": "CID",
            "default_labels": "Chemical,Disease",
        }
    return {
        "relation_mode": getattr(cls, "relation_mode", "cid_mesh"),
        "rel_label": getattr(cls, "rel_label", "CID"),
        "default_labels": getattr(cls, "default_labels", "Chemical,Disease"),
    }


def load_articles_from_source(source: str | Path) -> list:
    path = resolve_source_path(source)
    base_dir = path.parent
    tsv_files = tsv_files_for_txt(path)
    parser = None
    for cls in PARSER_ORDER:
        if not cls.matches(RAW_UPLOAD_DATASET, path, base_dir, tsv_files):
            continue
        if cls is ChemDisGeneTsvParser:
            parser = cls.load_file(path, tsv_files)
        else:
            parser = cls.load_file(path)
        break
    if parser is None:
        raise FileNotFoundError(f"no parser for {path}")
    articles = parser.get_articles()
    if not articles:
        raise ValueError(f"no articles parsed from {path.name}")
    return articles


def load_datasets() -> dict[str, list[str]]:
    datasets: dict[str, list[str]] = {}
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_files = sorted(p.name for p in RAW_DIR.glob("*.txt"))
    if raw_files:
        datasets[RAW_UPLOAD_DATASET] = raw_files
    for ds_dir in DATA_ROOT.iterdir():
        if not ds_dir.is_dir() or ds_dir.name == RAW_UPLOAD_DATASET:
            continue
        txt_files = sorted(p.name for p in ds_dir.glob("*.txt"))
        if txt_files:
            datasets[ds_dir.name] = txt_files
    return datasets


def count_dataset() -> int:
    return len(list(DATA_ROOT.iterdir()))


def article_count(dataset: str, file_name: str) -> int | None:
    try:
        parser = load_parser(dataset, file_name)
        if parser is None:
            return None
        return len(parser.get_articles())
    except Exception:
        return None
