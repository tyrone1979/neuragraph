# Data format & dataset plugins

[README](../README.md) · [TESTING](TESTING.md) · [META_INVENTORY](META_INVENTORY.md) · [CODE_WIKI](CODE_WIKI.md)

NeuraGraph does **not** use a central dataset registry. Raw gold files are parsed on demand; structured CSVs live under `tests/<agent_id>/` or `tests/<graph_id>/`.

---

## Layers

| Layer | Location | Role |
| --- | --- | --- |
| Raw gold | `data/raw/*.txt` (+ optional `.tsv`) | Source PubTator / ChemDisGene exports (data/ has no Python code) |
| Article parsers | `service/dataset/data_parser.py` | `CIDParser`, `ChemDisGeneParser`, `Article` dataclasses |
| Parser routing | `service/dataset/parsers.py` | Auto-detect format; expose `relation_mode`, `default_labels`, `rel_label` |
| Catalog plugin | `plugin/plugins.py` → `DatasetCatalogPlugin` | Build CSV rows from raw source + `format` (`re`, `ner`, `pubtator`) |
| Structured tests | `tests/<agent_id>/sample.csv` | One regression row per agent |
| Workflow batches | `tests/<graph_id>/*.csv` | Multi-row experiment / graph test sets |

---

## Parser plugins (`DatasetCatalog` helpers)

Registered in `plugin/plugins.py`:

| Plugin id | Parser | Typical source |
| --- | --- | --- |
| `parser_cdr` | `CdrParser` | BC5CDR PubTator (`comparison/data/CDR/dev.txt`, `data/raw/dev.txt`) |
| `parser_chemdisgene` | `ChemDisGeneTsvParser` | ChemDisGene PubTator + relation TSV (`data/raw/chemdisgene.txt`) |
| `parser_plain_text` | `PlainTextParser` | Plain text uploads |

`DatasetParserRegistry` routes `(dataset, file)` pairs to the correct parser.

---

## Building CSVs from raw gold

PGM agents `dataset_cid_tuning_build` and `dataset_chemdisgene_build` call `get_plugin('DatasetCatalog')`:

```python
catalog = get_plugin("DatasetCatalog")
catalog.build_tuning(
    "wf_cid_re_llm_linear",
    source="data/raw/dev.txt",
    format="re",
    size=20,
)
catalog.build_full(
    "wf_chemdisgene_re_llm_linear",
    source="data/raw/chemdisgene.txt",
    format="re",
    mirror=[{"agent_id": "ner_chemdisgene_llm", "format": "ner"}],
)
```

Outputs are written under `tests/<agent_id>/` via `TestLoader.save_csv_rows`.

Legacy aliases `CidDatasetBuilder` and `ChemDisGeneDatasetBuilder` point to the same catalog instance.

---

## CSV column conventions

### Agent sample (`tests/<agent_id>/sample.csv`)

- Exactly **one data row** (plus header) for regression.
- Header keys must match the agent `inputs` array in `meta/agents/<id>.json`.
- JSON/list/dict cells are JSON-encoded strings.

Regenerate all agent samples:

```powershell
$env:PYTHONPATH = (Get-Location).Path
.\venv\Scripts\python.exe -c "from ui_tests.utils.agent_sample_row_fixtures import write_all_agent_sample_csvs; write_all_agent_sample_csvs()"
```

### Workflow / experiment CSV (`tests/<graph_id>/*.csv`)

- One row per article/sample.
- Columns align with graph **START** bindings (`compute_graph_global_inputs`).
- Gold columns (stripped in no-gold regression): `gold_relations`, `gold_entities`, `expected_entities`, `expected_relations`, `expected`, `ground_truth`.

| Column | Role |
| --- | --- |
| `text` / `sentence` | Document or sentence input |
| `entities` | Entity list or label dict (JSON) |
| `gold_relations` | Gold relation lines for metrics |
| `labels` | NER label filter string (`Chemical,Disease`, …) |

Regression suites auto-write 2-row files as `regression_2_gold_test.csv` under each graph id.

---

## Related code

- `service/dataset/data_parser.py` — PubTator / ChemDisGene article parsing
- `service/dataset/core.py` — `DatasetCatalog`
- `service/dataset/rows.py` — row builders per `format`
- `service/dataset/parsers.py` — `load_articles_from_source`, `row_options_for_source`
- `ui_tests/utils/agent_sample_row_fixtures.py` — canonical 1-row agent inputs
- `ui_tests/utils/regression_helpers.py` — 2-row graph/exp dataset builders
