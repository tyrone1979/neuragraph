## 1) Metrics

**Overall Metrics (Micro)**

| Metric | Value |
|--------|-------|
| Precision | 0.50 |
| Recall | 0.50 |
| F1 | 0.50 |
| TP | 2 |
| FP | 2 |
| FN | 2 |

**Overall Metrics (Macro)**

| Metric | Value |
|--------|-------|
| Precision | 0.50 |
| Recall | 0.50 |
| F1 | 0.50 |

**F1 Distribution**

| Stat | Value |
|------|-------|
| Mean | 0.50 |
| Std | 0.50 |
| Min | 0.00 |
| Max | 1.00 |

**Per-Sample Metrics**

| Sample ID | Precision | Recall | F1 | TP | FP | FN |
|-----------|-----------|--------|----|----|----|----|
| 1 | 1.00 | 1.00 | 1.00 | 2 | 0 | 0 |
| 2 | 0.00 | 0.00 | 0.00 | 0 | 2 | 2 |

**Agent Version Mapping**

| Agent ID | Version Used |
|----------|-------------|
| text_sentence_split | current |
| eval_metrics | current |
| ner_flair_sent | current |

## 2) FN and FP Analysis

**Sample 2 Analysis (F1=0.0, FP=2, FN=2)**

- **Text**: "Metformin is commonly used to treat type 2 diabetes."
- **Predicted entities**: `{'Chemical': ['Metformin'], 'Disease': ['type 2 diabetes']}`
- **Expected entities**: `{'Chemical': ['Aspirin'], 'Disease': ['heart disease']}`

**Root Cause**: The expected entities for Sample 2 are identical to Sample 1's expected entities (`Aspirin` / `heart disease`), but the text is about `Metformin` / `type 2 diabetes`. This is a **data loading or test dataset configuration error** — the `expected_entities` field for Sample 2 was incorrectly copied from Sample 1. The `ner_flair_sent` agent correctly predicted the entities present in the text (`Metformin`, `type 2 diabetes`), but they were compared against the wrong gold standard.

**Impact on Metrics**: All 2 FP and 2 FN for Sample 2 are entirely due to this gold data mismatch, not model performance. The `eval_metrics` agent correctly computed zero matches against the erroneous expected set.

## 3) Agent Modification Suggestions

### Suggestion 1: Add input validation guard in `eval_metrics` PGM

- **Target agent**: `eval_metrics`
- **What to change**: Add a pre-check in the PGM `process` code that compares the text content of predicted entities against expected entities for obvious mismatches (e.g., no overlapping tokens between any predicted and expected entity text).
- **Expected impact**: Catches data loading errors like the one in Sample 2, preventing misleading metrics. Would flag this case because `Metformin`/`type 2 diabetes` share zero tokens with `Aspirin`/`heart disease`.
- **Why easy**: Single PGM code change; no new dependencies; uses only existing inputs (`predicted`, `expected`).

### Suggestion 2: Add text-entity consistency check in `eval_metrics` PGM

- **Target agent**: `eval_metrics`
- **What to change**: Before computing metrics, verify that each expected entity text appears as a substring in the original text (passed as an additional input from the graph binding). If any expected entity is absent from the text, log a warning and skip metrics for that sample.
- **Expected impact**: Prevents evaluation on samples where gold labels don't match the input text, avoiding false FP/FN counts.
- **Why easy**: Requires adding `text` to the graph binding for `eval_metrics` (already available from `START.text`), plus ~5 lines of PGM code. No external dependencies.