## 1) Metrics

**Overall Metrics (2 samples)**

| Metric | Micro |
|--------|-------|
| Precision | 0.0 |
| Recall | 0.0 |
| F1 | 0.0 |
| TP | 0 |
| FP | 0 |
| FN | 2 |

**F1 Distribution** — mean: 0.0, std: 0.0, min: 0.0, max: 0.0

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

**Per-Sample Metrics**

| Sample ID | Precision | Recall | F1 | TP | FP | FN |
|-----------|-----------|--------|----|----|----|----|
| 1 | 0.0 | 0.0 | 0.0 | 0 | 0 | 1 |
| 2 | 0.0 | 0.0 | 0.0 | 0 | 0 | 1 |

## 2) FN and FP Analysis

**Sample 1** — Text: "Aspirin may reduce the risk of heart disease."
- **FN**: Gold relation `CHEBI:15365 | MESH:D006331` (Aspirin → heart disease) not predicted.
- **Cause**: The Flair NER pipeline produced **no entities** (`entities: []`). The sentence "Aspirin may reduce the risk of heart disease." was processed by `ner_flair_sent` but returned zero spans. This is a **NER recall failure** — HunFlair2 did not recognize "Aspirin" as Chemical or "heart disease" as Disease in this sentence. Since no entities were extracted, the CID RE pipeline never generated any pairs to verify.

**Sample 2** — Text: "Metformin is commonly used to treat type 2 diabetes."
- **FN**: Gold relation `CHEBI:6801 | MESH:D003924` (Metformin → type 2 diabetes) not predicted.
- **Cause**: The `e2e_entities_passthrough` agent received `entities: []` (empty from NER), so `filtered_entities` was empty. However, the `cid_pair_generate` agent produced a pair `(Metformin, type 2 diabetes)` with correct MeSH IDs. This pair was sent to `relation_verify_llm` (v0010). The LLM correctly identified the entities but the text describes **treatment** ("used to treat"), not causation. The prompt's **Assumption 1.5** states: *"if {head} is used as ... treatment for {tail} ... answer '~'"*. The LLM correctly returned `~`, so `relation_result_to_id_pair` output `[]`. This is a **correct LLM verdict** — the relation is therapeutic, not causal. The gold standard labels this as a CID relation, but the task definition (Chemical-Induced Disease) should not include therapeutic uses. This is a **gold standard labeling issue**, not a pipeline error.

## 3) Agent Modification Suggestions

### Suggestion 1: Improve NER recall for short/simple sentences
- **Target agent**: `ner_flair_sent`
- **What to change**: Add a pre-processing step in the PGM code that checks if the sentence contains known biomedical entity patterns (capitalized drug names, common disease terms) before calling the Flair tagger. If the tagger returns empty but the sentence contains such patterns, re-run with a lower confidence threshold.
- **Expected impact**: Recovers entities like "Aspirin" and "heart disease" in simple sentences where HunFlair2 may miss them due to short context or lack of surrounding biomedical text.
- **Why easy**: Single PGM code change in the existing agent; no new dependencies or external calls.

### Suggestion 2: Add therapeutic-relation detection to the RE verify prompt
- **Target agent**: `relation_verify_llm`
- **What to change**: Add a new Assumption (1.6) to the prompt: *"if {head} is used as a treatment, therapy, or management for {tail} (e.g., 'used to treat', 'administered for', 'prescribed for', 'therapy for'), answer '~'."*
- **Expected impact**: Reduces FNs on therapeutic relations that are incorrectly labeled as CID in the gold standard. The current prompt only covers rescue/resuscitation/antidote scenarios (Assumption 1.5), missing the broader treatment context.
- **Why easy**: Single prompt template edit; no code changes needed.

### Suggestion 3: Add entity-level confidence filtering in `ner_entities_to_re_format`
- **Target agent**: `ner_entities_to_re_format`
- **What to change**: Add a PGM guard that filters out entities with very short text (single character or whitespace-only) before passing to the RE pipeline. Currently, the agent accepts any non-empty string.
- **Expected impact**: Prevents downstream processing of spurious single-character entities that may occasionally pass through Flair NER, reducing noise in pair generation.
- **Why easy**: Simple string length check in existing PGM code; no new dependencies.