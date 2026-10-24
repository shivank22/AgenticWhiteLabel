"""Shared system-prompt composition for DICE deep agents."""

from __future__ import annotations

from typing import Any

_WORKSPACE = """## Workspace

Mounted directories:
- `/skills/` — skill contracts
- `/templates/` — output templates
- `/scratch/` — working memory; the live canvas is `/scratch/canvas.md`
- `/artifacts/` — validated deliverables; the canonical manifest is `/artifacts/artifact.yaml`

`/artifacts/artifact.yaml` is the structured index: identity, status, a short summary, and the paths of deliverables the active skill produced. Read it first. Register every new deliverable there. Do not put raw notes in it.

`/scratch/canvas.md` is the live evidence ledger shared with subagents: extracted facts, gaps, and drafts. Keep it current so nothing is lost between delegated tasks.

Organize work with a live task list. Use the code interpreter for computation. Delegate heavy or parallel detail through subagents, passing paths from the skill and the manifest. Write only the deliverables the skill names, then register those paths in the manifest. During rework, change only the one artifact the user named.

When a required fact, decision, or confirmation is missing, ask the user with `ask_user` or `ask_user_interrupt` and wait for the answer."""


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
        _WORKSPACE.strip(),
    ]
    if phase_contract:
        parts.extend(["", phase_contract.strip()])
    return "\n".join(parts).strip() + "\n"


def build_default_middleware() -> list[Any]:
    """Todo planning plus a QuickJS code interpreter for every Deep Agent."""
    from langchain.agents.middleware import TodoListMiddleware
    from langchain_quickjs import CodeInterpreterMiddleware

    return [TodoListMiddleware(), CodeInterpreterMiddleware()]
