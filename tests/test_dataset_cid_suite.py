"""Tests for CID dataset registry and extraction."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from service.dataset_cid import (
    build_tuning_dataset,
    extract_test_dataset,
    get_registry_status,
    load_source_articles,
)
from service.entity.test import TestLoader, TEST_DIR

RUNNER = "wf_cid_re_llm_linear"
TUNING = "_pytest_cid_tuning.csv"
TEST_OUT = "_pytest_cid_test.csv"
CUSTOM = "_pytest_cid_custom.csv"


@pytest.fixture(autouse=True)
def _cleanup_csv():
    yield
    for name in (TUNING, TEST_OUT, CUSTOM):
        p = TEST_DIR / RUNNER / name
        if p.is_file():
            p.unlink()


def test_registry_has_source_and_structured_counts():
    from service.meta.loader import MetaLoader

    status = get_registry_status(RUNNER)
    assert status["source_raw"]["count"] == 500
    assert status["structured"]["tuning"]["file"] == "cid_dev_tuning_stratified.csv"
    assert status["structured"]["tuning"]["count"] == 20

    meta = MetaLoader.load("agents", "dataset_cid_tuning_build")
    assert meta and meta.get("type") == "PGM"
    assert meta["outputs"]["name"] == "tuning_result"
    assert "CidDatasetBuilder" in meta["process"]


def test_build_tuning_and_extract_remain():
    articles = load_source_articles()
    result = build_tuning_dataset(
        RUNNER,
        size=5,
        tuning_out=TUNING,
        test_out=TEST_OUT,
        write_test_remain=True,
        mirror_ner=False,
    )
    assert result["tuning_count"] == 5
    assert result["test_count"] == 495

    custom = extract_test_dataset(
        RUNNER,
        CUSTOM,
        mode="random",
        size=3,
        exclude_tuning_file=TUNING,
        mirror_ner=False,
    )
    assert custom["count"] == 3
    _fields, rows = TestLoader.load_by_id_file(RUNNER, CUSTOM)
    assert len(rows) == 3

    tuning_fields, tuning_rows = TestLoader.load_by_id_file(RUNNER, TUNING)
    tuning_texts = {r["text"] for r in tuning_rows}
    for row in rows:
        assert row["text"] not in tuning_texts


def test_extract_pmids_mode():
    articles = load_source_articles()
    pmids = [articles[0].pmid, articles[1].pmid]
    out = "_pytest_cid_pmids.csv"
    try:
        result = extract_test_dataset(
            RUNNER,
            out,
            mode="pmids",
            pmids=pmids,
            mirror_ner=False,
        )
        assert result["count"] == 2
        _fields, rows = TestLoader.load_by_id_file(RUNNER, out)
        assert len(rows) == 2
    finally:
        p = TEST_DIR / RUNNER / out
        if p.is_file():
            p.unlink()
