# DICE — Original Agentic Framework

LangGraph outer orchestrator embedding **deepagents** (supervisor / discovery / design), with Postgres checkpoints, a validating `CompositeBackend`, and HITL via `ask_user` → `interrupt()` → `Command(resume=…)`.

Reconstructed from the screen-capture set in `images/` (HITL, resume, graph routing, backends, agents). **Domain tools are stubs** — add them next under each agent’s `tools.py`.

## Architecture

```
API / UI
   │  awaiting_input  ←→  Command(resume=…)
   ▼
orchestrator_graph (DICEState, phase router)
   ├── supervisor  (collection | review | review_design | rework_*)
   ├── discovery
   └── design (+ baseline-author / target-plan-author / design-reviewer)
         │
         ▼
CompositeBackend  → validating StoreBackend
                  → /skills/     (FilesystemBackend)
                  → /templates/  (FilesystemBackend)
         │
         ▼
Postgres checkpointer + store (+ LISTEN/NOTIFY for multi-pod chat)
```

### Phase machine

| Phase | Owner | Typical next step |
|-------|--------|-------------------|
| `""` / `collection` | supervisor | instantiate → auto `discovery` |
| `discovery` | discovery | handoff → `design` or `review` |
| `review` | supervisor (HITL) | yes → `design` / rework / complete |
| `design` | design | `populate_design_artifacts` → `review_design` |
| `review_design` | supervisor (HITL) | approve → `complete` |
| `rework_*` | supervisor | edit artifacts, then advance |
| `complete` | END | — |

## Layout

```
src/
  workflows/
    state.py                 # DICEState + PendingInteraction
    interrupts.py            # interrupt payload + gate ids + decision normalize
    resume.py                # resolve_resume_map
    runtime.py               # compiled graph singleton
    runtime_notify.py        # Postgres LISTEN/NOTIFY
    graphs/orchestrator_graph.py
    backends/                # CompositeBackend + validating store
    agents/
      supervisor|discovery|design/
      skill_prompt.py
    tools/hitl.py            # ask_user, set_phase (live)
    tools/stubs.py           # deferred domain tools
  memory/  config/  llm/  validators/  services/
skills/                      # progressive-disclosure SKILL.md packs
images/                      # original screen captures
```

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

# Unit tests (no LLM / Postgres required)
pytest -q
```

Without `DICE_DATABASE_URL`, the checkpointer falls back to in-memory `MemorySaver`.

## Chat UI

```bash
pip install -e ".[dev,web]"
python -m src.api
```

Open http://127.0.0.1:8080. The page talks to the orchestrator: a message starts or continues the supervisor, and an open interrupt (`awaiting_input`) is answered through the same composer — free text, choices, or tool approve / edit / reject. Set `OPENAI_API_KEY` in `.env`. Threads stay in memory for the life of the process unless Postgres is configured.

## HITL contract

1. Agent calls `ask_user(...)` → LangGraph `interrupt(payload)`.
2. Checkpoint stores open interrupts; API returns `status="awaiting_input"`.
3. Client answers → `resolve_resume_map(snapshot, answer)` → `Command(resume=resume_map)`.
4. Runtime interrupt id is canonical for resume; caller id is preserved as `payload_interrupt_id`.

## Tools

| Tool | Status | Path |
|------|--------|------|
| `ask_user` / `set_phase` / tool review | live | `src/workflows/tools/hitl.py` |
| `call_authenticated_api` | live | `src/workflows/agents/discovery/tools/authenticated_api.py` |
| thread filesystem IO | live | `src/io/thread_files.py` + `src/workflows/tools/filesystem_io.py` |
| remaining domain tools | stubs | agent `tools` packages |

**How tools use the backend (from your usage photos):**
- HITL via `ask_user` / `request_tool_review` → LangGraph `interrupt()`
- Side-effecting APIs go through `review_tool_call` (re-ask on unknown, never silent-approve)
- Successful API payloads persist with `persist_successful_api_result` → store-backed `/scratch/` or `/artifacts/` under namespace `("users", user_id, "threads", thread_id, "filesystem")`

`call_authenticated_api` is HITL-gated (`tool_review`), supports Bearer or PACE OAuth, and persists PACE results to `/scratch/discovery/pace-servers.json`.

Still deferred — replace stubs in:

- `src/workflows/agents/supervisor/tools.py`
- `src/workflows/agents/discovery/tools/` (except authenticated_api)
- `src/workflows/agents/design/tools.py`

## Notes from the photos

- Subgraphs must **not** get a separate checkpointer — inherit the outer one so interrupts propagate.
- Graph state holds **artifact refs only**, never full YAML bodies.
- Skills are listed as cards in the system prompt; bodies load via `read_file("/skills/.../SKILL.md")`.
