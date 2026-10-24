---
id: application-discovery
name: Application Discovery
description: Discover application estate, servers, and code signals for migration assessment.
tags: [discovery_agent, discovery]
env: [dev, all]
version: 0.1.0
---

# Application Discovery

1. Ensure an AA number is present — ask the user if missing.
2. Gather server / inventory evidence. Keep raw payloads under `/scratch/discovery/` and extracted facts in `/scratch/canvas.md`.
3. Run repository selection and code analysis when applicable. Use `/templates/` for the expected deliverable shape.
4. Persist `/artifacts/discovery/scope-inventory.yaml`, `/artifacts/discovery/discovery-details.yaml`, and `/artifacts/discovery/discovery-code-v1.yaml`, and register those paths in `/artifacts/artifact.yaml`.
