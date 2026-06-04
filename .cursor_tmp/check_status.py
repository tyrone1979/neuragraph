import json, os, datetime
p = 'result/c422b97c-be21-4b6a-968c-c4994229d702/states.json'
mtime = os.path.getmtime(p)
s = json.loads(open(p, encoding='utf-8').read())
ks = [int(k) for k in s if k.isdigit()]
mtp=mfp=mfn=0; mp=[]; mr=[]; mf=[]
for k in sorted(ks):
    m = s[str(k)].get('metrics',{})
    tp=int(m.get('rel_tp',0)); fp=int(m.get('rel_fp',0)); fn=int(m.get('rel_fn',0))
    mtp+=tp; mfp+=fp; mfn+=fn
    mp.append(float(m.get('precision',0))); mr.append(float(m.get('recall',0))); mf.append(float(m.get('f1',0)))
n=len(mf)
mip=mtp/(mtp+mfp) if mtp+mfp else 0; mir=mtp/(mtp+mfn) if mtp+mfn else 0
mif=2*mip*mir/(mip+mir) if mip+mir else 0
map_=sum(mp)/n if n else 0; mar=sum(mr)/n if n else 0; maf=sum(mf)/n if n else 0
print(f'Updated: {datetime.datetime.fromtimestamp(mtime).strftime("%H:%M:%S")}')
print(f'Samples: {n}/{len(ks)}')
print(f'Micro:  P={mip:.3f}  R={mir:.3f}  F1={mif:.3f}  (TP={mtp}  FP={mfp}  FN={mfn})')
print(f'Macro:  P={map_:.3f}  R={mar:.3f}  F1={maf:.3f}')
# Check terminal
t = open(r'C:\Users\tyron\.cursor\projects\d-projects-neuragraph\terminals\837854.txt', encoding='utf-8').read()
alive = 'ended_at' not in t
last_article = ''
import re
m = re.findall(r'(?m)^  \[wf_cid_re_llm_linear\] (\d+)/500$', t)
if m:
    last_article = m[-1]
print(f'Terminal alive: {alive}')
print(f'Terminal last article: {last_article}/500')
