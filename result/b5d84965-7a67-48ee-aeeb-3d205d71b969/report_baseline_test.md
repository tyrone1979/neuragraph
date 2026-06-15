## 1) Metrics

**Overall Metrics (2 samples)**

| Metric | Micro | Macro |
|--------|-------|-------|
| Precision | 0.0 | 0.0 |
| Recall | 0.0 | 0.0 |
| F1 | 0.0 | 0.0 |
| TP | 0 | - |
| FP | 0 | - |
| FN | 2 | - |

**F1 Distribution:** mean=0.0, std=0.0, min=0.0, max=0.0

**Per-Sample Metrics**

| Sample ID | Precision | Recall | F1 | TP | FP | FN |
|-----------|-----------|--------|----|----|----|----|
| 1 | 0.0 | 0.0 | 0.0 | 0 | 0 | 1 |
| 2 | 0.0 | 0.0 | 0.0 | 0 | 0 | 1 |

**Agent Version Mapping**

| Agent ID | Version Used |
|----------|-------------|
| relation_verify_llm | v0010 |
| relation_result_to_id_pair | v0003 |
| cid_pair_generate | current |
| e2e_entities_assign_group_ids | current |
| e2e_entities_dedup_by_id | current |
| e2e_entities_passthrough | current |
| e2e_entity_aliases_snapshot | current |
| e2e_hypernym_filter | current |
| e2e_synonym_filter | current |
| eval_metrics_relation | current |
| ner_entities_to_re_format | current |
| text_sentence_split | current |
| ner_flair_sent | current |

## 2) FN and FP Analysis

**Sample 1 — FN: `Aspirin may reduce the risk of heart disease.`**
- **Ground truth:** `CHEBI:15365 | MESH:D006503` (Aspirin induces heart disease)
- **Predicted:** No relations (0 TP, 1 FN)
- **Cause:** The text states "Aspirin *may reduce the risk* of heart disease" — this is a protective/negative association. The `relation_verify_llm` agent (v0010) correctly applies Assumption 1.5 (head used as treatment/rescue therapy for tail) and returns `~`. The `relation_result_to_id_pair` PGM then outputs no relation. The ground truth expects a causal relation (`$`), but the text explicitly describes a risk reduction, not causation. This is a gold data issue or a deliberate test of the protective-effect handling.

**Sample 2 — FN: `Metformin is commonly used to treat type 2 diabetes.`**
- **Ground truth:** `CHEBI:6801 | MESH:D003924` (Metformin induces type 2 diabetes)
- **Predicted:** No relations (0 TP, 1 FN)
- **Cause:** The text states "Metformin is commonly used to *treat* type 2 diabetes" — this is a therapeutic use, not causation. The `relation_verify_llm` agent correctly applies Assumption 1.5 (head used as treatment for tail) and returns `~`. The `relation_result_to_id_pair` PGM outputs no relation. The ground truth expects a causal relation, but the text explicitly describes treatment, not induction. This is a gold data issue.

**Summary:** Both FNs are caused by the `relation_verify_llm` agent correctly identifying therapeutic/protective relationships (Assumption 1.5) and returning `~`, while the ground truth labels these as causal (`$`). The pipeline is functioning as designed — the gold data appears to contain non-causal pairs labeled as causal.

## 3) Agent Modification Suggestions

### Suggestion 1: Add "treats" context awareness to `relation_verify_llm` prompt

- **Target agent:** `relation_verify_llm` (v0010)
- **What to change:** Add a new Assumption 1.6 to the prompt: "if the article states that {head} is used to treat, prevent, reduce risk of, or manage {tail} (e.g., '{head} treats {tail}', '{head} reduces risk of {tail}', '{head} is used for {tail}'), answer '~'."
- **Expected impact:** Formalizes the existing implicit behavior for therapeutic contexts, making the prompt more robust against edge cases where treatment language is ambiguous.
- **Why easy:** Single prompt template edit in `prompt_template.human` — no code changes, no new tools, no external dependencies.

### Suggestion 2: Add "risk reduction" pattern to `relation_result_to_id_pair` negation guard

- **Target agent:** `relation_result_to_id_pair` (v0003)
- **What to change:** Add `'reduce risk of'`, `'reduces risk of'`, `'prevent'`, `'prevents'`, `'decrease risk'`, `'decreases risk'` to the `negation_phrases` list in the PGM process.
- **Expected impact:** Catches cases where the LLM returns `$` but the text explicitly describes risk reduction or prevention, overriding the false positive.
- **Why easy:** Single list addition in existing PGM code — no new logic, no external dependencies, no prompt changes.

### Suggestion 3: Add "treatment" pattern to `relation_result_to_id_pair` negation guard

- **Target agent:** `relation_result_to_id_pair` (v0003)
- **What to change:** Add `'used to treat'`, `'used for'`, `'treatment of'`, `'therapy for'`, `'therapeutic'` to the `negation_phrases` list.
- **Expected impact:** Overrides false `$` verdicts when the text describes therapeutic use rather than causation.
- **Why easy:** Single list addition in existing PGM code — no new logic, no external dependencies, no prompt changes.