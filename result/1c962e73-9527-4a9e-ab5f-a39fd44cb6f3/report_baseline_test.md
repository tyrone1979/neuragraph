## 1) Metrics

**Experiment Overview**
- **Experiment ID:** `1c962e73-9527-4a9e-ab5f-a39fd44cb6f3`
- **Runner:** `sg_e2e_cid_re` (regression no_gold_test_only)
- **Dataset:** `regression_2_no_gold_test.csv`
- **Sample Count:** 2
- **Report Mode:** `table`

**Agent Version Mapping**

| Agent ID | Version Used |
|---|---|
| `relation_verify_llm` | v0010 |
| `relation_result_to_id_pair` | v0003 |
| `e2e_entities_passthrough` | current |
| `e2e_synonym_filter` | current |
| `e2e_entities_assign_group_ids` | current |
| `e2e_entity_aliases_snapshot` | current |
| `e2e_entities_dedup_by_id` | current |
| `e2e_hypernym_filter` | current |
| `cid_pair_generate` | current |

**Per-Sample Metrics**

| Sample ID | Text | Pairs Generated | Result |
|---|---|---|---|
| 1 | Aspirin may reduce the risk of heart disease. | 1 (Aspirin → heart disease) | `$` (induced) |
| 2 | Metformin is commonly used to treat type 2 diabetes. | 0 | N/A |

**Observations:**
- Sample 1 produced a false positive: `Aspirin` is described as reducing risk of `heart disease`, not causing it. The LLM incorrectly returned `$`.
- Sample 2 produced no pairs because only a Chemical entity (`Metformin`) was extracted; no Disease entity was present in the filtered entities.

## 2) FN and FP Analysis

**False Positive Analysis (Sample 1)**

- **Text:** "Aspirin may reduce the risk of heart disease."
- **Predicted Relation:** `Aspirin` induces `heart disease` (result: `$`)
- **Cause:** The `relation_verify_llm` agent (v0010) failed to apply Assumption 1.5 (rescue/treatment scenario). The text explicitly states that Aspirin *reduces* the risk of heart disease, which is a protective/treatment relationship, not causation. The LLM likely matched the surface pattern `{head} ... {tail}` and defaulted to Condition 1 or 4 without properly evaluating the semantic direction of the relationship. The `relation_result_to_id_pair` PGM's negation guard did not catch this because the text uses "reduce the risk of" — a phrase not in the negation_phrases list.

**False Negative Analysis (Sample 2)**

- **Text:** "Metformin is commonly used to treat type 2 diabetes."
- **Predicted Relations:** None (0 pairs generated)
- **Cause:** The `e2e_hypernym_filter` or upstream entity processing dropped the Disease entity `type 2 diabetes`. The filtered_entities output contains only `Metformin` (Chemical). The `e2e_entities_passthrough` deduplication or the `e2e_synonym_filter` may have failed to pass through the Disease entity, or the `e2e_hypernym_filter` incorrectly removed it as a modifier. Since `cid_pair_generate` requires at least one Chemical and one Disease to form pairs, no pairs were generated.

## 3) Agent Modification Suggestions

### Suggestion 1: Improve `relation_verify_llm` prompt to handle protective/treatment relationships

- **Target Agent:** `relation_verify_llm` (v0010)
- **What to Change:** Add a new Assumption to the prompt template (human section) that explicitly covers protective/reductive relationships.
- **Change Details:** Insert after Assumption 1.5:
  ```
  1.6 if the article states that {head} reduces, prevents, treats, protects against, or lowers the risk of {tail} (e.g., '{head} reduces {tail}', '{head} prevents {tail}', '{head} lowers risk of {tail}'), answer '~'.
  ```
- **Expected Impact:** Eliminates the false positive in Sample 1 and similar cases where a drug is described as beneficial rather than causative.
- **Why Easy:** Single prompt addition; no code changes, no new tools, no external dependencies. Follows the existing Assumption pattern.

### Suggestion 2: Add Disease entity preservation guard in `e2e_hypernym_filter`

- **Target Agent:** `e2e_hypernym_filter` (current)
- **What to Change:** Add a Step 0 to the prompt that explicitly preserves all Disease entities that are multi-word disease names (e.g., "type 2 diabetes") before applying modifier removal.
- **Change Details:** Insert at the beginning of the human prompt:
  ```
  Step 0 — Preserve multi-word disease names: Any Disease entity consisting of two or more words (e.g., 'type 2 diabetes', 'heart disease', 'acute kidney injury') MUST be kept regardless of modifier rules in later steps. Only single-word Disease entities that are standalone modifiers (e.g., 'severe', 'acute', 'chronic') may be considered for removal.
  ```
- **Expected Impact:** Prevents loss of specific disease entities like "type 2 diabetes" in Sample 2, enabling pair generation for valid CID relations.
- **Why Easy:** Single prompt addition; no code changes. The LLM can easily follow this explicit preservation rule.

### Suggestion 3: Add "reduces risk" to `relation_result_to_id_pair` negation guard

- **Target Agent:** `relation_result_to_id_pair` (v0003)
- **What to Change:** Add `'reduces risk of'`, `'reduces the risk of'`, `'prevents'`, `'protects against'`, `'lowers risk of'` to the `negation_phrases` list in the PGM process.
- **Change Details:** Insert these phrases into the existing `negation_phrases` list:
  ```python
  negation_phrases = [
      ...existing phrases...,
      'reduces risk of', 'reduces the risk of', 'prevents', 'protects against',
      'lowers risk of', 'decreases risk of', 'decreases the risk of'
  ]
  ```
- **Expected Impact:** Provides a second line of defense: even if the LLM incorrectly returns `$`, the PGM guard will override it when protective language is detected near the head/tail terms.
- **Why Easy:** Simple list addition in existing PGM code; no new logic or external dependencies.