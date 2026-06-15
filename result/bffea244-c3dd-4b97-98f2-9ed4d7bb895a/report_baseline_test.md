## 1) Metrics

**Overall Performance (500 samples)**

| Metric | Micro | Macro |
|--------|-------|-------|
| Precision | 0.5431 | 0.6322 |
| Recall | 0.7645 | 0.7814 |
| F1 | 0.6351 | 0.6632 |

**Error Totals:** TP=724, FP=609, FN=223

**F1 Distribution:** mean=0.6632, std=0.3567, min=0.0, max=1.0

**Agent Version Mapping (effective)**

| Agent ID | Version Used |
|----------|-------------|
| relation_verify_llm | v0010 |
| relation_result_to_id_pair | v0003 |
| eval_metrics_relation | current |
| text_sentence_split | current |
| ner_entities_to_re_format | current |
| ner_flair_sent | current |
| e2e_entities_passthrough | current |
| e2e_synonym_filter | current |
| e2e_entities_assign_group_ids | current |
| e2e_entity_aliases_snapshot | current |
| e2e_entities_dedup_by_id | current |
| e2e_hypernym_filter | current |
| cid_pair_generate | current |

## 2) FN and FP Analysis

**False Positive Pattern (dominant): Cross-product explosion from synonym cluster over-splitting**

The most severe FP cases (sample 205: 19 FP, sample 132: 19 FP, sample 363: 14 FP) share a common root cause: the synonym filter (`e2e_synonym_filter`) assigns different cluster IDs to entities that should be merged, causing the pair generator to create a Cartesian product of all chemical × all disease clusters.

- **Sample 205:** "1,4-dihydropyridine calcium channel blockers" is split into 3 separate chemical clusters (ids 1,2,3) and another as id 6. "cardiovascular diseases" and "angina" are kept as separate disease clusters (ids 1,2). This produces 4×2=8 pairs per chemical cluster × 3 clusters = 24 predicted relations, when only 5 are correct.
- **Sample 132:** "methylprednisolone acetate", "lidocaine", "epinephrine", "penicillin" each get separate chemical IDs, and 5 disease entities get separate disease IDs → 4×5=20 pairs, only 1 correct.
- **Sample 363:** "5-fluorouracil / folinic acid" appears as 3 separate chemical clusters (ids 1,3,4) plus "MMC-dependent" as another → 4 chemicals × 8 diseases = 32 pairs, 14 correct.

**False Negative Pattern 1: Missing relations due to entity under-generation (NER gap)**

- **Sample 407 (11 FN):** The pipeline only predicts 1 relation ("oestrogen-only → gallbladder disease") but the article discusses 14 distinct disease outcomes. The NER captures "oestrogen-only" as the sole chemical entity, missing "oestrogens", "progestogens", and combined HT formulations. The disease NER captures only 14 of ~20 disease mentions. The pair generator can only produce pairs from captured entities.
- **Sample 50 (4 FN):** The pipeline predicts 0 relations. The NER captures "norpethidine" (metabolite) but not "pethidine" (parent drug). The gold standard likely uses pethidine as the causative agent. The synonym filter assigns norpethidine id 1 and 2 (duplicate), but pethidine is never captured by NER.

**False Negative Pattern 2: Relation verification rejecting valid causal links**

- **Sample 111 (5 FN):** The pipeline predicts only 2 relations (carbetocin → hyper/hypotension, carbetocin → retained placenta). Missing: carbetocin → abdominal pain, carbetocin → vomiting. The text explicitly states "dose-limiting adverse events: hyper- or hypotension (three), severe abdominal pain (0), vomiting (0) and retained placenta (four)." The LLM verifier likely rejects abdominal pain and vomiting because the text reports zero occurrences, but the gold standard includes them as known adverse effects.
- **Sample 436 (4 FN):** The pipeline predicts 4 relations (all chemicals → acute encephalopathy and cerebral vasospasm) but misses the relation to "acute lymphoblastic leukemia" (the condition being treated, not caused). The gold standard likely does not include leukemia as an induced disease, so these are correct rejections. The 4 FN come from missing the encephalopathy relation for some chemicals.

**False Negative Pattern 3: Hypernym filter removing specific disease mentions**

- **Sample 118 (3 FN):** The pipeline predicts only 3 relations (cocaine → haemorrhagic infarction, cocaine → ischemic stroke, cocaine → cerebral hypoperfusion). Missing: cocaine → cardiac arrhythmia, cocaine → respiratory dysfunction. The hypernym filter may have removed "cardiac arrhythmia" and "respiratory dysfunction" as broader terms relative to "cerebral hypoperfusion", but they are distinct causal pathways.

## 3) Agent Modification Suggestions

### Suggestion 1: Improve synonym cluster merging in `e2e_synonym_filter`

- **Target agent:** `e2e_synonym_filter`
- **What to change:** Prompt template — add explicit instruction to merge entities that refer to the same drug class or chemical family (e.g., "1,4-dihydropyridine calcium channel blockers" and "dihydropyridine calcium channel blockers" and "nifedipine" should share one cluster ID when the article treats them as interchangeable members of the same class).
- **Expected impact:** Reduce FP by 30-50% on articles with multiple drug class mentions. The cross-product explosion (samples 205, 132, 363) would be eliminated because entities would share cluster IDs, reducing pair count from O(N_chem × N_dis) to O(1 × N_dis).
- **Why easy:** Single prompt change in an existing LLM agent. No new code, tools, or dependencies.

### Suggestion 2: Add entity normalization for drug metabolites in `e2e_synonym_filter`

- **Target agent:** `e2e_synonym_filter`
- **What to change:** Prompt — add rule: "If an entity is a known metabolite of another entity in the same article (e.g., norpethidine is metabolite of pethidine), assign them the same cluster ID."
- **Expected impact:** Recover FN in cases like sample 50 where the NER captures the metabolite but not the parent drug. The metabolite would inherit the parent's cluster ID, enabling relation generation.
- **Why easy:** Single prompt addition. No external database needed — the LLM can infer metabolite relationships from context (e.g., "its neurotoxic metabolite, norpethidine").

### Suggestion 3: Relax relation verification for zero-count adverse events in `relation_verify_llm`

- **Target agent:** `relation_verify_llm`
- **What to change:** Prompt — add condition: "If the article lists {tail} as a known or monitored adverse event of {head} (even if zero occurrences were observed in the study), answer '$'."
- **Expected impact:** Recover FN in cases like sample 111 where "abdominal pain" and "vomiting" are listed as dose-limiting adverse events with zero occurrences but are still valid drug-adverse event relations.
- **Why easy:** Single condition addition to the prompt. No code changes.

### Suggestion 4: Prevent hypernym filter from removing distinct causal pathways in `e2e_hypernym_filter`

- **Target agent:** `e2e_hypernym_filter`
- **What to change:** Prompt — add rule: "Do not remove a disease entity if it represents a distinct causal mechanism or pathway from another disease entity, even if one is semantically broader. For example, 'cardiac arrhythmia' and 'cerebral hypoperfusion' are distinct mechanisms and should both be kept."
- **Expected impact:** Recover FN in cases like sample 118 where distinct adverse effects are incorrectly removed as hypernyms.
- **Why easy:** Single rule addition to existing prompt. No code changes.

### Suggestion 5: Improve NER coverage for drug class mentions in `ner_flair_sent`

- **Target agent:** `ner_flair_sent`
- **What to change:** Process — after Flair NER prediction, add a PGM post-processing step that expands abbreviated or hyphenated drug names. For example, if "oestrogen-only" is detected, also add "oestrogens" as a Chemical entity if present in the text.
- **Expected impact:** Recover FN in cases like sample 407 where the NER misses the parent drug class "oestrogens" and only captures "oestrogen-only".
- **Why easy:** Small PGM addition after existing Flair output. No model retraining needed.