import json, os
p = 'result/c422b97c-be21-4b6a-968c-c4994229d702/states.json'
mtime = os.path.getmtime(p)
import datetime
print(f'mtime: {datetime.datetime.fromtimestamp(mtime).strftime("%H:%M:%S")}')
s = json.loads(open(p, encoding='utf-8').read())
ks = [int(k) for k in s if k.isdigit()]
print(f'samples: {len(ks)} (latest: {max(ks)})')
mtp=mfp=mfn=0
for k in sorted(ks):
    m = s[str(k)].get('metrics', {})
    mtp += int(m.get('rel_tp',0)); mfp += int(m.get('rel_fp',0)); mfn += int(m.get('rel_fn',0))
mip=mtp/(mtp+mfp) if mtp+mfp else 0; mir=mtp/(mtp+mfn) if mtp+mfn else 0
mif=2*mip*mir/(mip+mir) if mip+mir else 0
print(f'Micro: P={mip:.3f}  R={mir:.3f}  F1={mif:.3f}  (TP={mtp}  FP={mfp}  FN={mfn})')
