import json
g = json.load(open('data/auto_processed/graphs/window_00042.json'))
print('Node 0 features:')
for k, v in g['nodes'][0].items():
    if k != 'id':
        print(f"  {k}: {v}")
