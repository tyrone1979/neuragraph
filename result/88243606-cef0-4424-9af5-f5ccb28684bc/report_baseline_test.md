## 1) Metrics

**Overall Metrics (Micro & Macro)**

| Metric | Precision | Recall | F1 |
|--------|-----------|--------|----|
| Micro | 0.500 | 0.500 | 0.500 |
| Macro | 0.500 | 0.500 | 0.500 |

**Error Totals**
- True Positives: 2
- False Positives: 2
- False Negatives: 2

**F1 Distribution**
- Mean: 0.500
- Std: 0.500
- Min: 0.000
- Max: 1.000

**Per-Sample Metrics**

| Sample ID | Precision | Recall | F1 | TP | FP | FN |
|-----------|-----------|--------|----|----|----|----|
| 1 | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 |
| 2 | 0.000 | 0.000 | 0.000 | 0 | 2 | 2 |

**Agent Version Mapping**

| Agent ID | Version Used |
|----------|-------------|
| ner_flair_doc | current |
| eval_metrics | current |

## 2) FN and FP Analysis

**Sample 2 Analysis (All errors originate here)**

- **Text**: "Metformin is commonly used to treat type 2 diabetes."
- **Predicted entities**: Chemical: ['Metformin'], Disease: ['type 2 diabetes']
- **Expected entities**: Chemical: ['Aspirin'], Disease: ['heart disease']

**False Positives (2)**: The model correctly identified "Metformin" as a Chemical and "type 2 diabetes" as a Disease. These are valid biomedical entities present in the text. The FP classification is a data issue: the expected entities for this sample are from a different article (Aspirin/heart disease), not from the actual text provided.

**False Negatives (2)**: The model failed to predict "Aspirin" and "heart disease" because these entities do not appear in the text "Metformin is commonly used to treat type 2 diabetes." The FN classification is also a data mismatch issue.

**Root Cause**: The test dataset (regression_2_gold_test.csv) contains a sample where the `expected_entities` field does not match the `text` field. Sample 2's text discusses Metformin and type 2 diabetes, but the expected entities reference Aspirin and heart disease from a different document. This is a data quality issue in the test set, not a model performance issue.

## 3) Agent Modification Suggestions

**Suggestion 1: Add input validation guard in `eval_metrics` agent**

- **Target agent**: `eval_metrics`
- **What to change**: Add a PGM guard at the beginning of the process that checks whether any expected entity text appears in the input text (case-insensitive substring match). If no expected entities are found in the text, return empty metrics (or a warning flag) instead of computing false metrics.
- **Expected impact**: Prevents misleading metrics when test data has mismatched text/expected pairs. Sample 2 would produce empty metrics instead of 0.0 F1, making the aggregate metrics more accurate.
- **Why easy**: Single guard condition added to existing PGM code. No new dependencies. Uses only input fields already available (`text` and `expected`).

**Suggestion 2: Add data validation step before graph execution**

- **Target agent**: `START` node (or new validation node between START and ner_flair_doc)
- **What to change**: Add a PGM node that validates each sample's `expected_entities` against the `text` field. If any expected entity text is not found in the text, log a warning and either skip the sample or flag it for review.
- **Expected impact**: Catches data quality issues early, preventing wasted compute and misleading metrics. Improves experiment reliability.
- **Why easy**: Simple string matching logic in PGM. Can be added as a new node in the graph without modifying existing agents.