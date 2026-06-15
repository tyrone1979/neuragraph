"""Tests for raw-source catalog (no dataset registry file)."""
from __future__ import annotations

import pytest

from service.dataset.registry import require_catalog
from service.entity.test import TestLoader, TEST_DIR

SOURCE = "data/raw/dev.txt"
AGENT_ID = "wf_cid_re_llm_linear"
TUNING = "_pytest_cid_tuning.csv"
TEST_OUT = "_pytest_cid_test.csv"
CUSTOM = "_pytest_cid_custom.csv"


@pytest.fixture(autouse=True)
def _cleanup_csv():
    yield
    for name in (TUNING, TEST_OUT, CUSTOM):
        p = TEST_DIR / AGENT_ID / name
        if p.is_file():
            p.unlink()


def test_registry_has_source_and_agent_files():
    from service.meta.loader import MetaLoader

    catalog = require_catalog()
    status = catalog.registry(SOURCE, agent_id=AGENT_ID)
    assert status["source_raw"]["count"] == 500
    tuning = next(
        (f for f in status.get("test_files", []) if f["name"] == "cid_dev_tuning_stratified.csv"),
        None,
    )
    assert tuning and tuning["count"] and tuning["count"] > 0

    meta = MetaLoader.load("agents", "dataset_cid_tuning_build")
    assert meta and meta.get("type") == "PGM"
    assert meta["outputs"]["name"] == "tuning_result"
    assert "DatasetCatalog" in meta["process"]


def test_build_tuning_and_extract_remain():
    catalog = require_catalog()
    articles = catalog.load_articles(SOURCE)
    assert articles
    result = catalog.build_tuning(
        AGENT_ID,
        source=SOURCE,
        format="re",
        size=5,
        tuning_out=TUNING,
        test_out=TEST_OUT,
        write_test_remain=True,
    )
    assert result["tuning_count"] == 5
    assert result["test_count"] == 495

    custom = catalog.extract_test(
        AGENT_ID,
        CUSTOM,
        source=SOURCE,
        format="re",
        mode="random",
        size=3,
        exclude_tuning_file=TUNING,
    )
    assert custom["count"] == 3
    _fields, rows = TestLoader.load_by_id_file(AGENT_ID, CUSTOM)
    assert len(rows) == 3

    tuning_fields, tuning_rows = TestLoader.load_by_id_file(AGENT_ID, TUNING)
    tuning_texts = {r["text"] for r in tuning_rows}
    for row in rows:
        assert row["text"] not in tuning_texts


def test_extract_pmids_mode():
    catalog = require_catalog()
    articles = catalog.load_articles(SOURCE)
    pmids = [articles[0].pmid, articles[1].pmid]
    out = "_pytest_cid_pmids.csv"
    try:
        result = catalog.extract_test(
            AGENT_ID,
            out,
            source=SOURCE,
            format="re",
            mode="pmids",
            pmids=pmids,
        )
        assert result["count"] == 2
        _fields, rows = TestLoader.load_by_id_file(AGENT_ID, out)
        assert len(rows) == 2
    finally:
        p = TEST_DIR / AGENT_ID / out
        if p.is_file():
            p.unlink()
