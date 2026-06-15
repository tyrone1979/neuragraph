## 1) Metrics

**Experiment Overview**
- **Experiment ID:** f71223ad-9250-48a6-b62c-2ffb7c2a7103
- **Graph:** wf_flair_vs_llm_ner
- **Dataset:** regression_2_gold_test.csv (2 samples)
- **Report Mode:** table (sample_count ≤ 20)

**Agent Version Mapping**

| Agent ID | Version Used |
|---|---|
| text_sentence_split | current |
| ner_flair_aggregate | current |
| ner_llm | current |
| eval_flair | current |
| eval_llm | current |
| merge_metrics | current |
| ner_comparison_report | current |

**Per-Sample Gold Entities**

| Sample ID | Text | Gold Entities |
|---|---|---|
| 1 | Aspirin may reduce the risk of heart disease. | Disease: ['heart disease'], Chemical: ['Aspirin'] |
| 2 | Metformin is commonly used to treat type 2 diabetes. | Disease: ['type 2 diabetes'], Chemical: ['Metformin'] |

**Note:** No metrics_summary or per-agent metrics are available in the provided states. The eval_flair and eval_llm agents only count entity occurrences without comparing to gold labels. The merge_metrics agent simply combines these counts without computing precision/recall/F1. No FN/FP data exists in the states.

## 2) FN and FP Analysis

**No FN/FP data available.** The current evaluation pipeline (eval_flair, eval_llm, merge_metrics) only counts entity occurrences per label and merges them. It does not perform any comparison against gold standard entities, so false negatives and false positives cannot be computed from the provided states.

**Likely Cause:** The graph lacks a proper evaluation agent that compares predicted entities against gold entities. The eval_flair and eval_llm agents only produce entity counts, not classification metrics. The merge_metrics agent simply combines these counts without any comparison logic.

## 3) Agent Modification Suggestions

### Suggestion 1: Add proper NER evaluation agent
- **Target Agent:** New agent (e.g., `ner_evaluator`) inserted between `merge_metrics` and `ner_comparison_report`
- **What to Change:** Add a new PGM agent that takes predicted entities (from flair_entities and llm_entities) and gold entities (from START.entities) and computes per-label precision, recall, and F1
- **Expected Impact:** Enables meaningful FN/FP analysis and metric reporting
- **Why Easy:** Pure PGM code; no external dependencies; follows existing pattern of eval_flair/eval_llm but adds comparison logic

### Suggestion 2: Modify eval_flair and eval_llm to accept gold entities
- **Target Agent:** eval_flair, eval_llm
- **What to Change:** Add `gold_entities` input to both agents; modify process to compute true positives, false positives, false negatives per label
- **Expected Impact:** Immediate per-agent metrics without new graph nodes
- **Why Easy:** Minimal PGM code change; inputs already available from START.entities

### Suggestion 3: Update merge_metrics to compute aggregate metrics
- **Target Agent:** merge_metrics
- **What to Change:** Accept gold_entities input; compute overall precision, recall, F1 for both Flair and LLM; output structured metrics_summary
- **Expected Impact:** Provides the missing metrics_summary data needed for reporting
- **Why Easy:** Single PGM agent change; leverages existing data flow