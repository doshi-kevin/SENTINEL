import torch
from torch_geometric.loader import DataLoader
from dataset import SentinelDataset
from model import SentinelGNN
import os
import json
from tqdm import tqdm
import numpy as np

# --- CONFIG ---
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
BATCH_SIZE = 64
ROOT_DIR = r"c:\SENTINEL\data\model_ready"
MODEL_PATH = r"c:\SENTINEL\backend\models\sentinel_encoder.pt"
OUTPUT_PATH = r"c:\SENTINEL\data\model_ready\embeddings.csv"

def generate():
    print(f"Using device: {DEVICE}")
    
    # Load Data
    dataset = SentinelDataset(root=ROOT_DIR)
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=False)
    
    # Load Model
    # Must match training config
    model = SentinelGNN(input_dim=19, hidden_dim=64, embedding_dim=32, edge_dim=12).to(DEVICE)
    model.load_state_dict(torch.load(MODEL_PATH))
    model.eval()
    
    print("Generating embeddings...")
    
    results = []
    
    with torch.no_grad():
        for data in tqdm(loader):
            data = data.to(DEVICE)
            
            # Forward pass (get representation h, not projection z)
            h = model(data.x, data.edge_index, data.edge_attr, data.batch)
            
            # Move to CPU
            embeddings = h.cpu().numpy()
            window_ids = data.window_id.cpu().numpy()
            labels = data.y.cpu().numpy()
            
            for i in range(len(window_ids)):
                results.append({
                    "window_id": int(window_ids[i]),
                    "label": int(labels[i]),
                    "embedding": embeddings[i].tolist()
                })
    
    # Save to CSV for easy parsing or JSON
    # let's do CSV with embedding as string or JSON
    # JSON is safer for list of floats
    import pandas as pd
    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(results)} embeddings to {OUTPUT_PATH}")

if __name__ == "__main__":
    generate()
