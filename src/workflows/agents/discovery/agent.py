"""Discovery Deep Agent."""

from __future__ import annotations

import logging
from typing import Any

from src.workflows.agents.prompt_blocks import (
    build_default_middleware,
    compose_system_prompt,
)

logger = logging.getLogger(__name__)


def build_discovery_subagents() -> list[dict[str, Any]]:
    """Same instruction-following worker the design agent uses."""
    from src.workflows.agents.design.subagents import build_general_purpose_subagent

    return [build_general_purpose_subagent()]


_DISCOVERY_RESPONSIBILITIES = """## Agent Responsibilities

Your canvas is `/scratch/discovery/canvas.md`.
Read `/scratch/supervisor/canvas.md` for intake facts. Write only your own canvas, drafts, and the deliverables the skill names.
Load the applicable discovery skill from the available skills list and follow it
end to end. Delegate heavy extraction to `general-purpose` and put the complete
instructions in the task."""

_DISCOVERY_SYSTEM_PROMPT = compose_system_prompt(
    role="Discovery",
    responsibilities=_DISCOVERY_RESPONSIBILITIES,
)


async def build_discovery_agent(*, llm: Any, store: Any | None = None) -> Any:
    """Build the Discovery deep agent compiled graph."""
    from src.workflows.agents.deep_state import DICEDeepAgentState
    from src.workflows.agents.discovery.tools import (
        ask_user,
        ask_user_interrupt,
        call_authenticated_api,
        proteas_code_analysis,
        select_repositories,
        set_phase,
    )
    from src.workflows.backends import get_shared_backend

    try:
        from deepagents import create_deep_agent  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "deepagents is not installed. Run: pip install deepagents",
        ) from exc

    system_prompt = _DISCOVERY_SYSTEM_PROMPT

    from src.workflows.agents.skill_prompt import build_minimal_skill_cards_section

    skill_cards = await build_minimal_skill_cards_section(
        tags=["discovery_agent"],
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
        call_authenticated_api,
        select_repositories,
        proteas_code_analysis,
        set_phase,
    ]

    create_kwargs: dict[str, Any] = {
        "model": llm,
        "tools": tools,
        "middleware": build_default_middleware(),
        "system_prompt": system_prompt,
        "name": "dice_discovery_agent",
        "backend": get_shared_backend(),
        "state_schema": DICEDeepAgentState,
        "subagents": build_discovery_subagents(),
    }

    if store is not None:
        create_kwargs["store"] = store

    return create_deep_agent(**create_kwargs)
