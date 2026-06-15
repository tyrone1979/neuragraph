"""Dataset parsers and catalog — prefer service.dataset.registry for loose coupling."""

from service.dataset.registry import (
    get_catalog,
    get_chemdisgene_builder,
    get_cid_builder,
    get_parser,
    get_parser_registry,
    list_parsers,
    load_datasets,
    load_parser,
    require_catalog,
)
from service.dataset.rows import FORMAT_FIELDS, row_ner, row_pubtator, row_re

__all__ = [
    "FORMAT_FIELDS",
    "get_catalog",
    "get_chemdisgene_builder",
    "get_cid_builder",
    "get_parser",
    "get_parser_registry",
    "list_parsers",
    "load_datasets",
    "load_parser",
    "require_catalog",
    "row_ner",
    "row_pubtator",
    "row_re",
]
