## 1) Metrics

**Overall Metrics (Micro)**

| Metric | Value |
|--------|-------|
| Precision | 0.0 |
| Recall | 0.0 |
| F1 | 0.0 |
| TP | 0 |
| FP | 0 |
| FN | 8 |

**Macro Metrics**

| Metric | Value |
|--------|-------|
| Precision | 0.0 |
| Recall | 0.0 |
| F1 | 0.0 |

**F1 Distribution**

| Stat | Value |
|------|-------|
| Mean | 0.0 |
| Std | 0.0 |
| Min | 0.0 |
| Max | 0.0 |

**Per-Sample Metrics**

| Sample ID | Precision | Recall | F1 | TP | FP | FN |
|-----------|-----------|--------|----|----|----|----|
| 1 | 0.0 | 0.0 | 0.0 | 0 | 0 | 4 |
| 2 | 0.0 | 0.0 | 0.0 | 0 | 0 | 4 |

**Agent Version Mapping**

| Agent ID | Version Used |
|----------|-------------|
| chemdisgene_pair_generate | current |
| chemdisgene_re_chem_disease_affects | current |
| chemdisgene_re_gene_disease_marker | current |
| chemdisgene_re_gene_disease_therapeutic | current |
| chemdisgene_re_chem_gene_expression | current |
| chemdisgene_re_chem_gene_aff_expr | current |
| chemdisgene_re_chem_gene_inc_activity | current |
| chemdisgene_re_chem_gene_activity | current |
| chemdisgene_re_chem_gene_transport | current |
| chemdisgene_re_chem_gene_aff_local | current |
| chemdisgene_re_chem_gene_aff_bind | current |
| chemdisgene_re_chem_gene_inc_metab | current |
| chemdisgene_re_chem_gene_dec_metab | current |
| chemdisgene_re_synonym | current |
| chemdisgene_re_hypernyms | current |
| chemdisgene_answer_map | current |
| chemdisgene_result_to_relation | current |

**Error Totals:** 8 FN, 0 FP

## 2) FN and FP Analysis

**False Negative Analysis**

Both samples have 0 predicted relations (empty `pairs` arrays) against 4 gold relations each, resulting in 8 total FN. The root cause is upstream of the RE verification agents.

**Sample 1** (`Aspirin may reduce the risk of heart disease.`): The `entities` list contains 19 entries from a different article (obesity, Orlistat, pancreatic lipase, etc.) — none match the text. The `chemdisgene_pair_generate` PGM iterates over these entities to create pairs. Since no entities from the actual text are present, no pairs are generated for the gold relation `Aspirin | chem_disease:therapeutic | heart disease`. The pipeline never reaches the RE verification step for the correct entities.

**Sample 2** (`Metformin is commonly used to treat type 2 diabetes.`): Same issue — the `entities` list is identical to Sample 1 (copied from a different article). No entities matching `Metformin` or `type 2 diabetes` are present, so no pairs are generated for the gold relation `Metformin | chem_disease:therapeutic | type 2 diabetes`.

**Root Cause:** The input entities are incorrect/mismatched for both samples. The `chemdisgene_pair_generate` agent correctly generates all possible pairs from the provided entities, but since those entities do not correspond to the text, no valid pairs are produced. The RE verification agents never receive the correct head/tail pairs to evaluate.

**False Positive Analysis:** 0 FP — no relations were predicted at all.

## 3) Agent Modification Suggestions

### Suggestion 1: Add entity extraction fallback in `chemdisgene_pair_generate`

- **Target Agent:** `chemdisgene_pair_generate`
- **What to Change:** Add a PGM guard that checks if the input `entities` dict is empty or contains no entries matching the text. If so, perform a simple regex-based extraction of capitalized biomedical terms from the text (e.g., `re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)`) and assign them as `Chemical` type entities. This ensures at least some pairs are generated.
- **Expected Impact:** Prevents complete pipeline failure when input entities are missing/mismatched. Would generate pairs for `Aspirin` and `heart disease` in Sample 1, and `Metformin` and `type 2 diabetes` in Sample 2.
- **Why Easy:** Single PGM code change in existing agent; no new dependencies or tools.

### Suggestion 2: Add text-entity overlap validation in `chemdisgene_pair_generate`

- **Target Agent:** `chemdisgene_pair_generate`
- **What to Change:** Before generating pairs, filter the input entities to only include those whose text appears in the input `text` (case-insensitive substring match). Add a guard: `if name.lower() not in text.lower(): continue` in the entity iteration loop.
- **Expected Impact:** Prevents generation of pairs from entities that don't appear in the text, reducing noise and focusing on relevant pairs. In the current experiment, this would filter out all 19 mismatched entities, resulting in 0 pairs — same outcome. However, combined with Suggestion 1, it would ensure only text-relevant entities are used.
- **Why Easy:** Single line addition in existing PGM code; no new dependencies.

### Suggestion 3: Add entity type validation in `chemdisgene_pair_generate`

- **Target Agent:** `chemdisgene_pair_generate`
- **What to Change:** Add a guard that validates entity types against the expected types in the `templates` dictionary. If an entity has an unrecognized type (e.g., `Disease` for `pancreatic lipase enzyme` which is actually a gene/protein), skip it or reclassify it based on the entity ID prefix (e.g., `OMIM:` → `Gene`, `MESH:` → `Chemical` or `Disease` based on MESH tree).
- **Expected Impact:** Reduces invalid pair generation from misclassified entities. In the current data, `pancreatic lipase enzyme` (OMIM:614338) is labeled `Disease` but should be `Gene` — this would prevent incorrect `Chemical-Disease` pairs and enable correct `Chemical-Gene` pairs.
- **Why Easy:** Simple PGM logic change; uses existing entity ID metadata already present in the input.