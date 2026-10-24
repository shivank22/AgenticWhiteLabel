from __future__ import annotations

from typing import Any

from src.workflows.agents.prompt_blocks import (
    build_default_middleware,
    compose_system_prompt,
)

_SUPERVISOR_RESPONSIBILITIES = """## Agent Responsibilities

Coordinate the application migration lifecycle from intake through discovery and
target-platform design:

1. **Intake**: Follow the collector skill.
2. **Discovery & Review**: Delegate discovery to `discovery-agent`, summarize the outcome for the user, and confirm whether they are satisfied. If not, change only the one artifact they named, directly or through `general-purpose`, and re-confirm.
3. **Design & Review**: Delegate design to `design-agent`, summarize the outcome for the user, and confirm whether they are satisfied. If not, change only the one artifact they named, directly or through `general-purpose`, and re-confirm.
4. **Completion**: Mark the workflow complete once the user approves the design."""

_SUPERVISOR_SYSTEM_PROMPT = compose_system_prompt(
    role="Supervisor",
    responsibilities=_SUPERVISOR_RESPONSIBILITIES,
)


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
    from src.workflows.agents.design.subagents import build_general_purpose_subagent
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
                "Executes application discovery and registers deliverables in "
                "/artifacts/artifact.yaml."
            ),
            "runnable": discovery_runnable,
        },
        {
            "name": "design-agent",
            "description": (
                "Executes target-platform migration design and registers "
                "deliverables in /artifacts/artifact.yaml."
            ),
            "runnable": design_runnable,
        },
        build_general_purpose_subagent(),
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
