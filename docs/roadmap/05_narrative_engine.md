# Stage 5: Narrative Engine (The "Storyteller")

## 1. Overview
This is the user-facing differentiator. Instead of `Alert: Anomaly Score 0.98`, we output: *"Malware 'netcat' scanned the network and exfiltrated /etc/passwd to external IP."*

## 2. Construction
We use a **Template-Based Generation** system augmented by the semantic roles. LLMs are too slow and hallucinate; structured templates are deterministic and trustworthy for security.

### Narrative Templates
*   **Infection:** `[Subject:Executor] downloaded [Object:File] from [Object:Socket] acting as [Role:Downloader].`
*   **Lateral Movement:** `[Subject:Process] scanned [Number] hosts and connected to [Target:IP].`
*   **Exfiltration:** `[Subject:Process] read [Object:File] and transmitted [Bytes] to [Target:IP].`

## 3. Current Status: ❌ NOT STARTED
*   No code exists for this yet.

## 4. Best Practices
*   **Causal Chaining:**
    *   *Strategy:* The engine must follow the edges backward.
    *   *Logic:* found Anomaly -> Trace back "Cause" edges (Parent, Writer) -> Stop at root cause (e.g., Phishing Email or USB insert).
*   **Summarization:**
    *   *Optimization:* Don't list every packet. "Connected to 50 IPs" is better than 50 lines of logs.
*   **Confidence Scores:**
    *   Always attach the model's anomaly score to the story. "We are 98% confident this is an attack."

## 5. Metrics
| Metric | Target |
| :--- | :--- |
| **Readability** | Flesch-Kincaid Grade 8 (Simple English) |
| **Completeness** | Story must include Source, Action, and Target |

## 6. Implementation Plan
1.  **StoryBuilder Class:** Create a class that takes an annotated graph (from Stage 4).
2.  **Traversal Algorithms:** Implement BFS (Breadth-First Search) starting from the most anomalous node to find its neighbors.
3.  **String Construction:** Map the subgraph to the English templates.
