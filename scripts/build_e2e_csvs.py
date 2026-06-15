#!/usr/bin/env python3
"""Build CSVs for E2E evaluation graphs."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from service.dataset.parsers import load_articles_from_source, row_options_for_source
from service.dataset.rows import row_ner, row_pubtator
from service.entity.test import TestLoader

SOURCE = ROOT / "comparison" / "data" / "CDR" / "test.txt"
OPTS = row_options_for_source(SOURCE)
ARTICLES = load_articles_from_source(SOURCE)

# ── Flair NER E2E ─────────────────
FLAIR_FIELDS = ["text", "labels", "gold_relations"]
flair_rows = []
for a in ARTICLES:
    r = row_ner(art=a, **OPTS)
    flair_rows.append({
        "text": r["text"],
        "labels": r["labels"],
        "gold_relations": r["gold_relations"],
    })
p = TestLoader.save_csv_rows("wf_e2e_flair_opt_re", "cdr_test_500.csv", FLAIR_FIELDS, flair_rows)
print(f"Flair E2E CSV: {p} ({len(flair_rows)} rows)")

# ── PubTator3 E2E ─────────────────
PUB_FIELDS = ["text", "pmid", "entities", "gold_relations"]
pub_rows = [row_pubtator(a, rel_label=OPTS["rel_label"]) for a in ARTICLES]
p2 = TestLoader.save_csv_rows("wf_e2e_pubtator_re", "cdr_test_500.csv", PUB_FIELDS, pub_rows)
print(f"PubTator E2E CSV: {p2} ({len(pub_rows)} rows)")
