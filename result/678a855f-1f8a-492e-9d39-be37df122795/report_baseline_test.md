## 1) Metrics

**Overall Performance (500 samples)**

| Metric | Micro | Macro |
|--------|-------|-------|
| Precision | 0.4892 | 0.5725 |
| Recall | 0.8527 | 0.8689 |
| F1 | 0.6218 | 0.6467 |

**F1 Distribution (per-article):** mean=0.6467, std=0.2977, min=0.0, max=1.0

**Error Totals:** TP=909, FP=949, FN=157

**Agent Version Mapping (effective)**

| Agent ID | Version Used |
|----------|-------------|
| relation_verify_llm | v0010 |
| relation_result_to_id_pair | v0003 |

## 2) FN and FP Analysis

**False Positive Analysis (dominant error type: 949 FP vs 157 FN)**

The primary FP pattern is **over-generation of relations from co-occurrence or generic toxicity associations** where the LLM verifier (`relation_verify_llm`) outputs `$` for pairs that are merely listed as adverse events in a study, not causally induced by the chemical.

**Top FP articles (examples_detail):**
- **Sample 132** (39 FP): All 5 chemicals (corticosteroid, methylprednisolone acetate, lidocaine, epinephrine, penicillin) paired with all 8 diseases from the article. The text describes a case report of injection complications, but the LLM verifier outputs `$` for every pair, including `penicillin → chorioretinal atrophy` which has no causal link in text.
- **Sample 453** (19 FP): All 5 HIV drugs paired with all listed adverse events (rash, peripheral neuropathy, anemia, hepatitis, etc.) plus `alanine` (a lab value) paired with all diseases. The text reports incidence percentages of adverse events in a cohort study, not causal attribution per drug.
- **Sample 250** (17 FP): All 4 chemotherapy drugs + CPDD paired with all toxicity types (hematologic, GI, nephrotoxicity). The text describes a combination chemotherapy regimen; individual drug-toxicity causal links are not established.
- **Sample 344** (15 FP): Cocaine, ethanol, and cocaethylene paired with all cardiac effects. The text describes combined toxicity, but the LLM outputs `$` for each individual chemical with each effect.
- **Sample 227** (13 FP): Barium compounds and anesthetics paired with all cardiovascular disturbances. The text describes barium-induced effects, but the LLM outputs `$` for unrelated anesthetics (ketamine, xylazine) with all diseases.

**Root cause:** The `relation_verify_llm` prompt's Condition 3 ("if {head} is administered together with other chemical(s) as a combination/co-treatment regimen and {tail} is reported as an adverse event... answer '$' for {head} as a component of the regimen") is too permissive. It causes the LLM to output `$` for every chemical in a multi-drug regimen for every adverse event reported in the study, even when the event is attributed to the combination or to a specific drug. The `relation_result_to_id_pair` PGM guard does not catch these because the LLM output `$` passes through.

**False Negative Analysis (157 FN total)**

FN cases show two patterns:
1. **LLM verifier outputs `~` for true causal relations** (e.g., Sample 62: `propofol → bradycardia` gets `~` despite text stating "both agents are associated with significant hemodynamic side effects" and reporting prevalence data; Sample 104: `heparin → chondrodysplasia punctata` gets `~` despite text describing warfarin-induced embryopathy—heparin is mentioned as replacement, not cause).
2. **Missing entity pairs** (Sample 407: 12 FN, all `oestrogens` and `progestogens` pairs with diseases like stroke, breast cancer, venous thromboembolism—the LLM verifier output `$` for `progestogens → chronic disease` but the gold relations include many specific disease pairs that were never generated because the entity list lacks the specific disease MeSH IDs for some gold relations).

**Root cause for FN:** The `relation_verify_llm` prompt's Assumptions (1.1-1.5) sometimes cause the LLM to output `~` for true causal relations when the text uses associative language (e.g., "associated with", "risk of") rather than explicit causal verbs. The `relation_result_to_id_pair` PGM's associative guard then reinforces this by overriding `$` outputs when associative phrases are within 15 characters of terms.

## 3) Agent Modification Suggestions

### Suggestion 1: Tighten `relation_verify_llm` prompt Condition 3

**Target agent:** `relation_verify_llm` (LLM, v0010)

**What to change:** Modify Condition 3 in the prompt from:
```
3. else if {head} is administered together with other chemical(s) as a combination/co-treatment regimen and {tail} is reported as an adverse event, toxicity, or complication (including incidence or percentage) in patients receiving that regimen, answer '$' for {head} as a component of the regimen—even when the text attributes the event to the combination rather than {head} alone
```
To:
```
3. else if {head} is administered together with other chemical(s) as a combination/co-treatment regimen and {tail} is reported as an adverse event, toxicity, or complication: answer '$' ONLY if the text explicitly attributes {tail} to {head} specifically (e.g., '{head}-induced {tail}', '{head} caused {tail}') or if {head} is the only drug in the regimen known to cause {tail}. If the text attributes {tail} to the combination regimen as a whole or to another specific drug in the regimen, answer '~'.
```

**Expected impact:** Reduces FP by ~40-60% on multi-drug regimen articles (Samples 132, 453, 250, 344, 227, 258, 413, 433, 467). These 10 articles alone contribute ~200 FP.

**Why easy:** Single prompt text change in the existing agent meta. No code changes, no new tools, no external dependencies.

### Suggestion 2: Relax associative guard in `relation_result_to_id_pair`

**Target agent:** `relation_result_to_id_pair` (PGM, v0003)

**What to change:** In the PGM code, increase the distance threshold for associative phrase override from 15 to 50 characters, or remove the associative guard entirely and rely solely on the negation guard.

**Current code (lines ~40-50):**
```python
if abs(idx - tidx) <= 15:
    override = True
```

**Change to:**
```python
if abs(idx - tidx) <= 50:
    override = True
```

**Expected impact:** Reduces FN by ~20-30% on articles where true causal relations use associative language (e.g., "associated with", "risk of", "may cause"). Samples 62, 104, 111, 343 show this pattern.

**Why easy:** Single numeric change in existing PGM agent code. No new logic, no external dependencies.

### Suggestion 3: Add LLM instruction to distinguish causal vs associative language

**Target agent:** `relation_verify_llm` (LLM, v0010)

**What to change:** Add a new Assumption before the existing ones:
```
0. If the article uses only associative language (e.g., 'associated with', 'linked to', 'correlated with', 'risk factor for', 'co-occurrence') without explicit causal verbs (e.g., 'caused', 'induced', 'resulted in', 'led to'), and the text does not state that {head} directly caused {tail}, answer '~'.
```

**Expected impact:** Reduces FP on articles where adverse events are reported as statistical associations in cohort studies (Samples 453, 250, 258, 432). Also reduces FN by preventing the LLM from outputting `$` for associative-only relations that the PGM guard then overrides inconsistently.

**Why easy:** Single prompt addition. No code changes, no new tools.