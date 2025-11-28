from src.dataset.sentinel_pyg_dataset import SentinelGraphDataset

dataset = SentinelGraphDataset(
    graphs_dir="data/model_ready/graphs",
    labels_csv="data/model_ready/labels.csv"
)

print("Total graphs:", len(dataset))

sample = dataset[0]
print("Node features shape:", sample.x.shape)
print("Edge index shape:", sample.edge_index.shape)
print("Label:", sample.y)
