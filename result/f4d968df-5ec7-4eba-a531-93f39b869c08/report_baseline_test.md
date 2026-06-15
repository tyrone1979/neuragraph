## 1) Metrics

**Overall Metrics (Micro)**

| Metric | Value |
|--------|-------|
| Precision | 0.0 |
| Recall | 0.0 |
| F1 | 0.0 |
| TP | 0 |
| FP | 10 |
| FN | 6 |

**Overall Metrics (Macro)**

| Metric | Value |
|--------|-------|
| Precision | 0.0 |
| Recall | 0.0 |
| F1 | 0.0 |

**F1 Distribution**

| Mean | Std | Min | Max |
|------|-----|-----|-----|
| 0.0 | 0.0 | 0.0 | 0.0 |

**Per-Sample Metrics**

| Sample ID | Precision | Recall | F1 | TP | FP | FN |
|-----------|-----------|--------|----|----|----|----|
| 1 | 0.0 | 0.0 | 0.0 | 0 | 5 | 3 |
| 2 | 0.0 | 0.0 | 0.0 | 0 | 5 | 3 |

**Agent Version Mapping**

| Agent ID | Version Used |
|----------|-------------|
| relation_extract_pubtator | current |
| eval_metrics_relation | current |

## 2) FN and FP Analysis

**False Positives (10 total, 5 per sample)**

Both samples produce identical FP relations:
- `D008094 | CID | D006331` (lithium → cardiac disease)
- `D016651 | CID | D003866` (lithium carbonate → neurologic depression)
- `D016651 | CID | D001145` (lithium carbonate → cardiac arrhythmia)
- `D016651 | CID | D006330` (lithium carbonate → heart disease)
- `D016651 | CID | D003490` (lithium carbonate → cyanosis)

**False Negatives (6 total, 3 per sample)**

Both samples have 3 FN relations (not explicitly listed in states, but inferred from metrics: 3 FN per sample with 0 TP).

**Root Cause Analysis**

The `relation_extract_pubtator` agent is producing the same set of 5 relations for both samples, despite the samples having completely different texts:
- Sample 1 text: "Aspirin may reduce the risk of heart disease."
- Sample 2 text: "Metformin is commonly used to treat type 2 diabetes."

The predicted relations reference entities (lithium, lithium carbonate, cardiac disease, neurologic depression, etc.) that do not appear in either text. The entities list in both samples contains identical entity annotations (13 entities including lithium carbonate, tricuspid valve regurgitation, etc.), which appear to be from a different document entirely. This indicates the `entities` input to `relation_extract_pubtator` is being populated with incorrect/static entity data, causing the PubTator extractor to generate relations for entities not present in the actual text.

The `eval_metrics_relation` agent correctly normalizes and compares relations, but since the predicted relations are entirely wrong (matching no gold relations), all predictions are FP and all gold relations are FN.

## 3) Agent Modification Suggestions

### Suggestion 1: Fix entity input binding in graph

**Target Agent:** `relation_extract_pubtator`

**What to Change:** In graph bindings, change `'entities': '{{ START.entities }}'` to `'entities': '{{ START.filtered_entities }}'` or ensure the correct entity field is passed from the input dataset.

**Expected Impact:** The PubTator extractor will receive the correct entities for each sample text, producing relations that match the actual content rather than static/wrong entities.

**Why Easy:** This is a single binding change in the graph meta (`bindings` section of `wf_re_pubtator_eval`). No code changes needed.

### Suggestion 2: Add entity-text validation guard in relation_extract_pubtator

**Target Agent:** `relation_extract_pubtator`

**What to Change:** Add a PGM guard after `pt.extract_relations()` that filters predicted relations to only include those where the entity text actually appears in the input `text`. Add this before `__result__ = payload.get('relations') or []`:
```python
text_lower = text.lower()
filtered = []
for rel in __result__:
    # rel format: "CHEM_ID | CID | DISEASE_ID"
    # find matching entity text from entities dict
    chem_id, _, disease_id = rel.split(' | ')
    chem_texts = [e['text'] for e in entities if e['id'] == chem_id]
    disease_texts = [e['text'] for e in entities if e['id'] == disease_id]
    if any(t.lower() in text_lower for t in chem_texts) and any(t.lower() in text_lower for t in disease_texts):
        filtered.append(rel)
__result__ = filtered
```

**Expected Impact:** Eliminates FP relations for entities not mentioned in the text. This would reduce FP from 10 to 0 in both samples.

**Why Easy:** This is a small PGM code addition in the existing agent process. No new dependencies or external services.

### Suggestion 3: Add entity presence check before PubTator call

**Target Agent:** `relation_extract_pubtator`

**What to Change:** Before calling `pt.extract_relations()`, add a guard that checks if any entity text from the `entities` dict appears in the input `text`. If none match, return empty relations immediately.

**Expected Impact:** Prevents wasted API calls and spurious relations when entity data is mismatched with text. Provides graceful degradation.

**Why Easy:** Simple text matching check added as early return in the existing PGM process. No new tools or dependencies.