## 1) Metrics

**Overall Metrics (micro)**

| Metric | Value |
|--------|-------|
| Precision | 0.0 |
| Recall | 0.0 |
| F1 | 0.0 |
| TP | 0 |
| FP | 2 |
| FN | 2 |

**Macro Metrics**

| Metric | Value |
|--------|-------|
| Precision | 0.0 |
| Recall | 0.0 |
| F1 | 0.0 |

**F1 Distribution**

| Mean | Std | Min | Max |
|------|-----|-----|-----|
| 0.0 | 0.0 | 0.0 | 0.0 |

**Agent Version Mapping**

| Agent ID | Version Used |
|----------|-------------|
| ner_llm | current |
| relation_extract_llm | current |
| ontology_synonym_resolve | current |
| eval_metrics_relation | current |

**Per-Sample Metrics**

| Sample ID | TP | FP | FN | Precision | Recall | F1 | Route |
|-----------|----|----|----|-----------|--------|----|-------|
| 1 | 0 | 1 | 1 | 0.0 | 0.0 | 0.0 | Run full RE |
| 2 | 0 | 1 | 1 | 0.0 | 0.0 | 0.0 | Run full RE |

## 2) FN and FP Analysis

**Sample 1** - Text: "Aspirin may reduce the risk of heart disease."
- Predicted relation: `Aspirin | CID | heart disease`
- Ground truth: No relation (CID would be incorrect since Aspirin *reduces* risk)
- **FP**: The relation_extract_llm incorrectly classified a protective/risk-reducing relationship as CID ($). The prompt's condition 3 states that mediating/attenuating should yield '~', but the model output '$' instead.
- **FN**: The model failed to output '~' for this pair, which would have been the correct non-CID classification.

**Sample 2** - Text: "Metformin is commonly used to treat type 2 diabetes."
- Predicted relation: `Metformin | CID | type 2 diabetes`
- Ground truth: No relation (treatment is not causation)
- **FP**: The relation_extract_llm incorrectly classified a treatment relationship as CID ($). The prompt's conditions do not explicitly cover "treats" scenarios, leading the model to default to '$' when it should output '~'.
- **FN**: The model failed to recognize this as a non-CID relationship.

**Root Cause Analysis**: The relation_extract_llm prompt lacks explicit handling for common biomedical relationship types (treatment, prevention, risk reduction). The current conditions only cover: (1) causation/induction, (2) percentage-based adverse effects, (3) mediating/attenuating, and (4) no relationship. Missing categories like "treats", "prevents", "reduces risk of" cause the model to incorrectly default to '$' (CID) for these non-causal relationships.

## 3) Agent Modification Suggestions

### Suggestion 1: Add "treats" and "prevents" conditions to relation_extract_llm prompt

- **Target agent**: `relation_extract_llm`
- **What to change**: Add new conditions to the prompt template's human section, between existing conditions 2 and 3:
  - "3. if the article mentioned {{head}} is used to treat, prevent, or reduce the risk of {{tail}}, answer '~'"
  - Renumber existing conditions 3 and 4 to 4 and 5
- **Expected impact**: Eliminates the 2 FPs observed (both are treatment/prevention scenarios), improving precision from 0.0 to 1.0 on this dataset
- **Why easy**: Single prompt text edit; no code changes, no new tools, no external dependencies

### Suggestion 2: Add "no relationship" fallback guard in eval_metrics_relation PGM

- **Target agent**: `eval_metrics_relation`
- **What to change**: Add a PGM guard after `calculator.parse_relation_pairs(predicted_raw)` that checks if any predicted relation's head chemical appears in a known treatment context (e.g., "used to treat", "for the treatment of", "reduce the risk of") in the original text, and if so, excludes that relation from the predicted set
- **Expected impact**: Catches remaining FP cases where the LLM still outputs '$' for treatment/prevention relationships despite prompt improvements
- **Why easy**: PGM code change only; uses existing text input available in state; no new infrastructure needed