# Stage 2: Self-Supervised Encoder (The "Brain")

## 1. Overview
This is the core innovation. We train a Graph Neural Network (GNN) to understand "normal" system behavior without needing attack labels. By learning the grammar of normal system execution, the model will later identify anything "ungrammatical" (anomalous) as a potential attack.

## 2. Architecture
The `SentinelZEncoder` moves beyond simple autoencoders by combining three objectives:

1.  **Structural Encoding:** GraphSAGE layers to aggregate local neighborhood information (Process A talks to File B).
2.  **Temporal Context:** A Transformer (Attention) layer that looks at the sequence of graphs. "Process A usually reads File B *after* connecting to Socket C."
3.  **Self-Supervised Heads:**
    *   **Contrastive Loss (NT-Xent):** Pushes temporally adjacent windows close together in embedding space, pulls random windows apart.
    *   **Masked Prediction:** Like BERT for graphs. Mask an edge (e.g., the write to a file) and ask the model to predict it from context.

## 3. Current Status: ⚠️ PARTIAL
*   **Accomplished:**
    *   Advanced model architecture defined in `src/sentinel_z/self_supervised_encoder.py`.
*   **Missing:**
    *   The training script `train_encoder.py` relies on a dummy model.
    *   Model has not been trained on the full dataset.

## 4. Accuracy & Optimization Strategies
*   **Metric Learning:** The key to accuracy is the **Separation Margin** (distance between benign and attack scores).
    *   *Strategy:* Use "Hard Negative Mining" in contrastive loss—specifically focus on benign windows that look very different from each other.
*   **Batch Size:**
    *   *Optimization:* Larger batch sizes (64+) stabilize contrastive learning.
*   **Gradient Accumulation:** If GPU memory is tight, accumulate gradients to simulate larger batches.
*   **Feature Importance:**
    *   *Strategy:* Use learnable semantic embeddings for node types (Process, File, Socket) instead of one-hot encoding.

## 5. Metrics & Targets
| Metric | Target | Why? |
| :--- | :--- | :--- |
| **Training Loss** | Converge < 0.1 | Indicates model learned the "normal" grammar |
| **Separation** | > 2.0 std devs | Attack scores should be clearly distinct from benign noise |
| **Reconstruction** | > 90% Acc | Model can accurately predict masked edges |

## 6. Implementation Plan (Immediate Priority)
1.  **Refactor `train_encoder.py`:**
    *   Import `SentinelZEncoder`.
    *   Wire up the self-supervised loss functions.
2.  **Train Pilot Model:**
    *   Run 50 epochs on the 6,000 graph dataset.
    *   Save best checkpoint based on validation loss.
3.  **visualize Embeddings:**
    *   Use t-SNE to plot the learn embeddings of "normal" data. They should form tight clusters.
