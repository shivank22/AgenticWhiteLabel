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

1. Read `/artifacts/artifact.yaml` and consolidate discovery facts and gaps into `/scratch/canvas.md`. Use `/templates/` for the expected section shape.
2. Conduct the blocking-question interview and open-decisions confirmation gate with the user, saving `/artifacts/design/interview-backfill.yaml` and `/artifacts/design/open-decisions.yaml`.
3. Delegate each document draft to `general-purpose`. The task must name the contract path, the output path, and the result to return.
4. Delegate each evidence check to `general-purpose`, naming the drafted paths to compare, and resolve any flagged gaps.
5. Persist `/artifacts/design/design.yaml`, `/artifacts/design/UK8S-Discovery-Baseline.md`, and `/artifacts/design/UK8S-Target-Architecture-and-Migration-Plan.md`, and register those paths in `/artifacts/artifact.yaml`.
