## Experiment Results

### Performance Summary

| Experiment | Task | Precision | Recall | F1-Score | TP | FP | FN |
|:---|:---|---:|---:|---:|---:|---:|---:|
| **1** | Entity | 0.8462 | 0.9167 | 0.8800 | 11 | 2 | 1 |
| **1** | Relation | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 3 |
| **2** | Entity | 1.0000 | 0.8333 | 0.9091 | 5 | 0 | 1 |
| **2** | Relation | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 1 |

---

### Analysis and Conclusions

**1. Entity Recognition (NER)**
- **Moderate Overall Success:** Both experiments achieve reasonable F1 scores (**0.880** and **0.909**), indicating that the model is fairly capable of identifying entities.
- **Precision vs. Recall Trade-off:** 
  - *Experiment 1* is more balanced, with slightly higher recall (**0.917**) than precision (**0.846**). It produces 2 false positives while only missing 1 entity.
  - *Experiment 2* achieves perfect precision (**1.000**) with zero false positives, but recall drops to **0.833** (1 false negative).
- **Key Weakness:** The consistent false negatives in both runs suggest the model struggles with *recall*—it misses valid entities that are present in the ground truth.

**2. Relation Extraction (RE)**
- **Complete Failure:** The model scores **0.000** across all relation metrics (precision, recall, F1) in both experiments.
- **No Predictions Made:** With **0 true positives** and **0 false positives**, the model fails to predict any relations whatsoever. It entirely misses 3 relations in Experiment 1 and 1 relation in Experiment 2.
- **Critical Bottleneck:** Relation extraction is non-functional. The model appears either untrained for this task, severely miscalibrated, or structurally incapable of detecting relationships under the current setup.

**3. Overall Assessment**
- The system demonstrates a stark performance gap: **entity recognition works acceptably, while relation extraction is entirely broken.**
- Immediate priority should be diagnosing the relation extraction pipeline—checking model architecture, output layer configuration, training data coverage, and loss function weights for the relation head.
- For NER, minor improvements to recall (e.g., through data augmentation, lower confidence thresholds, or improved contextual encoding) could yield marginal gains, but RE requires fundamental corrective action before the system is viable.