import torch
import torch.nn.functional as F
from torch_geometric.loader import DataLoader
from dataset import SentinelDataset
from model import SentinelGNN
import os
import random
from tqdm import tqdm

# --- CONFIG ---
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
BATCH_SIZE = 32
LEARNING_RATE = 0.001
EPOCHS = 20
TEMPERATURE = 0.5
EMBEDDING_DIM = 32
HIDDEN_DIM = 64
ROOT_DIR = r"c:\SENTINEL\data\model_ready"
MODEL_SAVE_PATH = r"c:\SENTINEL\backend\models\sentinel_encoder.pt"

# Ensure model dir exists
os.makedirs(os.path.dirname(MODEL_SAVE_PATH), exist_ok=True)

# --- AUGMENTATIONS ---
def augment_graph_view(data, device):
    """
    Generate two augmented views of the graph batch.
    View 1: Feature Masking
    View 2: Edge Dropout
    """
    x, edge_index, edge_attr, batch = data.x.to(device), data.edge_index.to(device), data.edge_attr.to(device), data.batch.to(device)
    
    # --- View 1: Feature Masking ---
    x1 = x.clone()
    mask_rate = 0.2
    mask = torch.rand_like(x1) < mask_rate
    x1[mask] = 0
    
    # --- View 2: Edge Dropout ---
    # We keep node features intact but drop edges
    dropout_rate = 0.2
    num_edges = edge_index.shape[1]
    perm = torch.randperm(num_edges, device=device)
    preserve_count = int(num_edges * (1 - dropout_rate))
    preserved_edges = perm[:preserve_count]
    
    edge_index2 = edge_index[:, preserved_edges]
    edge_attr2 = edge_attr[preserved_edges] if edge_attr is not None else None
    
    # Return inputs formatted for model
    return (x1, edge_index, edge_attr, batch), (x, edge_index2, edge_attr2, batch)

# --- LOSS FUNCTION ---
def contrastive_loss(z1, z2, temperature=0.5):
    """
    Computes SimCLR loss for a batch of embeddings.
    z1, z2: [Batch, Dim]
    """
    batch_size = z1.size(0)
    
    # Normalize embeddings
    z1 = F.normalize(z1, dim=1)
    z2 = F.normalize(z2, dim=1)
    
    # Combine (2N)
    z_all = torch.cat([z1, z2], dim=0) # [2N, D]
    
    # Similarity matrix
    sim_matrix = torch.matmul(z_all, z_all.T) / temperature # [2N, 2N]
    
    # Mask out self-similarity
    mask = torch.eye(2 * batch_size, device=z_all.device).bool()
    sim_matrix.masked_fill_(mask, -9e15)
    
    # Positive pairs: (i, i+N) and (i+N, i)
    # We want sim(z1[i], z2[i]) to be high
    
    # Labels for CrossEntropy
    # Target for row i is (i + batch_size) % (2*batch_size)
    labels = torch.arange(2 * batch_size, device=z_all.device)
    labels = (labels + batch_size) % (2 * batch_size)
    
    loss = F.cross_entropy(sim_matrix, labels)
    return loss

# --- TRAINING LOOP ---
def train():
    print(f"Using device: {DEVICE}")
    
    # Load Data
    dataset = SentinelDataset(root=ROOT_DIR)
    # Shuffle for training
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
    
    # Initialize Model
    # input_dim=19 checked from previous step
    # edge_dim=12 checked from previous step
    model = SentinelGNN(input_dim=19, hidden_dim=HIDDEN_DIM, embedding_dim=EMBEDDING_DIM, edge_dim=12).to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    
    model.train()
    
    print("Starting Self-Supervised Training...")
    
    for epoch in range(EPOCHS):
        total_loss = 0
        batch_count = 0
        
        progress = tqdm(loader, desc=f"Epoch {epoch+1}/{EPOCHS}")
        
        for data in progress:
            optimizer.zero_grad()
            
            # Create two views
            (args1), (args2) = augment_graph_view(data, DEVICE)
            
            # Forward pass
            h1 = model(*args1) # [Batch, Emb]
            h2 = model(*args2) # [Batch, Emb]
            
            # Project
            z1 = model.project(h1)
            z2 = model.project(h2)
            
            # Loss
            loss = contrastive_loss(z1, z2, TEMPERATURE)
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            batch_count += 1
            
            progress.set_postfix({"loss": loss.item()})
            
        print(f"Epoch {epoch+1} Avg Loss: {total_loss / batch_count:.4f}")
        
    # Save Model
    torch.save(model.state_dict(), MODEL_SAVE_PATH)
    print(f"Model saved to {MODEL_SAVE_PATH}")

if __name__ == "__main__":
    train()
