## 1) Metrics

**Overall Metrics (Micro)**

| Metric | Value |
|--------|-------|
| Precision | 0.50 |
| Recall | 0.50 |
| F1 | 0.50 |
| True Positives | 2 |
| False Positives | 2 |
| False Negatives | 2 |

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

| Sample ID | Text | Precision | Recall | F1 | TP | FP | FN |
|-----------|------|-----------|--------|----|----|----|----|
| 1 | Aspirin may reduce the risk of heart disease. | 1.00 | 1.00 | 1.00 | 2 | 0 | 0 |
| 2 | Metformin is commonly used to treat type 2 diabetes. | 0.00 | 0.00 | 0.00 | 0 | 2 | 2 |

**Agent Version Mapping**

| Agent ID | Version Used |
|----------|-------------|
| ner_llm | current |
| eval_metrics | current |

## 2) FN and FP Analysis

**Sample 2 Analysis (Metformin / type 2 diabetes)**

- **Text:** "Metformin is commonly used to treat type 2 diabetes."
- **Predicted entities:** `{'Disease': ['type 2 diabetes'], 'Chemical': ['Metformin']}`
- **Metrics:** 0 TP, 2 FP, 2 FN — all entities were predicted but counted as both FP and FN.

**Likely Cause:** The `eval_metrics` PGM agent uses `MetricsCalculation.calculate()` which performs exact string matching between predicted and expected entities. The gold entities in the dataset likely use a different surface form or include MeSH IDs (e.g., `D008687` for Metformin, `D003922` for Diabetes Mellitus Type 2), while the LLM predicts plain text names. This causes a complete mismatch: every predicted entity is counted as both a false positive (not in gold) and a false negative (gold entity not predicted). The `ner_llm` agent correctly extracts the entities from the text, but the evaluation fails due to surface-form or ID normalization mismatch.

**Sample 1 Analysis (Aspirin / heart disease)**

- **Text:** "Aspirin may reduce the risk of heart disease."
- **Predicted entities:** `{'Disease': ['heart disease'], 'Chemical': ['Aspirin']}`
- **Metrics:** 2 TP, 0 FP, 0 FN — perfect match.

This sample works correctly, confirming the LLM NER agent is functional. The issue is isolated to samples where gold entities use non-plain-text representations.

## 3) Agent Modification Suggestions

### Suggestion 1: Add ID normalization to eval_metrics PGM

- **Target agent:** `eval_metrics`
- **What to change:** Add a normalization step in the PGM `process` code before calling `calculator.calculate()`. Use `MetricsCalculation.normalize_cid_lines()` (already available in the plugin) to convert both `expected` and `predicted` entity strings to a canonical form (e.g., stripping MeSH IDs, lowercasing, removing punctuation).
- **Expected impact:** Resolves the 2 FP / 2 FN in Sample 2, improving micro F1 from 0.50 to 1.00. Prevents similar mismatches in future samples where gold uses ID-based or differently-formatted entity names.
- **Why easy:** Single-line addition to existing PGM code. The `normalize_cid_lines` function already exists in the `MetricsCalculation` plugin. No new dependencies, no prompt changes, no external services.

### Suggestion 2: Add entity normalization instruction to ner_llm prompt

- **Target agent:** `ner_llm`
- **What to change:** Add a sentence to the `human` prompt template: "Normalize entity names to their canonical form (lowercase, remove trailing IDs/numbers)."
- **Expected impact:** Reduces surface-form variation between LLM output and gold entities, improving match rates in evaluation. Complements the PGM-side normalization from Suggestion 1.
- **Why easy:** Simple prompt tweak, no code changes, no new tools. Low risk of breaking existing functionality.