# Stage 7: API Layer

## 1. Overview
The bridge between the Python backend (Detection Engine) and the Frontend (Dashboard). We will use **FastAPI** for high performance and automatic documentation.

## 2. API Endpoints

### `/status`
*   **GET:** Returns system health, events processed per second, and active model version.

### `/alerts`
*   **GET:** List of recent detected anomalies (paginated).
    *   *Response:* `[{id: 1, severity: "High", story: "Scanner detected...", timestamp: ...}]`
*   **GET /:id:** Detailed graph JSON for a specific alert (for visualization).

### `/stream` (WebSocket)
*   **WS:** Pushes real-time graph updates to the 3D visualizer.

## 3. Current Status: ❌ NOT STARTED
*   `src/api` directory exists but is empty.

## 4. Architecture & Optimization
*   **FastAPI + Uvicorn:** Standard high-perf python stack.
*   **WebSocket Broadcasting:**
    *   *Strategy:* The frontend shouldn't poll. The server pushes updates.
    *   *Optimization:* Send **Diffs** (deltas) of the graph, not the whole graph every second. "Node A added", "Edge B removed". Reduces bandwidth by 90%.
*   **Pydantic Models:** Enforce strict typing on all input/output to prevent runtime errors.

## 5. Metrics
| Metric | Target |
| :--- | :--- |
| **Response Time** | < 50ms for REST endpoints |
| **Broadcast Delay** | < 100ms for WebSocket frames |

## 6. Implementation Plan
1.  **Schema Definition:** Define the `Alert` and `Graph` response models.
2.  **Server Setup:** Initialize FastAPI app in `src/api/server.py`.
3.  **Integration:** Connect the `stage_6_realtime` output queue to the WebSocket broadcaster.
