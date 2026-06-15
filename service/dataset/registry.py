"""Plugin-backed access to dataset parsers and catalog (loose coupling)."""
from __future__ import annotations

from typing import Any


def _get_plugin(name: str) -> Any:
    from plugin.plugin_loader import get_plugin

    return get_plugin(name)


def get_parser_registry():
    return _get_plugin("DatasetParserRegistry")


def get_parser(name: str):
    return _get_plugin(name)


def load_parser(dataset: str, file_name: str):
    reg = get_parser_registry()
    if reg is not None:
        return reg.load_parser(dataset, file_name)
    from service.dataset import parsers

    return parsers.load_parser(dataset, file_name)


def load_datasets() -> dict[str, list[str]]:
    reg = get_parser_registry()
    if reg is not None:
        return reg.load_datasets()
    from service.dataset import parsers

    return parsers.load_datasets()


def list_parsers() -> list[dict[str, str]]:
    reg = get_parser_registry()
    if reg is not None:
        return reg.list_parsers()
    from service.dataset import parsers

    return parsers.list_parsers()


def get_catalog():
    return _get_plugin("DatasetCatalog")


def require_catalog():
    catalog = get_catalog()
    if catalog is None:
        raise RuntimeError("DatasetCatalog plugin unavailable")
    return catalog


def get_cid_builder():
    return _get_plugin("CidDatasetBuilder") or get_catalog()


def get_chemdisgene_builder():
    return _get_plugin("ChemDisGeneDatasetBuilder") or get_catalog()


def require_cid_builder():
    return require_catalog()


def require_chemdisgene_builder():
    return require_catalog()
