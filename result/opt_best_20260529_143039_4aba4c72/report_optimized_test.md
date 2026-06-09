## 1) Metrics

**Overall Metrics**

| Metric | Value |
|--------|-------|
| Precision | 0.727 |
| Recall | 1.000 |
| F1 | 0.842 |
| Total TP | 8 |
| Total FP | 4 |
| Total FN | 0 |

**Per-Sample Metrics**

| Sample ID | Precision | Recall | F1 | TP | FP | FN |
|-----------|-----------|--------|----|----|----|----|
| 1 | 1.000 | 1.000 | 1.000 | 1 | 0 | 0 |
| 2 | 0.667 | 1.000 | 0.800 | 2 | 1 | 0 |
| 3 | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 |
| 4 | 1.000 | 1.000 | 1.000 | 1 | 0 | 0 |
| 5 | 0.400 | 1.000 | 0.571 | 2 | 3 | 0 |

**Agent Version Mapping**

| Graph ID | Agent ID | Version Used |
|----------|----------|--------------|
| wf_cid_re_llm_linear_opt_20260529_143039 | ontology_hypernym_filter | current |
| wf_cid_re_llm_linear_opt_20260529_143039 | cid_pair_generate | current |
| wf_cid_re_llm_linear_opt_20260529_143039 | relation_verify_llm | v0007 |
| wf_cid_re_llm_linear_opt_20260529_143039 | relation_result_to_id_pair | v0001 |
| sg_cid_re_verify | relation_verify_llm | current |
| sg_cid_re_verify | relation_result_to_id_pair | current |

## 2) FN and FP Analysis

**False Positives (4 total)**

- **Sample 2 (1 FP):** The pair `diuretic | diabetes` was predicted as a relation. The text lists "diuretic" as a therapy type and "diabetes" as a comorbidity predictor, but does not state that diuretic causes diabetes. The LLM returned `~` (correctly rejecting), but the PGM guard in `relation_result_to_id_pair` did not override because the associative phrase "risk factor" appears in the text near "diabetes" (within 30 chars), causing a false override to accept the relation. The guard's proximity check is too aggressive for this case.

- **Sample 5 (3 FPs):** The pairs `norepinephrine | convulsions`, `tricaine | convulsions`, and `Na | convulsions` were predicted as relations. The text discusses norepinephrine transporter function and Na+ channels in the context of convulsion modulation, but does not state that norepinephrine, tricaine, or Na cause convulsions. The LLM returned `$` for these pairs, likely because the prompt's broad causal language list (e.g., "associated with", "implicated in") caused over-acceptance of indirect mechanistic associations as causal relations.

**False Negatives (0 total)**

No false negatives were observed across all samples.

**Root Cause Summary**

The primary issue is the `relation_verify_llm` prompt being too permissive with causal language. The prompt includes phrases like "associated with", "risk factor for", "implicated in" as acceptable causal indicators, which leads the LLM to output `$` for non-causal associations. The PGM guard in `relation_result_to_id_pair` attempts to catch these but uses a proximity-based heuristic that is both too aggressive (sample 2) and insufficient (sample 5) because it relies on fixed distance thresholds rather than semantic understanding.

## 3) Agent Modification Suggestions

### Suggestion 1: Tighten `relation_verify_llm` prompt to reduce over-acceptance

- **Target Agent:** `relation_verify_llm`
- **What to Change:** Prompt template — remove weak causal phrases from the acceptable list and add explicit rejection instructions for mechanistic/indirect associations.
- **Change Details:**
  - Remove from the acceptable list: "associated with", "risk factor for", "implicated in", "may cause", "can lead to", "due to".
  - Add to the system prompt: "Reject if the text describes a mechanism, pathway, or biological process that involves both entities but does not state that {head} causes {tail}. Reject if the text lists {tail} as a comorbidity, predictor, or risk factor without stating causation by {head}."
  - Keep only strong causal phrases: "caused by", "induced by", "resulted in", "leads to", "side effect of", "adverse effect of", "results from", "attributed to".
- **Expected Impact:** Reduces FPs from samples 2 and 5 by preventing the LLM from outputting `$` for non-causal associations. The LLM will return `~` for these cases, and the PGM guard will not need to override.
- **Why Easy:** Single prompt edit in agent meta; no code changes, no new tools, no external dependencies.

### Suggestion 2: Remove the associative phrase guard from `relation_result_to_id_pair`

- **Target Agent:** `relation_result_to_id_pair`
- **What to Change:** Process code — delete the entire "Relaxed associative guard" block (lines with `associative_phrases` and the loop that checks proximity).
- **Change Details:** Remove the second guard block that checks for phrases like "associated with", "linked to", etc. within 30 characters. Keep only the negation guard.
- **Expected Impact:** Eliminates the false override in sample 2 where "risk factor" near "diabetes" incorrectly caused acceptance. The LLM will now correctly return `~` for that pair (after Suggestion 1), and the PGM will output nothing.
- **Why Easy:** Single code deletion in PGM agent; no new logic, no external dependencies. The guard was a heuristic that is now redundant after tightening the LLM prompt.

### Suggestion 3: Add a PGM guard to reject relations where the head entity is a generic ion or element

- **Target Agent:** `relation_result_to_id_pair`
- **What to Change:** Process code — add a check before the negation guard that rejects relations where the head entity's text is a single-element chemical symbol (e.g., "Na", "K", "Ca") or a generic biological molecule (e.g., "norepinephrine" when used as a mechanistic mediator rather than a drug).
- **Change Details:** Add a simple check: if the head text is in a small set of generic ions/elements (e.g., "Na", "K", "Ca", "Cl", "Mg", "Fe", "Zn", "Cu") or if the head text is a neurotransmitter name (e.g., "norepinephrine", "dopamine", "serotonin") and the text does not explicitly state that the head causes the tail (i.e., the LLM output is `$` but the text only mentions the head in a mechanistic context), then output `[]`. This can be implemented as a lookup set in the PGM code.
- **Expected Impact:** Reduces FPs in sample 5 for "Na | convulsions" and "norepinephrine | convulsions" where the entities are discussed as mechanistic mediators, not causal agents.
- **Why Easy:** Small PGM code addition; no new tools, no external dependencies, no API calls. The set of generic ions and neurotransmitters is small and domain-stable.