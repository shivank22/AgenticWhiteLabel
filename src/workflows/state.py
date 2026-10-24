# TODO: reconstruct from photo edge (module docstring / lines ~1-11 not fully visible)

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages  # type: ignore[import]


def _keep_last(current: Any, update: Any) -> Any:
    """Last-writer-wins reducer for scalar/list state fields.

    Used on fields that can be written by both the outer graph input and an
    embedded subgraph node in the same step.
    """
    return update if update is not None else current


class PendingInteraction(TypedDict, total=False):
    """Uniform structure for all interrupt payloads regardless of phase."""

    interrupt_id: str
    type: str  # "intake_question" | "clarification" | "approval"
    question: str
    phase: str
    raw: dict[str, Any]


class DICEState(TypedDict, total=False):
    """Shared graph state - execution context only.

    total=False: all fields are optional so nodes can return partial updates.

    All non-messages fields use the _keep_last reducer. When a Command.update
    is applied at the same step that an embedded deep-agent subgraph also writes
    state, LangGraph sees two writes per channel. _keep_last makes every
    channel accept multiple writes and keep the last non-None value, which is
    the correct last-writer-wins semantic for all scalar/list context fields.
    """

    # --- identity ------------------------------------------------------------
    user_id: Annotated[str, _keep_last]
    thread_id: Annotated[str, _keep_last]
    aa_number: Annotated[str | None, _keep_last]

    # --- conversation --------------------------------------------------------
    # messages uses add_messages (append reducer) - required for deep-agent embedding.
    # All other conversation fields use _keep_last (last-writer-wins).
    messages: Annotated[list[AnyMessage], add_messages]
    user_input: Annotated[str, _keep_last]
    resume_message: Annotated[str, _keep_last]

    # --- phase control -------------------------------------------------------
    phase: Annotated[str, _keep_last]

    # --- artifact references (NEVER the full YAML) ---------------------------
    application_id: Annotated[str | None, _keep_last]
    artifact_id: Annotated[str | None, _keep_last]
    artifact_url: Annotated[str | None, _keep_last]
    artifact_version: Annotated[int | None, _keep_last]
    migration_id: Annotated[str | None, _keep_last]

    # --- discovery -----------------------------------------------------------
    discovery_status: Annotated[str | None, _keep_last]
    run_id: Annotated[str | None, _keep_last]

    # --- response / interaction ----------------------------------------------
    ai_response: Annotated[str, _keep_last]
    pending_interaction: Annotated[PendingInteraction | None, _keep_last]
    todos: Annotated[list[dict[str, Any]] | None, _keep_last]

    # --- errors --------------------------------------------------------------
    errors: Annotated[list[str], _keep_last]
