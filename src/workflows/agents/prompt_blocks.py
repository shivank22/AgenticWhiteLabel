"""Shared system-prompt composition for DICE deep agents."""

from __future__ import annotations

from typing import Any

_AGENT_FOLDERS = {
    "supervisor": "supervisor",
    "discovery": "discovery",
    "design": "design",
}

_SCRATCH_FILES = (
    "/scratch/supervisor/canvas.md",
    "/scratch/discovery/canvas.md",
    "/scratch/design/canvas.md",
)


def agent_canvas_path(role: str) -> str:
    """Return the single scratch canvas path for a phase agent role."""
    folder = _AGENT_FOLDERS.get(role.strip().lower(), "<agent>")
    return f"/scratch/{folder}/canvas.md"


def _workspace(role: str) -> str:
    canvas = agent_canvas_path(role)
    folder = _AGENT_FOLDERS.get(role.strip().lower(), "<agent>")
    scratch_list = "\n".join(f"- `{path}`" for path in _SCRATCH_FILES)
    return f"""## Workspace

Mounted directories:
- `/skills/` — skill contracts
- `/templates/` — output templates, including `/templates/memory/canvas.md` and `/templates/artifact.yaml`
- `/scratch/` — per-agent working memory
- `/artifacts/` — validated deliverables; the canonical manifest is `/artifacts/artifact.yaml`

Your canvas is `{canvas}`. Durable scratch files:
{scratch_list}
`canvas.md` is the only per-agent memory file: facts with a source path, gaps, the draft outline, and a handoff with Done, Artifacts, Open gaps, and Next. Create it from `/templates/memory/canvas.md` if it is missing. Update it before every delegation and before you return. Append; do not wipe prior decisions. A downstream phase agent may read an upstream canvas. Do not rewrite another agent's canvas.
`/artifacts/artifact.yaml` is the structured index: identity, status, a short summary, and the paths of deliverables the active skill produced. Read it first. Use `/templates/artifact.yaml` for the shape. Register every new deliverable there. Do not put the canvas body in it.
Long drafts go to `/scratch/{folder}/drafts/<task>.md`. Pass paths, not document bodies.
Pick the one skill whose description matches the user's answer. `read_file` that `SKILL.md` once as the router and turn its phases into `write_todos`. Read only the module or render contract for the `in_progress` phase. Use `read_file(path, limit=1000)` when that file is long, then continue at `offset=1000` only if that page stops before the phase's last step.
After each phase, and before any delegation, reduce what must survive into your canvas: facts with a source path, gaps, decisions, and the next step. Use the sections in `/templates/memory/canvas.md`. Do not paste the skill body or draft text.
Chat history is compacted automatically. After a phase is on the canvas, do not re-read earlier modules. Later steps must be recoverable from the canvas and the todos.
Record facts on your canvas with a source path. If a required fact, decision, or confirmation is missing, ask the user with `ask_user` or `ask_user_interrupt` and wait for the answer. Do not invent a value.
Organize work with a live task list. Use the code interpreter for computation. Delegate only heavy or parallel detail. The task must name the objective, the skill or contract path, the input files, the unique output path, and the short result to return: status, paths written, gaps, and a few-sentence summary. After the worker returns, merge its findings into your canvas.
Write only the deliverable paths the skill names, using `/templates/` for section shape. A document is ready when every required section exists, claims trace to the canvas or a user answer, and unknowns are explicit gaps. During rework, change only the one artifact the user named.
The supervisor, before any user summary or phase change, reads `/artifacts/artifact.yaml` and all three canvas files, then speaks from those files."""


_PHASE_TODOS = """## Phase todos

Todos are the skill-router phases, not one item per skill line. One phase is `in_progress`.
Delegate that phase as one `general-purpose` task. The task repeats the todo, the contract path, the input files, the output path, and the done check: required sections present, claims sourced, gaps explicit.
Mark the todo complete only after the handoff names status, paths written, and gaps, and those paths match the task. If the handoff is thin or a path is missing, delegate again with the gap named. The worker starts with a fresh message list, so the retry task must include the gap."""


def compose_system_prompt(
    *,
    role: str,
    responsibilities: str,
    phase_contract: str | None = None,
) -> str:
    parts = [
        f"You are the DICE {role} agent.",
        "",
        responsibilities.strip(),
        "",
        _workspace(role).strip(),
    ]
    if role.strip().lower() in {"discovery", "design"}:
        parts.extend(["", _PHASE_TODOS.strip()])
    if phase_contract:
        parts.extend(["", phase_contract.strip()])
    return "\n".join(parts).strip() + "\n"


def build_default_middleware() -> list[Any]:
    """Todo planning plus a QuickJS code interpreter for every Deep Agent."""
    from langchain.agents.middleware import TodoListMiddleware
    from langchain_quickjs import CodeInterpreterMiddleware

    return [TodoListMiddleware(), CodeInterpreterMiddleware()]
