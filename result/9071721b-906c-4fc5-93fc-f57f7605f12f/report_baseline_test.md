## 1) Metrics

**Overall Metrics (Micro)**

| Metric | Value |
|--------|-------|
| Precision | 0.0 |
| Recall | 0.0 |
| F1 | 0.0 |
| TP | 0 |
| FP | 4 |
| FN | 26 |

**Overall Metrics (Macro)**

| Metric | Value |
|--------|-------|
| Precision | 0.0 |
| Recall | 0.0 |
| F1 | 0.0 |

**F1 Distribution**

| Mean | Std | Min | Max |
|------|-----|-----|-----|
| 0.0 | 0.0 | 0.0 | 0.0 |

**Per-Sample Metrics**

| Sample ID | Precision | Recall | F1 | TP | FP | FN |
|-----------|-----------|--------|----|----|----|----|
| 1 | 0.0 | 0.0 | 0.0 | 0 | 2 | 13 |
| 2 | 0.0 | 0.0 | 0.0 | 0 | 2 | 13 |

**Agent Version Mapping**

| Agent ID | Version Used |
|----------|-------------|
| ner_chemdisgene_llm | current |
| chemdisgene_ner_parse | current |
| eval_metrics | current |

## 2) FN and FP Analysis

**False Negatives (FN = 26 total)**

Both samples share identical gold_entities: `{'Chemical': ['Orlistat', 'cholesterol', 'glucose'], 'Disease': ['obesity', 'weight loss', 'obesity', 'malabsorption', 'hyperlipidaemias, type 2 diabetes', 'hypertension', 'sleep apnoea', 'obesity', 'obesity', 'obesity', 'pancreatic lipase enzyme', 'weight loss', 'weight loss', 'obese', 'obese type 2 diabetic'], 'Gene': ['insulin']}`.

The test texts are:
- Sample 1: "Aspirin may reduce the risk of heart disease."
- Sample 2: "Metformin is commonly used to treat type 2 diabetes."

The gold_entities are clearly from a different source document (likely about obesity/Orlistat), not from these test texts. The LLM correctly extracted entities present in the text (Aspirin, heart disease, Metformin, type 2 diabetes), but none of these match the gold_entities. This is a dataset mismatch issue—the gold_entities do not correspond to the input text.

**False Positives (FP = 4 total)**

Each sample has 2 FP: the entities extracted by the LLM that are not in gold_entities. For sample 1: `{'Disease': ['heart disease'], 'Chemical': ['Aspirin']}`. For sample 2: `{'Chemical': ['Metformin'], 'Disease': ['type 2 diabetes']}`. These are correct extractions from the text but are counted as FP because gold_entities is from a different document.

**Root Cause**: The test dataset `regression_2_gold_test.csv` has gold_entities that do not match the input text. The NER pipeline is working correctly—it extracts entities present in the text. The evaluation is invalid because gold_entities are misaligned.

## 3) Agent Modification Suggestions

**Suggestion 1: Add input validation in `eval_metrics` PGM**

- **Target agent**: `eval_metrics`
- **What to change**: Add a guard that checks if predicted entities overlap with text before comparing to gold_entities. If predicted entities are not found in the text, skip evaluation and log a warning.
- **Expected impact**: Prevents invalid evaluations when gold_entities are misaligned with input text. Would have caught this dataset issue immediately.
- **Why easy**: Single PGM code change in the existing `eval_metrics` agent. No new dependencies.

**Suggestion 2: Add text-entity consistency check in `chemdisgene_ner_parse` PGM**

- **Target agent**: `chemdisgene_ner_parse`
- **What to change**: After parsing entities, add a check that each extracted entity name appears in the input text. Currently the code already does `if name not in text: continue`, but this only filters out entities not in text. Add a warning log when >50% of extracted entities are not in text.
- **Expected impact**: Early detection of text-entity mismatch issues. Would flag when the LLM extracts entities not present in the text.
- **Why easy**: Simple addition to existing PGM code. No new tools or dependencies.

**Suggestion 3: Add dataset validation step before graph execution**

- **Target agent**: `START` node (or new validation node before `ner_chemdisgene_llm`)
- **What to change**: Add a PGM node that checks if gold_entities contain entity names that appear in the input text. If mismatch rate > 80%, abort with clear error message.
- **Expected impact**: Prevents wasted compute on invalid test samples. Catches dataset alignment issues before running expensive LLM calls.
- **Why easy**: Can be implemented as a simple PGM node with text matching logic. No external dependencies.