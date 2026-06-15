## 1) Metrics

**Experiment Overview**
- **Experiment ID:** bdd593ae-2db9-4e67-8aeb-754c73fc3123
- **Graph:** sg_e2e_flair_ner (E2E Flair NER subgraph)
- **Dataset:** regression_2_no_gold_test.csv (2 samples)
- **Report Mode:** table (sample_count ≤ 20)

**Agent Version Mapping**

| Agent ID | Version Used |
|---|---|
| text_sentence_split | current |
| ner_entities_to_re_format | current |
| ner_flair_sent | current |

**Per-Sample Entity Extraction Results**

| Sample ID | Text | Predicted Entities |
|---|---|---|
| 1 | Aspirin may reduce the risk of heart disease. | [{"text": "Aspirin", "label": "Chemical", "id": ""}, {"text": "heart disease", "label": "Disease", "id": ""}] |
| 2 | Metformin is commonly used to treat type 2 diabetes. | [{"text": "Metformin", "label": "Chemical", "id": ""}, {"text": "type 2 diabetes", "label": "Disease", "id": ""}] |

**Observations:** Both samples produced correct entity extractions. No false negatives or false positives are present in the output. The pipeline correctly identified "Aspirin" and "Metformin" as Chemicals, and "heart disease" and "type 2 diabetes" as Diseases.

## 2) FN and FP Analysis

**False Negatives:** None detected. All expected entities were extracted correctly for both samples.

**False Positives:** None detected. No spurious entities were introduced.

**Analysis:** The current pipeline performs correctly on these two simple biomedical sentences. The HunFlair2 NER model (via `ner_flair_sent`) successfully identifies single-word chemicals ("Aspirin", "Metformin") and multi-word diseases ("heart disease", "type 2 diabetes"). The `ner_entities_to_re_format` PGM correctly converts the Flair output dict to the required entity list format.

## 3) Agent Modification Suggestions

No agent modifications are necessary based on the current experiment results. The pipeline correctly extracts all entities for both test samples. If future experiments reveal failures, the following areas could be investigated:

1. **Target Agent:** `ner_flair_sent`
   - **What to change:** Add a confidence threshold filter in the PGM process to exclude low-confidence Flair predictions.
   - **Expected impact:** Reduce false positives from borderline NER predictions.
   - **Why easy:** Simple addition of `if entity.score > 0.5:` guard before appending to result.

2. **Target Agent:** `ner_entities_to_re_format`
   - **What to change:** Add entity text normalization (lowercasing, whitespace stripping) in the PGM process.
   - **Expected impact:** Improve downstream matching consistency for RE pipeline.
   - **Why easy:** Single line addition: `"text": text.strip().lower()` in the dict construction.