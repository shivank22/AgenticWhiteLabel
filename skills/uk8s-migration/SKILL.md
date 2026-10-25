---
id: uk8s-migration
name: UK8S Migration
description: Platform-aware UK8S migration design — interview, score, render, review.
tags: [design_agent, migration, uk8s]
env: [dev, all]
version: 0.1.0
---

# UK8S Migration

This SKILL.md is a router. Step modules live under `/skills/uk8s-migration/modules/`
and render contracts live under `/skills/uk8s-migration/render/`.

## Flow

1. Read `/artifacts/artifact.yaml` and `/scratch/discovery/canvas.md`. Use the `ls` tool on `/scratch/discovery/` to see what other discovery documents are visible, and read the ones that apply. Create `/scratch/design/canvas.md` from `/templates/memory/canvas.md` if it is missing, and consolidate discovery facts and gaps onto the design canvas. Use `/templates/` for the expected section shape.
2. Conduct the blocking-question interview and open-decisions confirmation gate with the user, saving `/artifacts/design/interview-backfill.yaml` and `/artifacts/design/open-decisions.yaml`.
3. Delegate each document draft to `general-purpose`. The task must name the contract path, the input files, a unique output path under `/scratch/design/drafts/`, and the short result to return: status, paths written, gaps, and a few-sentence summary.
4. Delegate each evidence check to `general-purpose`, naming the drafted paths to compare, and resolve any flagged gaps. Merge accepted findings into `/scratch/design/canvas.md`.
5. Persist `/artifacts/design/design.yaml`, `/artifacts/design/UK8S-Discovery-Baseline.md`, and `/artifacts/design/UK8S-Target-Architecture-and-Migration-Plan.md`, and register those paths in `/artifacts/artifact.yaml`. Write the handoff on `/scratch/design/canvas.md`.
