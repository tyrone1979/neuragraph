import json
s = json.loads(open('result/c422b97c-be21-4b6a-968c-c4994229d702/states.json', encoding='utf-8').read())
ks = [int(k) for k in s if k.isdigit()]
mtp=mfp=mfn=0; mp=[]; mr=[]; mf=[]; mkeys=set()
for k in sorted(ks):
    m = s[str(k)].get('metrics',{})
    for mk in m: mkeys.add(mk)
    tp=int(m.get('rel_tp',0)); fp=int(m.get('rel_fp',0)); fn=int(m.get('rel_fn',0))
    mtp+=tp; mfp+=fp; mfn+=fn
    mp.append(float(m.get('precision',0))); mr.append(float(m.get('recall',0))); mf.append(float(m.get('f1',0)))
n=len(mf)
mip=round(mtp/(mtp+mfp),3) if mtp+mfp else 0; mir=round(mtp/(mtp+mfn),3) if mtp+mfn else 0
mif=round(2*mip*mir/(mip+mir),3) if mip+mir else 0
map_=round(sum(mp)/n,3) if n else 0; mar=round(sum(mr)/n,3) if n else 0; maf=round(sum(mf)/n,3) if n else 0
summary = {
    "runner_id": "wf_cid_re_llm_linear",
    "exp_id": "c422b97c-be21-4b6a-968c-c4994229d702",
    "dataset": "cdr_test_500.csv",
    "n": 500,
    "aggregate": {
        "n_samples": n,
        "micro": [mip, mir, mif],
        "macro": [map_, mar, maf],
        "tp": mtp, "fp": mfp, "fn": mfn,
        "metric_keys": sorted(mkeys),
    }
}
open('result/perf34_wf_cid_re_llm_linear_summary.json','w').write(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
