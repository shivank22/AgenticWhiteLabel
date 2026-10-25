---
id: application-discovery
name: Application Discovery
description: Discover application estate, servers, and code signals for migration assessment.
tags: [discovery_agent, discovery]
env: [dev, all]
version: 0.1.0
---

# Application Discovery

1. Ensure an AA number is present — ask the user if missing. Read `/artifacts/artifact.yaml` and `/scratch/supervisor/canvas.md`.
2. Create `/scratch/discovery/canvas.md` from `/templates/memory/canvas.md` if it is missing. Update the canvas before every delegation and before you return.
3. Gather server / inventory evidence. Keep raw payloads under `/scratch/discovery/` and extracted facts, each with a source path, in `/scratch/discovery/canvas.md`.
4. Run repository selection and code analysis when applicable. Use `/templates/` for the expected deliverable shape. Delegate heavy extraction to `general-purpose` with one objective, the input paths, a unique output under `/scratch/discovery/drafts/`, and a short return of status, paths written, gaps, and a few-sentence summary. Merge those findings into the canvas.
5. Persist `/artifacts/discovery/scope-inventory.yaml`, `/artifacts/discovery/discovery-details.yaml`, and `/artifacts/discovery/discovery-code-v1.yaml`, and register those paths in `/artifacts/artifact.yaml`. Write the handoff on `/scratch/discovery/canvas.md`.
