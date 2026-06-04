import json
s=json.loads(open('result/c422b97c-be21-4b6a-968c-c4994229d702/states.json').read())
ks=[int(k) for k in s if k.isdigit()]
print(f'Total samples: {len(ks)}')
err=0; zero=0; ok=0
for k in sorted(ks):
    m=s[str(k)].get('metrics',{})
    if not m:
        print(f'#{k}: no metrics dict')
        err+=1; continue
    if m.get('_metrics_error'):
        print(f'#{k}: _metrics_error={m.get("_metrics_error")[:150]}')
        err+=1; continue
    tp=int(m.get('rel_tp',0)); fp=int(m.get('rel_fp',0)); fn=int(m.get('rel_fn',0))
    if tp==0 and fp==0 and fn==0:
        print(f'#{k}: tp=fp=fn=0 (pairs={len(s[k].get("pairs",[]))}, relations={s[k].get("relations",[])})')
        zero+=1; continue
    ok+=1
print(f'\nOK={ok}  zero_tp_fp_fn={zero}  metrics_error={err}')
