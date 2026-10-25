---
id: supervisor-collector
name: Supervisor Collector
description: Collect application intake details and instantiate the application record.
tags: [supervisor_agent, collector]
env: [dev, all]
version: 0.1.0
---

# Supervisor Collector

1. Confirm required intake fields (AA number, application name) with the user if missing.
2. Initialize `/artifacts/artifact.yaml` from `/templates/artifact.yaml` with the application identity and status. Create `/scratch/supervisor/canvas.md` from `/templates/memory/canvas.md`. Record intake facts on the canvas.
3. Delegate to `discovery-agent`. The task names the discovery skill path, `/scratch/supervisor/canvas.md` as intake evidence, and `/scratch/discovery/canvas.md` as the file discovery owns.
