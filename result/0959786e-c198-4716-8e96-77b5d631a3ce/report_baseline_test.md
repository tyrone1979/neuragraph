# Experiment Report: sg_cid_re_verify (regression no_gold_with_tuning)

## 1) Metrics

### Experiment Overview
- **Experiment ID**: 0959786e-c198-4716-8e96-77b5d631a3ce
- **Runner**: sg_cid_re_verify (regression no_gold_with_tuning)
- **Dataset**: regression_2_no_gold_test.csv (2 samples)
- **Status**: completed

### Agent Version Mapping
| Agent ID | Version Used |
|----------|-------------|
| relation_verify_llm | v0010 |
| relation_result_to_id_pair | v0003 |

### Per-Sample Results (report_mode: table, sample_count ≤ 20)

| Sample ID | Head | Tail | Head ID | Tail ID | LLM Result | Relations Output | Expected |
|-----------|------|------|---------|---------|------------|-----------------|----------|
| 1 | Aspirin | heart disease | D001241 | D006331 | $ | [] | FN (should output pair) |
| 2 | Aspirin | heart disease | D001241 | D006331 | $ | [D001241 \| D006331] | Correct |

**Summary**: 1 correct, 1 false negative (FN). No false positives (FP).

## 2) FN and FP Analysis

### False Negative Analysis

**Sample 1**: Text = "Aspirin may reduce the risk of heart disease."
- LLM correctly returned `$` (indicates causation/induction)
- PGM `relation_result_to_id_pair` returned empty list despite `$` result and valid IDs

**Likely Cause**: The PGM's negation/associative guard overrode the LLM verdict. The text contains "reduce the risk of" which is not in the negation_phrases list, but the associative guard likely triggered on "risk of" (within 15 chars of "heart disease" and "Aspirin"). The text describes a protective/reducing effect, which the guard incorrectly treats as non-causal association.

**Root Issue**: The PGM guard logic in `relation_result_to_id_pair` v0003 has an overly broad associative phrase filter that catches "risk of" even when the context is about risk reduction (which is a causal relationship—the drug reduces risk of the disease). The guard does not distinguish between "risk of" (association) and "reduce the risk of" (causal protective effect).

### False Positive Analysis
- No false positives detected.

## 3) Agent Modification Suggestions

### Suggestion 1: Refine PGM associative guard in `relation_result_to_id_pair`

**Target Agent**: `relation_result_to_id_pair` (v0003 → v0004)

**What to Change**: In the PGM process code, modify the `associative_phrases` guard to exclude phrases that appear in a causal protective context (e.g., "reduce the risk of", "lower the risk of", "decrease the risk of", "prevent"). Specifically, before applying the associative override, check if the text contains a protective/causal verb phrase within 30 characters of the associative phrase.

**Expected Impact**: Fixes the FN in Sample 1 without introducing new FPs. The text "Aspirin may reduce the risk of heart disease" would no longer be overridden because "reduce the risk of" is a causal protective statement.

**Why Easy**: Single PGM code change in an existing agent. No new dependencies, no external APIs. The change is a small guard condition added before the associative override block.

### Suggestion 2: Add protective/causal context detection to LLM prompt

**Target Agent**: `relation_verify_llm` (v0010 → v0011)

**What to Change**: Add a new Condition to the prompt template: "If the article states that {head} reduces, lowers, decreases, or prevents the risk of {tail}, answer '$' (this is a causal protective relationship)."

**Expected Impact**: Reinforces correct LLM behavior for protective causal statements. Currently the LLM correctly returns `$` for Sample 1, but this change makes the behavior more robust across similar cases.

**Why Easy**: Single prompt template modification. No code changes needed. The LLM already handles this correctly, but explicit instruction reduces variance.

### Suggestion 3: Add protective verb exclusion to PGM negation guard

**Target Agent**: `relation_result_to_id_pair` (v0003 → v0004)

**What to Change**: In the `negation_phrases` list, add a pre-check: if the text contains protective causal verbs ("reduce", "lower", "decrease", "prevent") within 30 characters of "risk of", skip the associative override for that phrase.

**Expected Impact**: Prevents the associative guard from incorrectly overriding causal protective statements. This is the most targeted fix for the observed FN.

**Why Easy**: Single PGM code change. No new dependencies. The logic is a simple string proximity check already used elsewhere in the same agent.