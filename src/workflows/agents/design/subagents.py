from __future__ import annotations

from typing import Any

from src.workflows.tools.hitl import ask_user, ask_user_interrupt

_GENERAL_PURPOSE_PROMPT = """You execute the single task you are given.

Follow those instructions exactly: the paths, the contract, the output shape, and the result they ask you to return.
Ground every value in `/artifacts/artifact.yaml` and `/scratch/canvas.md`.
If a required value is absent from the evidence, mark the gap rather than inventing one.
When a required fact, decision, or confirmation is missing, ask the user with `ask_user` or `ask_user_interrupt` and wait for the answer.
"""


def build_general_purpose_subagent() -> dict[str, Any]:
    """One instruction-following subagent that can ask the user a required question."""
    return {
        "name": "general-purpose",
        "description": (
            "Executes one detailed task exactly as written. "
            "The task carries the paths, the contract, and the required result. "
            "Asks the user with ask_user or ask_user_interrupt when a required answer is missing."
        ),
        "system_prompt": _GENERAL_PURPOSE_PROMPT,
        "tools": [ask_user, ask_user_interrupt],
    }


def build_design_subagents() -> list[dict[str, Any]]:
    """One general-purpose subagent. The task text is the whole assignment."""
    return [build_general_purpose_subagent()]
