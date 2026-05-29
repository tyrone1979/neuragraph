"""Tests for CSV testset random sampling."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from service.entity.test import TestLoader, TEST_DIR

RUNNER = "wf_cid_re_llm_linear"
SOURCE = "_pytest_sample_source.csv"
OUTPUT = "_pytest_sample_out.csv"


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    for name in (SOURCE, OUTPUT):
        p = TEST_DIR / RUNNER / name
        if p.is_file():
            p.unlink()


def test_sample_csv_rows_unique():
    rows = [
        {"text": f"article {i}", "entities": "[]", "gold_relations": ""}
        for i in range(10)
    ]
    TestLoader.save_csv_rows(RUNNER, SOURCE, ["text", "entities", "gold_relations"], rows)

    result = TestLoader.sample_csv_rows(RUNNER, SOURCE, OUTPUT, size=5, seed=42)
    assert result["sample_size"] == 5
    assert result["source_count"] == 10

    _fields, picked = TestLoader.load_by_id_file(RUNNER, OUTPUT)
    assert len(picked) == 5
    texts = [r["text"] for r in picked]
    assert len(set(texts)) == 5

    result2 = TestLoader.sample_csv_rows(RUNNER, SOURCE, OUTPUT, size=5, seed=42)
    _fields2, picked2 = TestLoader.load_by_id_file(RUNNER, OUTPUT)
    assert [r["text"] for r in picked2] == texts

    result3 = TestLoader.sample_csv_rows(RUNNER, SOURCE, OUTPUT, size=5, seed=99)
    _fields3, picked3 = TestLoader.load_by_id_file(RUNNER, OUTPUT)
    assert [r["text"] for r in picked3] != texts
