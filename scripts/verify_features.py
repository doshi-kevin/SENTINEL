import json
from pathlib import Path

# Read a few sample graphs to verify features
graph_dir = Path("data/model_ready/graphs")

# Check benign graph
benign_graph = graph_dir / "window_0000.json"
print("=" * 60)
print("BENIGN GRAPH (window_0000.json)")
print("=" * 60)
with open(benign_graph) as f:
    g = json.load(f)
    if g['nodes']:
        print(f"Total nodes: {len(g['nodes'])}")
        print(f"Total edges: {len(g['links'])}")
        print(f"\nNode 0 features:")
        node = g['nodes'][0]
        feature_keys = sorted([k for k in node.keys() if k != 'id'])
        for key in feature_keys:
            print(f"  {key}: {node[key]}")
        print(f"\nTotal features: {len(feature_keys)}")

# Check attack graph
attack_graph = graph_dir / "window_0078.json"
print("\n" + "=" * 60)
print("ATTACK GRAPH (window_0078.json)")
print("=" * 60)
with open(attack_graph) as f:
    g = json.load(f)
    if g['nodes']:
        print(f"Total nodes: {len(g['nodes'])}")
        print(f"Total edges: {len(g['links'])}")
        print(f"\nNode 0 features:")
        node = g['nodes'][0]
        feature_keys = sorted([k for k in node.keys() if k != 'id'])
        for key in feature_keys:
            print(f"  {key}: {node[key]}")
        print(f"\nTotal features: {len(feature_keys)}")

# List expected features from FeatureEngineer
print("\n" + "=" * 60)
print("EXPECTED FEATURES FROM FeatureEngineer.NODE_KEYS")
print("=" * 60)
expected = [
    "node_type_flag", "degree", "in_degree", "out_degree",
    "event_count", "event_type_count", "ts_var",
    "closeness", "betweenness", "pagerank", "cluster_coeff",
    "avg_ts_gap", "last_seen_delta", "burst_flag",
    "activity_rate", "temporal_entropy",
    "time_sin", "time_cos"
]
print(f"Expected features ({len(expected)}):")
for i, feat in enumerate(expected, 1):
    print(f"  {i:2d}. {feat}")

# Check which are present
print("\n" + "=" * 60)
print("VERIFICATION")
print("=" * 60)
missing = set(expected) - set(feature_keys)
extra = set(feature_keys) - set(expected)
if missing:
    print(f"Missing features: {missing}")
if extra:
    print(f"Extra features: {extra}")
if not missing and not extra:
    print("✓ All expected features present!")
    print("✓ No extra features!")
else:
    # Account for node_type being stored
    if extra == {'node_type'}:
        print("✓ All expected features present!")
        print("Note: 'node_type' is stored for reference (not a feature)")

