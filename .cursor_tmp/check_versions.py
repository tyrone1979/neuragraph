import json
d = json.loads(open('meta/agent_versions/relation_result_to_id_pair/index.json', encoding='utf-8').read())
print('latest:', d.get('latest'))
vs = [v for v in d.get('versions', []) if 'opt_loop' in str(v.get('change_note', ''))]
print(f'opt versions: {len(vs)}')
for v in vs[-5:]:
    print(f"  {v['version']}: {v['change_note'][:120]}")
