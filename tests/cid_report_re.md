# Experiment Results Report: Entity & Relation Extraction Performance

## 1. Experiment Results

### Entity Recognition Performance

| Run | Precision | Recall | F1-Score | TP | FP | FN |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1** | 0.7857 | 0.9167 | 0.8462 | 11 | 3 | 1 |
| **2** | 1.0000 | 0.8333 | 0.9091 | 5 | 0 | 1 |

### Relation Extraction Performance

| Run | Precision | Recall | F1-Score | TP | FP | FN |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1** | 0.0000 | 0.0000 | 0.0000 | 0 | 10 | 3 |
| **2** | 0.0000 | 0.0000 | 0.0000 | 0 | 2 | 1 |

---

## 2. Performance Analysis & Conclusions

### Entity Extraction: Competent but Strategically Divergent
The entity recognition module demonstrates viable performance across both runs, though with distinctly different optimization profiles.  
- **Run 1** leans heavily toward recall (**0.9167**), successfully identifying 11 of 12 ground-truth entities. However, this aggressiveness generates 3 false positives, pulling precision down to **0.7857** and capping the F1-score at **0.8462**.  
- **Run 2** adopts a conservative stance, achieving **perfect precision (1.0000)** with zero false positives. The trade-off is a modest drop in recall to **0.8333** (missing 1 entity). This conservative profile yields a superior F1-score of **0.9091**, indicating that, in this experimental setup, minimizing false positives delivers better overall entity extraction utility.

### Relation Extraction: Critical System Failure
The relation extraction component exhibits catastrophic failure. Both runs register **0% precision, 0% recall, and 0% F1-score**, having failed to identify a single correct relation.  
- **Run 1** is particularly alarming, producing **10 false positive relations** while missing 3 valid ones, suggesting a severely over-generative or mis-calibrated model.  
- **Run 2** reduces the noise volume (2 false positives, 1 false negative) but remains entirely ineffective with zero true positives.

### Key Takeaways
1. **Severe Task Imbalance**: The system shows a stark capability gap—entity extraction is functional while relation extraction is effectively non-operational. This points to fundamental flaws in the relation module's training data, architecture, or input features.
2. **Precision vs. Recall Trade-off**: For entity tasks, Runs 1 and 2 represent two different points on the precision-recall frontier. Run 2's high-precision approach is more successful (F1: 0.9091 vs 0.8462), suggesting stricter classification thresholds or better noise filtering.
3. **Relation Module Needs Immediate Attention**: The absolute absence of true positives, combined with high false positive rates, means the relation extractor is not merely underperforming—it is unusable. It may be untrained, hallucinating connections, or decoupled from the entity layer.
4. **Downstream Risk**: Run 1's flood of 10 relation false positives poses a significant scalability risk; deployed at scale, such a system would inundate downstream pipelines with fabricated relational data.

### Verdict
While **entity extraction demonstrates promising results**—particularly Run 2's clean, high-precision output—the experiment must be deemed **unsuccessful for end-to-end information extraction**. The relation extraction pipeline requires complete diagnostic review, retraining, or architectural overhaul before the system can be considered viable for production use.