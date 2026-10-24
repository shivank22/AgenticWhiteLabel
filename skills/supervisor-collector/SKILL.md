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
2. Initialize `/artifacts/artifact.yaml` with the application identity and status, and start `/scratch/canvas.md`.
3. Delegate to `discovery-agent` to begin application discovery.
