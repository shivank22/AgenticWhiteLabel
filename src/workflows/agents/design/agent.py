"""Design Deep Agent - platform-aware migration plan generator."""

from __future__ import annotations

from typing import Any

from src.workflows.agents.prompt_blocks import (
    build_default_middleware,
    compose_system_prompt,
)

_DESIGN_RESPONSIBILITIES = """## Design Contract

Confirm the target migration platform with the user if not already selected,
load the matching migration skill from the available skills list, and follow it
end to end. Delegate detailed work to `general-purpose` and put the complete
instructions in the task."""

_DESIGN_SYSTEM_PROMPT = compose_system_prompt(
    role="Design",
    responsibilities=_DESIGN_RESPONSIBILITIES,
)


async def build_design_agent(*, llm: Any, store: Any | None = None) -> Any:
    """Build the Design deep-agent compiled graph."""
    from src.workflows.agents.deep_state import DICEDeepAgentState
    from src.workflows.agents.design.subagents import build_design_subagents
    from src.workflows.agents.design.tools import ask_user, ask_user_interrupt, set_phase
    from src.workflows.backends import get_shared_backend

    try:
        from deepagents import create_deep_agent  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "deepagents is not installed. Run: pip install deepagents",
        ) from exc

    system_prompt = _DESIGN_SYSTEM_PROMPT

    from src.workflows.agents.skill_prompt import build_minimal_skill_cards_section

    skill_cards = await build_minimal_skill_cards_section(
        tags=["design_agent"],
        env="dev",
        limit=8,
    )
    if skill_cards:
        system_prompt = (
            system_prompt.strip() + "\n" + skill_cards.strip()
        ).strip() + "\n"

    tools = [
        ask_user,
        ask_user_interrupt,
        set_phase,
    ]

    create_kwargs: dict[str, Any] = {
        "model": llm,
        "tools": tools,
        "middleware": build_default_middleware(),
        "system_prompt": system_prompt,
        "name": "dice_design_agent",
        "backend": get_shared_backend(),
        "state_schema": DICEDeepAgentState,
        "subagents": build_design_subagents(),
    }

    if store is not None:
        create_kwargs["store"] = store

    return create_deep_agent(**create_kwargs)
