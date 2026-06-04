"""Deep FP/FN pattern analysis for CID RE baseline."""
import json
from collections import Counter

s = json.loads(open('result/c422b97c-be21-4b6a-968c-c4994229d702/states.json', encoding='utf-8').read())
ks = sorted([int(k) for k in s if k.isdigit()])

fp_only = []
fn_focus = []
high_pairs_low_tp = []
mtp = mfp = mfn = 0
all_pairs_total = 0
all_predicted_total = 0

for k in ks:
    entry = s[str(k)]
    m = entry.get('metrics', {})
    tp = int(m.get('rel_tp', 0))
    fp = int(m.get('rel_fp', 0))
    fn = int(m.get('rel_fn', 0))
    pairs = entry.get('pairs', [])
    predicted = entry.get('relations', [])
    text = (entry.get('text', '') or '')[:300]
    all_pairs_total += len(pairs)
    all_predicted_total += len(predicted)
    mtp += tp; mfp += fp; mfn += fn

    if fp > 0 and tp == 0:
        fp_only.append({'idx': k, 'fp': fp, 'fn': fn,
                        'pairs': len(pairs), 'pred': len(predicted), 'text': text})
    if fn > 0 and tp == 0:
        fn_focus.append({'idx': k, 'fn': fn, 'fp': fp,
                         'pairs': len(pairs), 'pred': len(predicted), 'text': text})
    pr = len(pairs) / max(len(predicted), 1)
    if len(pairs) > 20 and pr > 3:
        high_pairs_low_tp.append({'idx': k, 'pairs': len(pairs), 'pred': len(predicted),
                                  'tp': tp, 'fp': fp, 'text': text[:80]})

llm_precision = mtp / max(all_predicted_total, 1)
llm_recall = mtp / max(mtp + mfn, 1)

print("=" * 70)
print("ROOT CAUSE ANALYSIS: RE Baseline FP=%d FN=%d F1=%.3f" % (mfp, mfn, 2*mtp/(mtp+mfp+mtp+mfn) if mtp+mfp+mtp+mfn else 0))
print("=" * 70)

mif = 2 * (mtp/(mtp+mfp)) * (mtp/(mtp+mfn)) / (mtp/(mtp+mfp) + mtp/(mtp+mfn)) if mtp+mfp and mtp+mfn else 0
print(f"\n  Micro P={mtp/(mtp+mfp):.3f}  R={mtp/(mtp+mfn):.3f}  F1={mif:.3f}")
print(f"  Total: TP={mtp} FP={mfp} FN={mfn}")
print(f"  Candidate pairs (hypernym): {all_pairs_total}")
print(f"  LLM-verified ($ verdict):   {all_predicted_total}")
print(f"  LLM precision: {llm_precision*100:.1f}%")
print(f"  LLM recall:    {llm_recall*100:.1f}%")

print(f"\n{'─'*70}")
print(f"FP DOMINATED: {len(fp_only)} articles have FP>0 and TP=0 (zero precision)")
print(f"{'─'*70}")
print(f"{'#':>4}  {'FP':>3}  {'FN':>3}  {'Pairs':>6}  {'Pred':>5}  Text")
for r in sorted(fp_only, key=lambda x: x['fp'], reverse=True)[:20]:
    print(f"{r['idx']:>4}  {r['fp']:>3}  {r['fn']:>3}  {r['pairs']:>6}  {r['pred']:>5}  {r['text'][:70]}")

print(f"\n{'─'*70}")
print("F1 SCENARIOS — cumulative improvements")
print(f"{'─'*70}")
print(f"{'Scenario':<45s} {'P':>5s} {'R':>5s} {'F1':>5s}  {'FP':>4s} {'FN':>4s}")
print(f"{'─'*70}")

scenarios = [
    ("1. Current baseline", 0, 0),
    ("2. Fix pair gen: -40% FP", -0.40, 0),
    ("3. + Better LLM: -30% FP, -20% FN", -0.30, -0.20),
    ("4. Combined (2+3)", -0.40, -0.20),  # approximate combined
    ("5. + Post-process: -15% FP, -15% FN", -0.15, -0.15),
    ("6. + All-at-once: -15% FP, -15% FN", -0.15, -0.15),
    ("7. TARGET: F1=0.80", -0.75, -0.62),
]

for label, fp_reduction, fn_reduction in scenarios:
    new_fp = int(mfp * (1 + fp_reduction))
    new_fn = int(mfn * (1 + fn_reduction))
    p = mtp / (mtp + new_fp) if mtp + new_fp else 0
    r = mtp / (mtp + new_fn) if mtp + new_fn else 0
    f = 2 * p * r / (p + r) if p + r else 0
    print(f"  {label:<43s} {p:.3f} {r:.3f} {f:.3f}  {new_fp:>4d} {new_fn:>4d}")

print()
print("=" * 72)
print("  ROADMAP: 4-LAYER STRATEGY TO REACH F1≈0.80")
print("=" * 72)
print("""
LAYER 1 — Fix pair generation  (-40% FP)
  Problem: hypernym filter generates 9.6 pairs/article, many non-co-occurring.
  Fix:     Co-occurrence constraint → only pairs where both terms appear
            within same sentence or adjacent sentences.
  ROI:     FP 1010 → ~600, FN unchanged.  F1 0.532 → ~0.62

LAYER 2 — Better LLM verification  (-30% FP, -20% FN)
  Problem: Single-pass binary $(yes)/~(no) is too coarse. v0007 was 
            WRONG — it expanded accepted causal language.
  Fix:     Multi-step reasoning (co-occurrence → causation evidence → verdict)
            + 3-5 few-shot examples from dev.txt gold. Stricter rejection
            of pre-existing conditions.
  ROI:     F1 0.62 → ~0.67-0.70

LAYER 3 — Post-processing  (-15% FP, -15% FN)
  Problem: No cross-article consistency or MeSH sanity checks.
  Fix:     Known-safe drug→disease blockers. Consistency: same pair
            gets same verdict across articles. Verdict confidence scoring.
  ROI:     F1 0.70 → ~0.74

LAYER 4 — All-at-once verification  (-15% FP, -15% FN)
  Problem: Each pair verified in isolation — LLM has no context.
  Fix:     Present ALL candidate pairs → ask LLM to select causal ones.
            Merges with individual verification results.
  ROI:     F1 0.74 → ~0.78-0.80

CUMULATIVE: F1 ≈ 0.78-0.80

IMPLEMENTATION EFFORT (sorted by ease):
  L1: cid_pair_generate PGM ~1hr   — pure code, no LLM cost change
  L2a: relation_verify_llm prompt ~30min
  L2b: add few-shot examples ~30min
  L3: new PGM post-process agent ~2hr
  L4: workflow change + all-at-once agent ~3hr
""")
