from __future__ import annotations

from typing import Any

from src.workflows.agents.prompt_blocks import (
    build_default_middleware,
    compose_system_prompt,
)

_SUPERVISOR_RESPONSIBILITIES = """## Agent Responsibilities

Your canvas is `/scratch/supervisor/canvas.md`.
You are the only agent that reads every canvas. Before any user summary or phase change, read `/artifacts/artifact.yaml` and all three canvas files, then speak from those files.
Coordinate the application migration lifecycle from intake through discovery and
target-platform design:
1. **Intake**: Follow the collector skill.
2. **Discovery & Review**: Delegate discovery to `discovery-agent`. The task names the discovery skill path, `/scratch/supervisor/canvas.md`, and `/scratch/discovery/canvas.md`. Summarize the outcome for the user, and confirm whether they are satisfied. If not, delegate to `general-purpose`. The task states only the artifact path and the change. Re-confirm.
3. **Design & Review**: Delegate design to `design-agent`. The task names the design skill path, `/scratch/discovery/canvas.md`, and `/scratch/design/canvas.md`. Summarize the outcome for the user, and confirm whether they are satisfied. If not, delegate to `general-purpose`. The task states only the artifact path and the change. Re-confirm.
4. **Completion**: Mark the workflow complete once the user approves the design."""

_SUPERVISOR_SYSTEM_PROMPT = compose_system_prompt(
    role="Supervisor",
    responsibilities=_SUPERVISOR_RESPONSIBILITIES,
)

_REWORK_PROMPT = """You change the artifact named in the task. The task states the path and the change.
Use `ls` to list `/artifacts/`, `read_file` to read any artifact, and `write_file` to write the changed artifact in full.
You may read every file under `/artifacts/`. Write only the path named in the task.
Do not use `edit_file`. Validated artifacts reject in-place edits.
"""


def build_supervisor_rework_subagent() -> dict[str, Any]:
    """Rework worker. The task is the artifact path and the change."""
    return {
        "name": "general-purpose",
        "description": (
            "Changes the artifact the user named. "
            "The task states the artifact path and the change."
        ),
        "system_prompt": _REWORK_PROMPT,
        "tools": [],
    }


async def build_supervisor_agent(
    *,
    llm: Any,
    store: Any | None = None,
    discovery_agent: Any | None = None,
    design_agent: Any | None = None,
) -> Any:
    """Build the DICE Supervisor deep-agent compiled graph with Discovery and Design as CompiledSubAgents."""
    from src.workflows.agents.deep_state import DICEDeepAgentState
    from src.workflows.agents.design.agent import build_design_agent
    from src.workflows.agents.discovery.agent import build_discovery_agent
    from src.workflows.agents.supervisor.tools import (
        ask_user,
        ask_user_interrupt,
        create_application_migration,
        instantiate_application,
        list_application_migrations,
        set_phase,
        update_application_migration,
    )
    from src.workflows.backends import get_shared_backend

    try:
        from deepagents import create_deep_agent  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "deepagents is not installed. Run: pip install deepagents",
        ) from exc

    discovery_runnable = discovery_agent or await build_discovery_agent(
        llm=llm, store=store
    )
    design_runnable = design_agent or await build_design_agent(
        llm=llm, store=store
    )

    subagents: list[dict[str, Any]] = [
        {
            "name": "discovery-agent",
            "description": (
                "Executes application discovery, writes "
                "/scratch/discovery/canvas.md, "
                "and registers deliverables in /artifacts/artifact.yaml."
            ),
            "runnable": discovery_runnable,
        },
        {
            "name": "design-agent",
            "description": (
                "Executes target-platform migration design, writes "
                "/scratch/design/canvas.md, "
                "and registers deliverables in /artifacts/artifact.yaml."
            ),
            "runnable": design_runnable,
        },
        build_supervisor_rework_subagent(),
    ]

    tools = [
        ask_user,
        ask_user_interrupt,
        set_phase,
        instantiate_application,
        list_application_migrations,
        create_application_migration,
        update_application_migration,
    ]

    from src.workflows.agents.skill_prompt import build_minimal_skill_cards_section

    system_prompt = _SUPERVISOR_SYSTEM_PROMPT
    skill_cards = await build_minimal_skill_cards_section(
        tags=["supervisor_agent"],
        env="dev",
        limit=8,
    )

    if skill_cards:
        system_prompt = (
            system_prompt.strip() + "\n\n" + skill_cards.strip()
        ).strip() + "\n"

    create_kwargs: dict[str, Any] = {
        "model": llm,
        "tools": tools,
        "middleware": build_default_middleware(),
        "subagents": subagents,
        "system_prompt": system_prompt,
        "name": "dice_supervisor_agent",
        "backend": get_shared_backend(),
        "state_schema": DICEDeepAgentState,
    }

    if store is not None:
        create_kwargs["store"] = store

    return create_deep_agent(**create_kwargs)
