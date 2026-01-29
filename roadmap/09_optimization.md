# Stage 9: Optimization & Hardening

## 1. Overview
Once the system works, we make it production-ready. This stage is about stability, resource usage, and edge cases.

## 2. Strategies

### Model Quantization
*   **Goal:** Reduce RAM usage and inference time.
*   **Action:** Convert PyTorch model from `float32` to `int8` (Dynamic Quantization). usually gives 2-4x speedup with <1% accuracy loss.

### Graph Caching
*   **Goal:** Prevent re-processing known benign patterns.
*   **Action:** Hash the graph topology. If `Hash(CurrentWindow) == Hash(PreviousWindow)`, skip inference. System maps often don't change for seconds at a time.

### False Positive Suppression
*   **Goal:** Reduce alert fatigue.
*   **Action:** `AllowList`. If user marks "BackupProcess.exe" as safe, add its signature to a filter that runs *before* the model.

## 3. Metrics
| Metric | Current (Est) | Target |
| :--- | :--- | :--- |
| **RAM Usage** | 2GB | < 500MB |
| **FPS (Frontend)** | 30 | 60 |
| **CPU Load** | 30% | < 10% |

## 4. Implementation Plan
1.  **Profiler:** Run `cProfile` on the backend to find bottlenecks.
2.  **Quantize Script:** Create `optimize_model.py`.
3.  **Stress Test:** Replay 100x speed logs and ensure the system doesn't crash.
