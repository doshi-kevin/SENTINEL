# Stage 8: Visualization (The "Wow" Factor)

## 1. Overview
A 2D table of alerts is boring. We will build a **3D Force-Directed Graph** in the browser using `React Three Fiber`. This allows analysts to rotate, zoom, and inspect attacks intuitively.

## 2. Technology Stack
*   **Framework:** Next.js (React)
*   **3D Engine:** Three.js / React Three Fiber / Drei
*   **Styling:** TailwindCSS (modern, dark mode)

## 3. Key Features
1.  **The Holodeck:** 3D view of the process tree.
    *   *Normal Nodes:* Blue spheres.
    *   *Anomalous Nodes:* Pulsing Red spheres.
    *   *Attack Path:* Glowing lines connecting the sequence.
2.  **The Timeline:** A scrubber bar to replay the attack (like a video player).
3.  **The Story Panel:** Sidebar showing the generated plain-English narrative.

## 4. Current Status: ✅ PARTIAL
*   You have the `frontend` skeleton created.
*   `package.json` includes `three` and `react-three-fiber`.

## 5. Optimization & Aesthetics
*   **InstancedMesh:**
    *   *Optimization:* Don't create 1,000 `Mesh` objects. Use `InstancedMesh` to render 1,000 nodes with 1 draw call. Crucial for 60FPS.
*   **Bloom Effect:**
    *   *Aesthetics:* Use post-processing (UnrealBloom) to make attack nodes glow.
*   **LOD (Level of Detail):**
    *   Hide labels for distant nodes to reduce clutter.

## 6. Implementation Plan
1.  **Graph Component:** Build the `ForceGraph3D` component.
2.  **Data Fetching:** Hook up `SWR` or `React Query` to the FastAPI endpoints.
3.  **Interaction:** Click node -> Show details panel (Process ID, Path, User).
