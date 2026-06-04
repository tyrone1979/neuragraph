import json
s=json.loads(open('result/c422b97c-be21-4b6a-968c-c4994229d702/states.json',encoding='utf-8').read())
bad=[]
for k in sorted(s, key=lambda x: int(x) if x.isdigit() else 0):
    if not k.isdigit(): continue
    m=s[k].get('metrics',{})
    if not m or m.get('_metrics_error') or (int(m.get('rel_tp',0))==0 and int(m.get('rel_fp',0))==0 and int(m.get('rel_fn',0))==0):
        tp=int(m.get('rel_tp',0)); fp=int(m.get('rel_fp',0)); fn=int(m.get('rel_fn',0))
        err=m.get('_metrics_error','')
        r=s[k].get('relations',[])
        p=s[k].get('pairs',[])
        print(f'#{k}: tp={tp} fp={fp} fn={fn} err={err[:120]} relations={r[:3]} pair_count={len(p)}')
print(f'---')
ok=0
for k in sorted(s, key=lambda x: int(x) if x.isdigit() else 0):
    if not k.isdigit(): continue
    m=s[k].get('metrics',{})
    if m and not m.get('_metrics_error') and (int(m.get('rel_tp',0))>0 or int(m.get('rel_fp',0))>0 or int(m.get('rel_fn',0))>0):
        ok+=1
print(f'OK samples: {ok}')
print(f'Bad samples: {len(s)-ok}')
