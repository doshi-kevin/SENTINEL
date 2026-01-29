import os
import json
import torch
import pandas as pd
import numpy as np
from torch_geometric.data import Dataset, Data
from tqdm import tqdm
import glob

class SentinelDataset(Dataset):
    def __init__(self, root, transform=None, pre_transform=None):
        """
        root: Directory containing 'graphs' folder and 'labels.csv'
        """
        self.graphs_dir = os.path.join(root, 'graphs')
        self.labels_path = os.path.join(root, 'labels.csv')
        
        # Load labels
        self.labels_df = pd.read_csv(self.labels_path)
        self.window_to_label = dict(zip(self.labels_df['window_id'], self.labels_df['label']))
        
        # Get all graph files
        self.graph_files = sorted(glob.glob(os.path.join(self.graphs_dir, "*.json")))
        
        # Define feature mappings
        self.node_numeric_fields = [
            "degree", "in_degree", "out_degree", "event_count", "event_type_count", 
            "ts_var", "closeness", "betweenness", "pagerank", "cluster_coeff", 
            "avg_ts_gap", "last_seen_delta", "burst_flag", "activity_rate", 
            "temporal_entropy", "time_sin", "time_cos"
        ]
        
        # Common system events (expand as needed or make dynamic)
        self.event_types = [
            "EVENT_OPEN", "EVENT_READ", "EVENT_WRITE", "EVENT_CLOSE", 
            "EVENT_EXECUTE", "EVENT_EXIT", "EVENT_FORK", "EVENT_Clone",
            "EVENT_MODIFY_FILE", "EVENT_CREATE_FILE", "EVENT_DELETE_FILE"
        ]
        self.event_map = {e: i for i, e in enumerate(self.event_types)}
        
        super(SentinelDataset, self).__init__(root, transform, pre_transform)
        
        # Load all data into memory for speed
        print("Loading data into memory...")
        self.data_list = []
        path = self.processed_dir
        for f in self.processed_file_names:
            self.data_list.append(torch.load(os.path.join(path, f)))
        print("Data loaded!")

    @property
    def raw_file_names(self):
        return [os.path.basename(f) for f in self.graph_files]

    @property
    def processed_file_names(self):
        # We process all files into individual .pt files
        return [f.replace('.json', '.pt') for f in self.raw_file_names]

    def download(self):
        pass # Data is already local

    def process(self):
        # Ensure processed directory exists
        processed_dir = self.processed_dir
        if not os.path.exists(processed_dir):
            os.makedirs(processed_dir)

        print(f"Processing {len(self.graph_files)} graphs...")
        
        for idx, file_path in enumerate(tqdm(self.graph_files)):
            # Check if already processed
            out_path = os.path.join(processed_dir, os.path.basename(file_path).replace('.json', '.pt'))
            if os.path.exists(out_path):
                continue
                
            try:
                with open(file_path, 'r') as f:
                    raw_data = json.load(f)
                
                # --- PROCESS NODES ---
                x = []
                for node in raw_data['nodes']:
                    features = []
                    
                    # 1. Node Type (Subject vs Object) - One-Hot [1, 0] or [0, 1]
                    # dataset uses 'node_type_flag' 1 for subject, 0 for object
                    is_subject = node.get('node_type_flag', 0)
                    features.append(float(is_subject))
                    features.append(1.0 - float(is_subject))
                    
                    # 2. Numeric Features
                    for field in self.node_numeric_fields:
                        features.append(float(node.get(field, 0.0)))
                    
                    x.append(features)
                
                x = torch.tensor(x, dtype=torch.float)
                
                # --- PROCESS EDGES ---
                edge_indices = []
                edge_attrs = []
                
                if 'links' in raw_data:
                    for link in raw_data['links']:
                        src = link['source']
                        dst = link['target']
                        edge_indices.append([src, dst])
                        
                        # Edge Features: Event Type (One-Hot)
                        event_type = link.get('event', 'UNKNOWN')
                        evt_idx = self.event_map.get(event_type, len(self.event_types)) # Map unknown to extra index
                        
                        # Timestamp (optional, maybe normalized delta?)
                        # For now, just use event type embedding
                        # Create one-hot vector for event type
                        evt_vec = [0.0] * (len(self.event_types) + 1)
                        evt_vec[evt_idx] = 1.0
                        
                        edge_attrs.append(evt_vec)
                
                if len(edge_indices) > 0:
                    edge_index = torch.tensor(edge_indices, dtype=torch.long).t().contiguous()
                    edge_attr = torch.tensor(edge_attrs, dtype=torch.float)
                else:
                    edge_index = torch.empty((2, 0), dtype=torch.long)
                    edge_attr = torch.empty((0, len(self.event_types) + 1), dtype=torch.float)

                # --- LABELS ---
                # Filename format: window_XXXX.json -> extract ID
                # But we can also look up by window_id if we have it.
                # Assuming labels.csv matches raw filenames or we parse ID.
                # Let's derive ID from filename for now?
                # window_0000.json -> 0
                fname = os.path.basename(file_path)
                win_id_str = fname.split('_')[1].split('.')[0]
                win_id = int(win_id_str)
                
                y_label = self.window_to_label.get(win_id, 0) # Default to 0 (benign) labels miss
                y = torch.tensor([y_label], dtype=torch.long)

                # encapsulating data
                data = Data(x=x, edge_index=edge_index, edge_attr=edge_attr, y=y, window_id=win_id)
                
                torch.save(data, out_path)
            
            except Exception as e:
                print(f"Error processing {file_path}: {e}")

    def len(self):
        return len(self.processed_file_names)

    def get(self, idx):
        return self.data_list[idx]

if __name__ == "__main__":
    # Test the dataset loading
    import sys
    
    root_dir = r"c:\SENTINEL\data\model_ready"
    dataset = SentinelDataset(root=root_dir)
    print(f"Dataset created with {len(dataset)} graphs.")
    
    data = dataset[0]
    print("Sample Graph 0:")
    print(data)
    print(f"Node Features (x): {data.x.shape}")
    print(f"Edge Index: {data.edge_index.shape}")
    print(f"Edge Attr: {data.edge_attr.shape}")
    print(f"Label (y): {data.y}")
