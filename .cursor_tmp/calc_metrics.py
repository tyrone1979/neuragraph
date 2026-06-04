import json
s = json.loads(open('result/c422b97c-be21-4b6a-968c-c4994229d702/states.json', encoding='utf-8').read())
ks = [int(k) for k in s if k.isdigit()]
mtp = mfp = mfn = 0
mp, mr, mf = [], [], []
for k in sorted(ks):
    m = s[str(k)].get('metrics', {})
    tp = int(m.get('rel_tp') or m.get('tp') or 0)
    fp = int(m.get('rel_fp') or m.get('fp') or 0)
    fn = int(m.get('rel_fn') or m.get('fn') or 0)
    mtp += tp; mfp += fp; mfn += fn
    p = float(m.get('precision', 0))
    r = float(m.get('recall', 0))
    f = float(m.get('f1', 0))
    mp.append(p); mr.append(r); mf.append(f)
n = len(mf)
mip = mtp / (mtp + mfp) if mtp + mfp else 0
mir = mtp / (mtp + mfn) if mtp + mfn else 0
mif = 2 * mip * mir / (mip + mir) if mip + mir else 0
map_ = sum(mp) / n if n else 0
mar = sum(mr) / n if n else 0
maf = sum(mf) / n if n else 0
print(f'Samples: {n}/{len(ks)}')
print(f'Micro:  P={mip:.3f}  R={mir:.3f}  F1={mif:.3f}  (TP={mtp}  FP={mfp}  FN={mfn})')
print(f'Macro:  P={map_:.3f}  R={mar:.3f}  F1={maf:.3f}')
