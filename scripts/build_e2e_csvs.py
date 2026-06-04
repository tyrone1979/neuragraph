#!/usr/bin/env python3
"""Build CSVs for E2E evaluation graphs."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from service.dataset_cid import load_source_articles, ner_row, pubtator_row
from service.entity.test import TestLoader

SOURCE = ROOT / "comparison" / "data" / "CDR" / "test.txt"
ARTICLES = load_source_articles(SOURCE)

# ── Flair NER E2E ─────────────────
# Fields needed by wf_e2e_flair_opt_re:
#   text, labels, gold_relations
FLAIR_FIELDS = ["text", "labels", "gold_relations"]
flair_rows = []
for a in ARTICLES:
    r = ner_row(a)
    flair_rows.append({
        "text": r["text"],
        "labels": r["labels"],
        "gold_relations": r["gold_relations"],
    })
p = TestLoader.save_csv_rows("wf_e2e_flair_opt_re", "cdr_test_500.csv", FLAIR_FIELDS, flair_rows)
print(f"Flair E2E CSV: {p} ({len(flair_rows)} rows)")

# ── PubTator3 E2E ─────────────────
# Fields needed by wf_e2e_pubtator_re:
#   text, pmid, entities (gold, for normalization), gold_relations
PUB_FIELDS = ["text", "pmid", "entities", "gold_relations"]
pub_rows = [pubtator_row(a) for a in ARTICLES]
p2 = TestLoader.save_csv_rows("wf_e2e_pubtator_re", "cdr_test_500.csv", PUB_FIELDS, pub_rows)
print(f"PubTator E2E CSV: {p2} ({len(pub_rows)} rows)")
