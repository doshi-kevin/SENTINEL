# Stage 10: Deployment

## 1. Overview
The final stage is packaging SENTINEL-Z so it can be installed on any machine with a single command.

## 2. Architecture
We will use **Docker Compose** to orchestrate the services.

```yaml
services:
  sentinel-backend:
    image: python:3.11
    command: python src/main.py
    volumes:
      - /var/log/syslog:/logs
  
  sentinel-frontend:
    image: node:18-alpine
    ports:
      - "3000:3000"
```

## 3. Deliverables
1.  **Dockerfile.backend:** Multi-stage python build (install torch, then copy code).
2.  **Dockerfile.frontend:** Node build -> Static export or specialized runner.
3.  **run.sh:** One-click startup script.

## 4. Documentation
*   **User Manual:** How to interpret the dashboard.
*   **Installation Guide:** Prereqs (Docker, Drivers).

## 5. Future Proofing
*   **CI/CD:** Add GitHub Actions for automated testing on push.
*   **Model Updates:** Mechanism to pull new trained weights from a central server.

## 6. Implementation Plan
1.  Write `Dockerfiles`.
2.  Test clean install on a fresh VM.
3.  Record Demo Video.
